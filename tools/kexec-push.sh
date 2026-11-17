#!/usr/bin/env bash
# Boot a new kernel on the gts7xl over USB, without flashing: kexec from the debug shell.
#
# usage: tools/kexec-push.sh [--dry-run] [--no-exec] [--force] [--host IP] [--local-ip IP]
#                            [--kernel FILE] [--dtb FILE] [--initramfs FILE]
#                            [--cmdline STR | --append STR]
#
#   --kernel     default build/vmlinuz (gzip Image from pmbootstrap export; sent decompressed)
#   --dtb        default build/dtbs/sm8250-samsung-gts7xl.dtb
#   --initramfs  default build/initramfs
#   --cmdline    full command line for the new kernel; default: the running one (--reuse-cmdline)
#   --append     added to the running command line (e.g. gts7xl.nomodules)
#   --no-exec    load only (kexec -l), do not jump; run `kexec -e` yourself
#   --force      skip the check that the RUNNING kernel can kexec (r12+, build #13+)
#   --dry-run    print every step, touch nothing (no connection to the tablet)
#
# The running kernel does the jump: up to r11 (#12) its machine_kexec() oopses under kCFI
# (fixed in linux-samsung-gts7xl r12). Boot an r12+ RECOVERY once before using this.
#
# Steps: pull /sys/firmware/fdt (memory layout from the ABL, via the shim) -> copy its
# /memory into the new DTB (tools/kexec_dtb.py) -> push Image, DTB, initramfs to /tmp/kx on
# the tablet (wget from a one-file HTTP server here) -> kexec -l -> kexec -e.
# The tablet must be in the pmOS debug shell (telnet 172.16.42.1). Nothing is flashed.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tools=$root/tools
dry=0 exec_=1 force=0 host=172.16.42.1 local_ip=172.16.42.2
kernel=$root/build/vmlinuz dtb=$root/build/dtbs/sm8250-samsung-gts7xl.dtb initramfs=$root/build/initramfs
cmdline="" append=""

while [ $# -gt 0 ]; do
	case "$1" in
	--dry-run) dry=1 ;;
	--no-exec) exec_=0 ;;
	--force) force=1 ;;
	--host) host=$2; shift ;;
	--local-ip) local_ip=$2; shift ;;
	--kernel) kernel=$2; shift ;;
	--dtb) dtb=$2; shift ;;
	--initramfs) initramfs=$2; shift ;;
	--cmdline) cmdline=$2; shift ;;
	--append) append=$2; shift ;;
	-h|--help) sed -n '2,25p' "$0"; exit 0 ;;
	*) echo "kexec-push.sh: unknown argument $1" >&2; exit 2 ;;
	esac
	shift
done
[ -n "$cmdline" ] && [ -n "$append" ] && { echo "kexec-push.sh: --cmdline and --append are exclusive" >&2; exit 2; }
for f in "$kernel" "$dtb" "$initramfs"; do
	[ -e "$f" ] || { echo "kexec-push.sh: missing $f" >&2; exit 1; }
done

usbsh() { python3 "$tools/usbsh.py" --host "$host" --local-ip "$local_ip" "$@"; }
step() { echo "== $*"; }
q() { printf "'%s'" "${1//\'/\'\\\'\'}"; }

if [ -n "$cmdline" ]; then
	cmdarg="--command-line=$(q "$cmdline")"
elif [ -n "$append" ]; then
	cmdarg="--reuse-cmdline --append=$(q "$append")"
else
	cmdarg="--reuse-cmdline"
fi
load="kexec -l /tmp/kx/Image --dtb=/tmp/kx/kexec.dtb --initrd=/tmp/kx/initramfs $cmdarg"
# Detached from the telnet session: a plain `&` job is killed when usbsh closes the
# connection. HUP is ignored from the fork on (inherited through exec, so there is no window
# before setsid takes effect), then setsid leaves the session. `& true`: ash rejects `&;`
# before usbsh's `; echo`.
jump="( trap '' HUP; exec setsid sh -c 'sleep 2; sync; exec kexec -e' ) </dev/null >/dev/null 2>&1 & true"
min_build=13     # first build with the machine_kexec() kCFI fix: linux-samsung-gts7xl r12

if [ "$dry" = 1 ]; then
	step "[dry-run] check: uname -v on $host is #$min_build or later (skip: --force)"
	step "[dry-run] pull $host:/sys/firmware/fdt -> WORK/running.fdt"
	step "[dry-run] tools/kexec_dtb.py --new $dtb --running WORK/running.fdt -o WORK/kexec.dtb"
	step "[dry-run] decompress $kernel -> WORK/Image"
	step "[dry-run] push WORK/Image WORK/kexec.dtb $initramfs -> $host:/tmp/kx/"
	step "[dry-run] run (timeout 300 s): $load"
	step "[dry-run] check: /sys/kernel/kexec_loaded = 1"
	[ "$exec_" = 1 ] && step "[dry-run] run: $jump"
	exit 0
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

if [ "$force" = 0 ]; then
	step "running kernel can kexec?"
	ver=$(usbsh run 'uname -v')
	n=$(printf '%s\n' "$ver" | sed -n 's/^#\([0-9][0-9]*\)-samsung-gts7xl.*/\1/p' | head -n1)
	if [ -z "$n" ] || [ "$n" -lt "$min_build" ]; then
		echo "kexec-push.sh: running kernel is '$ver'; builds before #$min_build oops in machine_kexec()" >&2
		echo "  (kCFI, fixed in r12). Boot an r12+ RECOVERY first, or --force." >&2
		exit 1
	fi
fi
step "pull the running DTB"
usbsh pull /sys/firmware/fdt "$work/running.fdt"
step "new DTB with the running /memory"
python3 "$tools/kexec_dtb.py" --new "$dtb" --running "$work/running.fdt" -o "$work/kexec.dtb"
step "kernel Image"
if gzip -t "$kernel" 2>/dev/null; then gzip -dc "$kernel" > "$work/Image"; else cp "$kernel" "$work/Image"; fi
step "push to /tmp/kx"
usbsh run "mkdir -p /tmp/kx && command -v kexec" > /dev/null || { echo "kexec-push.sh: no kexec on the tablet" >&2; exit 1; }
usbsh push "$work/Image" /tmp/kx/Image
usbsh push "$work/kexec.dtb" /tmp/kx/kexec.dtb
usbsh push "$initramfs" /tmp/kx/initramfs
step "kexec -l"
usbsh --timeout 300 run "$load"
[ "$(usbsh run 'cat /sys/kernel/kexec_loaded')" = 1 ] || { echo "kexec-push.sh: kexec_loaded is not 1" >&2; exit 1; }
if [ "$exec_" = 1 ]; then
	step "kexec -e (the USB link drops; wait for 172.16.42.1 to come back)"
	usbsh run "$jump"
else
	step "loaded; run 'kexec -e' on the tablet to jump"
fi
