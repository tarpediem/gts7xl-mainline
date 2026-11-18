#!/usr/bin/env bash
# kexec test of the per-cable charge current (r23: 1.5 A on a detected wall charger, DCP), over
# Wi-Fi with the tablet on its wall charger, then reboot to the BOOT kernel. Nothing is flashed.
# The kernel package (linux-gts7xl) must already be installed on the tablet (module dir).
#
#   tools/charge-dcp-test.sh APK      (pmbootstrap linux-samsung-gts7xl-<rel>.apk: Image + DTB)
#
# Env: HOST (tablet IP, default: poubelle.local over mDNS), SOAK_SECS (default 600),
#      BOOT_REL (kernel expected after the final reboot, default 7.3.4-r22),
#      RESUME=1 (already kexec'd into the test kernel: start at the checks).
# The Wi-Fi MAC (so the DHCP address) may change at each boot: without HOST the tablet is found by mDNS.
# Stops early (inhibit, reboot) if the battery reaches 40 C. Runs as the user; root on the
# tablet through its passwordless sudo.
set -uo pipefail
SP=${SP:-/tmp/claude-1000/-home-tarpediem-Work-samsung-gts7xl-mainline/8218a82d-737f-4327-a27f-5970ee3d04e8/scratchpad}
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
APK=$1
REL=$(basename "$APK" .apk); REL=${REL#linux-samsung-gts7xl-}
SOAK_SECS=${SOAK_SECS:-600}
BOOT_REL=${BOOT_REL:-7.3.4-r22}
OUT=$ROOT/build/charge-dcp-test-$(date +%H%M%S); mkdir -p "$OUT"
O=(-i "$HOME/.ssh/gts7xl_ed25519" -o IdentitiesOnly=yes -o HostKeyAlias=172.16.42.1 -o ConnectTimeout=5)
find_host() { [ -n "${HOST_FIXED:-}" ] && { echo "$HOST_FIXED"; return; }
	avahi-resolve -4 -n poubelle.local 2>/dev/null | awk '{print $2}'; }
HOST_FIXED=${HOST:-}
H=$(find_host)
s() { ssh "${O[@]}" "tarpediem@$H" "$@"; }
r() { ssh "${O[@]}" "tarpediem@$H" "sudo -n sh -c $(printf '%q' "$1")"; }
log() { echo "[$(date +%T)] $*" | tee -a "$OUT/run.log"; }
wait_up() { local i; for ((i=0;i<$1;i+=5)); do H=$(find_host); [ -n "$H" ] && s true 2>/dev/null && return 0; sleep 5; done; return 1; }
wait_down() { local i; for ((i=0;i<$1;i+=2)); do s true 2>/dev/null || return 0; sleep 2; done; return 1; }
C=/sys/class/power_supply/max77705-charger; B=/sys/class/power_supply/max170xx_battery
SAMPLE="echo \$(date +%T) type=\$(grep -o '\[[A-Z_]*\]' $C/usb_type) st=\$(cat $C/status) cc=\$(cat $C/constant_charge_current) ilim=\$(cat $C/input_current_limit) CNFG02=\$(i2cget -f -y 0 0x69 0xb9) CNFG00=\$(i2cget -f -y 0 0x69 0xb7) DTLS01=\$(i2cget -f -y 0 0x69 0xb4) Ibat=\$(cat $B/current_now) Iavg=\$(cat $B/current_avg) V=\$(cat $B/voltage_now) cap=\$(cat $B/capacity) T=\$(cat $C/temp) health=\$(cat $C/health)"

K=$OUT/k; mkdir -p "$K"; tar xzf "$APK" -C "$K" boot 2>/dev/null
[ -f "$K/boot/vmlinuz" ] || { echo "no kernel in $APK" >&2; exit 1; }
[ -n "$H" ] || { echo "tablet not found" >&2; exit 1; }
exec 9>"$SP/tablet.lock"; flock -w 3600 9 || exit 1
echo "battery agent: kexec $REL (1.5 A DCP charge current test), then reboot to $BOOT_REL ($(date +%T))" > "$SP/tablet.owner"
log "lock taken, tablet at $H"
if [ "${RESUME:-0}" != 1 ]; then
s 'uname -r' | grep -qx "$BOOT_REL" || { log "not on $BOOT_REL"; : > "$SP/tablet.owner"; exit 1; }
r "test -d /usr/lib/modules/$REL" || { log "no /usr/lib/modules/$REL on the tablet"; : > "$SP/tablet.owner"; exit 1; }
cap=$(s "cat $B/capacity"); log "before: $(r "$SAMPLE")"
[ "${cap:-0}" -ge 10 ] || { log "battery $cap % < 10: test skipped"; : > "$SP/tablet.owner"; exit 3; }
s "grep -q '\[DCP\]' $C/usb_type" || { log "not on a DCP (wall charger): test skipped"; : > "$SP/tablet.owner"; exit 3; }

r 'cat /sys/firmware/fdt' > "$OUT/running.fdt"
python3 "$ROOT/tools/kexec_dtb.py" --new "$K/boot/dtbs/qcom/sm8250-samsung-gts7xl.dtb" --running "$OUT/running.fdt" -o "$OUT/kexec.dtb" || exit 1
zcat "$K/boot/vmlinuz" > "$OUT/Image"
scp -q "${O[@]}" "$OUT/Image" "$OUT/kexec.dtb" "tarpediem@$H:/tmp/" && scp -q "${O[@]}" "$(realpath "$ROOT/build/initramfs")" "tarpediem@$H:/tmp/initramfs-test"
r 'kexec -c -l /tmp/Image --dtb=/tmp/kexec.dtb --initrd=/tmp/initramfs-test --reuse-cmdline 2>&1 | grep -v kcore; cat /sys/kernel/kexec_loaded' | tee -a "$OUT/run.log"
log "systemctl kexec"; r 'systemd-run --on-active=2 systemctl kexec' > /dev/null 2>&1
wait_down 60
fi
wait_up 400 || { log "NOT BACK: owner needed, lock kept"; exit 2; }
log "back at $H"; sleep 40
s "uname -r" | grep -qx "$REL" || { log "not on $REL"; exit 2; }

r "uname -r; journalctl -b -k | grep -E 'safety monitor|charge current|input limit' | cut -c1-200
journalctl -b -k | grep -c 'BTF: -22'; systemctl --failed --no-legend
nmcli -t -f DEVICE,STATE dev | grep wlp; bluetoothctl list" 2>&1 | tee -a "$OUT/checks.txt"

# Soak, screen off (backlight 0, restored after)
bl=$(r 'cat /sys/class/backlight/*/brightness'); r 'for b in /sys/class/backlight/*; do echo 0 > $b/brightness; done'
log "soak ${SOAK_SECS}s, screen off (backlight was $bl)"
end=$((SECONDS + SOAK_SECS)); hot=0
while [ $SECONDS -lt $end ]; do
	line=$(r "$SAMPLE"); echo "$line" | tee -a "$OUT/soak.log"
	t=$(echo "$line" | sed -n 's/.* T=\([0-9-]*\).*/\1/p')
	[ -n "$t" ] && [ "$t" -ge 400 ] && { hot=1; log "battery at $t (0.1 C): stopping"; break; }
	sleep 15
done
r "for b in /sys/class/backlight/*; do echo $bl > \$b/brightness; done"

if [ $hot = 0 ]; then
	log "inhibit-charge 60 s"
	r "echo inhibit-charge > $C/charge_behaviour"
	for i in 1 2 3 4 5 6; do sleep 10; r "$SAMPLE" | tee -a "$OUT/inhibit.log"; done
	r "echo auto > $C/charge_behaviour"
	for i in 1 2 3; do sleep 10; r "$SAMPLE" | tee -a "$OUT/inhibit.log"; done
fi

log "reboot to BOOT"; r 'systemd-run --on-active=2 systemctl reboot' > /dev/null 2>&1
wait_down 60; wait_up 400 || { log "not back after reboot: owner needed, lock kept"; exit 2; }
sleep 40
r "uname -r; systemctl --failed --no-legend; nmcli -t -f DEVICE,STATE dev | grep wlp; bluetoothctl list; $SAMPLE" 2>&1 | tee -a "$OUT/checks-back.txt"
: > "$SP/tablet.owner"; log "lock released ($OUT)"
