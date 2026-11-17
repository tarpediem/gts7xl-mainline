#!/usr/bin/env bash
# Write a pmOS rootfs image (nested GPT: pmOS_boot + pmOS_root) to the gts7xl USERDATA
# partition, over the USB network, from the pmOS debug shell. ERASES One UI's data.
#
# usage: tools/write-userdata.sh --image FILE [--dry-run] [--expect-sha256 HEX]
#                                [--pit FILE] [--disk sda] [--host IP] [--local-ip IP]
#                                [--notes FILE]
#
#   --image          raw image from `pmbootstrap install --no-split --no-sparse
#                    --sector-size 4096` (not an Android sparse image)
#   --expect-sha256  refuse unless the image has this sha256
#   --pit            default build/gts7xl.pit; USERDATA start (and size if the PIT gives one)
#                    must match the partition found on the tablet. Skipped if absent.
#   --disk           the disk the partition must be on (default sda)
#   --notes          where the result is logged (default NOTES.md)
#   --dry-run        resolve and check the target (read-only), print the plan, write nothing
#
# Steps: check the image (size multiple of the UFS block size, GPT at 4096) -> find the
# partition with PARTNAME=userdata in /sys/class/block/*/uevent on the tablet; refuse unless
# there is exactly one, on --disk, not read-only, not mounted, no holders (loop/dm), big
# enough, 4096-byte blocks, same start as the PIT -> print the plan -> the owner types
# ERASE-USERDATA -> resolve again (must be the same) -> serve the image here
# (tools/serve_file.py on --local-ip), `wget -O - | dd of=/dev/<part> bs=4M conv=fsync`
# on the tablet, detached from telnet, polled -> drop caches, read back the image length
# from the partition, compare sha256 -> log to --notes.
# The tablet must be in the debug shell (telnet 172.16.42.1); never run it from a pmOS
# booted from userdata (refused: the partition has holders).
# Tests: WRITE_USERDATA_USBSH replaces `python3 tools/usbsh.py`, WRITE_USERDATA_POLL the 5 s poll.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tools=$root/tools
dry=0 image="" expect="" pit=$root/build/gts7xl.pit disk=sda partname=userdata
host=172.16.42.1 local_ip=172.16.42.2 notes=$root/NOTES.md
confirm_word=ERASE-USERDATA

while [ $# -gt 0 ]; do
	case "$1" in
	--dry-run) dry=1 ;;
	--image) image=$2; shift ;;
	--expect-sha256) expect=$2; shift ;;
	--pit) pit=$2; shift ;;
	--disk) disk=$2; shift ;;
	--host) host=$2; shift ;;
	--local-ip) local_ip=$2; shift ;;
	--notes) notes=$2; shift ;;
	-h|--help) sed -n '2,31p' "$0"; exit 0 ;;
	*) echo "write-userdata.sh: unknown argument $1" >&2; exit 2 ;;
	esac
	shift
done

die() { echo "write-userdata.sh: $*" >&2; exit 1; }
step() { echo "== $*"; }
[ -n "$image" ] || die "--image is required"
[ -f "$image" ] || die "missing image $image"
[[ "$disk" =~ ^sd[a-z]$ ]] || die "--disk must look like sda"
[[ "$host" =~ ^[0-9.]+$ && "$local_ip" =~ ^[0-9.]+$ ]] || die "--host/--local-ip must be IPv4 addresses"

if [ -n "${WRITE_USERDATA_USBSH:-}" ]; then
	read -r -a usbsh_cmd <<< "$WRITE_USERDATA_USBSH"
else
	usbsh_cmd=(python3 "$tools/usbsh.py")
fi
usbsh() { "${usbsh_cmd[@]}" --host "$host" --local-ip "$local_ip" "$@"; }

# ---- the image -------------------------------------------------------------------
step "image"
img_size=$(stat -L -c %s "$image")
[ "$img_size" -gt 0 ] || die "empty image"
[ "$(head -c 8 "$image" | od -An -c | tr -d ' ')" != "ANDROID!" ] || die "$image is a boot image"
sparse_magic=$(od -An -tx4 -N4 "$image" | tr -d ' ')
[ "$sparse_magic" != "ed26ff3a" ] || die "$image is an Android sparse image; use --no-sparse"
hex8() { dd if="$image" bs=1 skip="$1" count=8 status=none | od -An -tx1 | tr -d ' \n'; }
gpt=4546492050415254	# "EFI PART"
[ "$(hex8 4096)" = "$gpt" ] ||
	die "$image has no GPT header at byte 4096 (needs --sector-size 4096)"
[ "$(hex8 512)" != "$gpt" ] ||
	die "$image has a GPT header at byte 512 (512-byte sectors: the initramfs would not find it)"
img_sha=$(sha256sum "$image" | cut -d' ' -f1)
if [ -n "$expect" ] && [ "$img_sha" != "${expect,,}" ]; then
	die "image sha256 $img_sha is not the expected $expect"
fi
echo "   $image: $img_size bytes, sha256 $img_sha"

# ---- PIT ---------------------------------------------------------------------------
pit_off="" pit_cnt=""
if [ -f "$pit" ]; then
	read -r pit_off pit_cnt < <(awk '
		/^--- Entry/ { off = ""; cnt = "" }
		/^Partition Block Size\/Offset:/ { off = $NF }
		/^Partition Block Count:/ { cnt = $NF }
		/^Partition Name: USERDATA$/ { print off, cnt; exit }' "$pit")
	[ -n "$pit_off" ] || die "no USERDATA entry in $pit"
	echo "   PIT: USERDATA at block $pit_off, count $pit_cnt"
else
	echo "   PIT: $pit absent, start/size not cross-checked"
fi

# ---- the target, read-only ---------------------------------------------------------
resolve_cmd=': wu-resolve; n=0; for u in /sys/class/block/*/uevent; do grep -qx "PARTNAME='$partname'" "$u" || continue; d=${u%/uevent}; b=${d##*/}; p=$(basename "$(dirname "$(readlink -f "$d")")"); n=$((n+1)); echo "dev=$b parent=$p size=$(cat "$d/size") start=$(cat "$d/start") ro=$(cat "$d/ro") lbs=$(cat "/sys/block/$p/queue/logical_block_size") holders=$(ls "$d/holders" | wc -l) used=$(cat /proc/mounts /proc/swaps | grep -c "^/dev/$b[[:space:]]")"; done; echo "count=$n"'

resolve() {
	local out line kv k v
	out=$(usbsh --timeout 60 run "$resolve_cmd") || die "cannot read the partitions on $host (debug shell up?)"
	t_count="" t_dev="" t_parent="" t_size="" t_start="" t_ro="" t_lbs="" t_holders="" t_used=""
	while IFS= read -r line; do
		case "$line" in
		count=*) t_count=${line#count=} ;;
		dev=*)
			for kv in $line; do
				k=${kv%%=*} v=${kv#*=}
				case "$k" in dev|parent|size|start|ro|lbs|holders|used) printf -v "t_$k" '%s' "$v" ;; esac
			done ;;
		esac
	done <<< "$out"
	[ "$t_count" = 1 ] || die "expected exactly one PARTNAME=$partname partition, found '${t_count:-?}'"
	[[ "$t_dev" =~ ^${disk}[0-9]+$ ]] || die "target '$t_dev' is not a partition of $disk"
	[ "$t_parent" = "$disk" ] || die "target $t_dev sits on '$t_parent', expected $disk"
	for v in "$t_size" "$t_start" "$t_lbs" "$t_holders" "$t_used" "$t_ro"; do
		[[ "$v" =~ ^[0-9]+$ ]] || die "unreadable values for $t_dev: $out"
	done
	t_bytes=$((t_size * 512)) t_start_bytes=$((t_start * 512))
	[ "$t_ro" = 0 ] || die "$t_dev is read-only"
	[ "$t_used" = 0 ] || die "$t_dev is mounted or used as swap"
	[ "$t_holders" = 0 ] || die "$t_dev has holders (loop/dm): is pmOS running from it?"
	[ "$t_lbs" = 4096 ] || die "$disk has $t_lbs-byte blocks, the image is built for 4096"
	[ $((img_size % t_lbs)) = 0 ] || die "image size $img_size is not a multiple of $t_lbs"
	[ "$t_bytes" -ge "$img_size" ] || die "$t_dev is $t_bytes bytes, smaller than the image ($img_size)"
	if [ -n "$pit_off" ]; then
		[ "$t_start_bytes" = $((pit_off * t_lbs)) ] ||
			die "$t_dev starts at byte $t_start_bytes, the PIT USERDATA at $((pit_off * t_lbs))"
		if [ -n "$pit_cnt" ] && [ "$pit_cnt" != 0 ]; then
			[ "$t_bytes" = $((pit_cnt * t_lbs)) ] ||
				die "$t_dev is $t_bytes bytes, the PIT USERDATA $((pit_cnt * t_lbs))"
		fi
	fi
}

step "target on $host (read-only)"
resolve
tools_out=$(usbsh --timeout 60 run ': wu-tools; for t in wget dd sha256sum setsid; do command -v $t >/dev/null || echo missing=$t; done; dd --help 2>&1 | grep -q count_bytes || echo missing=dd-count_bytes; (set -o pipefail) 2>/dev/null || echo missing=pipefail; echo tools=checked') ||
	die "cannot run commands on $host"
grep -q '^tools=checked' <<< "$tools_out" || die "tool check gave no answer: $tools_out"
! grep -q '^missing=' <<< "$tools_out" || die "the tablet lacks: $(grep '^missing=' <<< "$tools_out" | tr '\n' ' ')"
dev=$t_dev bytes=$t_bytes start_bytes=$t_start_bytes

cat <<EOF
== plan
   image:   $image
            $img_size bytes ($((img_size >> 20)) MiB), sha256 $img_sha
   target:  /dev/$dev on $host (PARTNAME=$partname, disk $disk, $t_lbs-byte blocks)
            start byte $start_bytes, $bytes bytes ($((bytes >> 30)) GiB)${pit_off:+, PIT start matches}
   write:   wget -O - http://$local_ip:<port>/f | dd of=/dev/$dev bs=4M conv=fsync
   check:   read back $img_size bytes of /dev/$dev, sha256 must be $img_sha
   effect:  the first $((img_size >> 20)) MiB of userdata are replaced: One UI's data is gone
            (the rest of the partition keeps old encrypted bytes; pmOS grows into it)
EOF

if [ "$dry" = 1 ]; then
	echo "== dry run: nothing written"
	exit 0
fi

printf 'Type %s to write /dev/%s: ' "$confirm_word" "$dev"
IFS= read -r answer || answer=""
[ "$answer" = "$confirm_word" ] || die "not confirmed, nothing written"

# Same partition as in the plan?
step "target again"
resolve
[ "$t_dev" = "$dev" ] && [ "$t_bytes" = "$bytes" ] && [ "$t_start_bytes" = "$start_bytes" ] ||
	die "the target changed since the plan ($t_dev $t_bytes $t_start_bytes), nothing written"

log_notes() {	# $1: result line
	{
		echo
		echo "## $(date -Iseconds) userdata write"
		echo "- image: \`$(basename "$image")\`, $img_size bytes, sha256 $img_sha"
		echo "- target: /dev/$dev (PARTNAME=$partname), start byte $start_bytes, $bytes bytes"
		echo "- $1"
	} >> "$notes"
}

srv_out=$(mktemp)
srv_pid=""
cleanup() { [ -n "$srv_pid" ] && kill "$srv_pid" 2>/dev/null; rm -f "$srv_out"; }
trap cleanup EXIT
python3 "$tools/serve_file.py" "$image" "$local_ip" > "$srv_out" &
srv_pid=$!
port=""
for _ in $(seq 1 50); do
	port=$(sed -n 's/^PORT \([0-9][0-9]*\)$/\1/p' "$srv_out")
	[ -n "$port" ] && break
	kill -0 "$srv_pid" 2>/dev/null || break
	sleep 0.1
done
[ -n "$port" ] || die "the HTTP server did not start on $local_ip"

step "write /dev/$dev (detached on the tablet, polled)"
write_cmd=": wu-write; rm -f /tmp/wu.rc /tmp/wu.err; ( trap '' HUP; exec setsid sh -c 'set -o pipefail; wget -q -O - http://$local_ip:$port/f | dd of=/dev/$dev bs=4M conv=fsync 2>/tmp/wu.err; echo \$? > /tmp/wu.rc' ) </dev/null >/dev/null 2>&1 & true"
usbsh --timeout 60 run "$write_cmd" > /dev/null || die "could not start the write"
# At least 30 min, or 1 MB/s for the whole image.
deadline=$(( $(date +%s) + (img_size / 1000000 > 1800 ? img_size / 1000000 : 1800) ))
rc="" written=""
while :; do
	sleep "${WRITE_USERDATA_POLL:-5}"
	poll=$(usbsh --timeout 60 run ': wu-poll; if [ -e /tmp/wu.rc ]; then echo rc=$(cat /tmp/wu.rc); sed -n "s/^\([0-9][0-9]*\) bytes.*/written=\1/p" /tmp/wu.err; else echo rc=running; fi') || {
		echo "   (poll failed, retrying)"; poll="rc=running"; }
	rc=$(sed -n 's/^rc=//p' <<< "$poll" | head -n1)
	[ "$rc" != running ] && [ -n "$rc" ] && break
	[ "$(date +%s)" -lt "$deadline" ] || { log_notes "result: TIMEOUT, write still running or lost"; die "write timed out; check /tmp/wu.err on the tablet"; }
done
written=$(sed -n 's/^written=//p' <<< "$poll" | head -n1)
if [ "$rc" != 0 ]; then
	log_notes "result: WRITE FAILED (rc $rc, ${written:-?} bytes); userdata is partly overwritten"
	die "write failed (rc $rc); userdata is partly overwritten, see /tmp/wu.err on the tablet"
fi
if [ "$written" != "$img_size" ]; then
	log_notes "result: SHORT WRITE (${written:-?} of $img_size bytes)"
	die "dd reports ${written:-?} bytes written, expected $img_size"
fi
echo "   dd: $written bytes"

step "read back $img_size bytes of /dev/$dev"
rb=$(usbsh --timeout 3600 run ": wu-readback; sync; echo 3 > /proc/sys/vm/drop_caches; dd if=/dev/$dev bs=4M iflag=count_bytes count=$img_size 2>/dev/null | sha256sum") ||
	die "read back failed"
rb_sha=$(awk 'NF { print $1; exit }' <<< "$rb")
if [ "$rb_sha" != "$img_sha" ]; then
	log_notes "result: READBACK MISMATCH, partition sha256 ${rb_sha:-?}"
	echo "write-userdata.sh: read back sha256 ${rb_sha:-?} != image $img_sha" >&2
	exit 3
fi
log_notes "result: OK, $written bytes written, read back sha256 matches"
echo "== OK: /dev/$dev holds $image (sha256 $img_sha); logged to $notes"
