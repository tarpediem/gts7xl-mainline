#!/usr/bin/env bash
# kexec test of the USB dual role (r25): dwc3 role switch, automatic role from the USB-C block's
# attach state (read only), manual role switch and back, gadget still bound. VBUS output (OTG
# boost) is NOT enabled here. Then reboot to the BOOT kernel. Nothing is flashed.
#
#   tools/otg-role-test.sh APK       (pmbootstrap linux-samsung-gts7xl-<rel>.apk: Image + DTB)
#
# Env: HOST (default 192.168.100.166), BOOT_REL (default 7.3.4-r24), HANDS=1 (wait for the owner:
# host-mode tests with a device plugged in, see the prompts; boost only if BOOST=1).
set -uo pipefail
SP=${SP:-/tmp/claude-1000/-home-tarpediem-Work-samsung-gts7xl-mainline/8218a82d-737f-4327-a27f-5970ee3d04e8/scratchpad}
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
APK=$1
REL=$(basename "$APK" .apk); REL=${REL#linux-samsung-gts7xl-}
BOOT_REL=${BOOT_REL:-7.3.4-r24}
H=${HOST:-192.168.100.166}
OUT=$ROOT/build/otg-role-test-$(date +%H%M%S); mkdir -p "$OUT"
O=(-i "$HOME/.ssh/gts7xl_ed25519" -o IdentitiesOnly=yes -o HostKeyAlias=172.16.42.1 -o ConnectTimeout=5)
s() { ssh "${O[@]}" "tarpediem@$H" "$@"; }
r() { ssh "${O[@]}" "tarpediem@$H" "sudo -n sh -c $(printf '%q' "$1")"; }
log() { echo "[$(date +%T)] $*" | tee -a "$OUT/run.log"; }
wait_up() { local i; for ((i=0;i<$1;i+=5)); do s true 2>/dev/null && return 0; sleep 5; done; return 1; }
wait_down() { local i; for ((i=0;i<$1;i+=2)); do s true 2>/dev/null || return 0; sleep 2; done; return 1; }
C=/sys/class/power_supply/max77705-charger; B=/sys/class/power_supply/max170xx_battery
ROLE='$(ls -d /sys/class/usb_role/*-role-switch | head -1)/role'
STATE="echo \$(date +%T) role=\$(cat $ROLE) auto=\$(cat $C/device/usb_role_auto) vbus=\"\$(cat $C/device/otg_vbus)\" CCST0=\$(i2cget -f -y 0 0x25 0x0a) BC=\$(i2cget -f -y 0 0x25 0x08) CNFG00=\$(i2cget -f -y 0 0x69 0xb7) CNFG02=\$(i2cget -f -y 0 0x69 0xb9) DTLS00=\$(i2cget -f -y 0 0x69 0xb3) DTLS02=\$(i2cget -f -y 0 0x69 0xb5) udc=\$(cat /sys/class/udc/a600000.usb/state 2>/dev/null || echo none) gadget=\$(cat /sys/kernel/config/usb_gadget/g1/UDC) usb0=\$(cat /sys/class/net/usb0/operstate 2>/dev/null || echo none) type=\$(grep -o '\[[A-Z_]*\]' $C/usb_type) st=\$(cat $C/status) Ibat=\$(cat $B/current_now) cap=\$(cat $B/capacity) T=\$(cat $C/temp)"

K=$OUT/k; mkdir -p "$K"; tar xzf "$APK" -C "$K" boot 2>/dev/null
[ -f "$K/boot/vmlinuz" ] || { echo "no kernel in $APK" >&2; exit 1; }
exec 9>"$SP/tablet.lock"; flock -w 3600 9 || exit 1
echo "battery agent: kexec $REL (USB dual role test), then reboot to $BOOT_REL ($(date +%T))" > "$SP/tablet.owner"
log "lock taken, tablet at $H"
if [ "${RESUME:-0}" != 1 ]; then
s 'uname -r' | grep -qx "$BOOT_REL" || { log "not on $BOOT_REL"; : > "$SP/tablet.owner"; exit 1; }
r "test -d /usr/lib/modules/$REL" || { log "no /usr/lib/modules/$REL on the tablet"; : > "$SP/tablet.owner"; exit 1; }
r 'cat /sys/firmware/fdt' > "$OUT/running.fdt"
python3 "$ROOT/tools/kexec_dtb.py" --new "$K/boot/dtbs/qcom/sm8250-samsung-gts7xl.dtb" --running "$OUT/running.fdt" -o "$OUT/kexec.dtb" || exit 1
zcat "$K/boot/vmlinuz" > "$OUT/Image"
scp -q "${O[@]}" "$OUT/Image" "$OUT/kexec.dtb" "tarpediem@$H:/tmp/" && scp -q "${O[@]}" "$(realpath "$ROOT/build/initramfs")" "tarpediem@$H:/tmp/initramfs-test"
r 'kexec -c -l /tmp/Image --dtb=/tmp/kexec.dtb --initrd=/tmp/initramfs-test --reuse-cmdline 2>&1 | grep -v kcore; cat /sys/kernel/kexec_loaded' | tee -a "$OUT/run.log"
log "systemctl kexec"; r 'systemd-run --on-active=2 systemctl kexec' > /dev/null 2>&1
wait_down 60
fi
wait_up 400 || { log "NOT BACK: owner needed, lock kept"; exit 2; }
log "back"; sleep 40
s "uname -r" | grep -qx "$REL" || { log "not on $REL"; exit 2; }

r "journalctl -b -k | grep -E 'max77705-charger|dwc3|role|xhci' | cut -c1-200 | tail -30
journalctl -b -k | grep -c 'BTF: -22'; systemctl --failed --no-legend
nmcli -t -f DEVICE,STATE dev | grep wlp; bluetoothctl list" 2>&1 | tee -a "$OUT/checks.txt"
r "$STATE" | tee -a "$OUT/state.log"

log "manual: host"
r "echo host > $ROLE"; sleep 6
r "$STATE; ls /sys/bus/usb/devices; journalctl -b -k --since -20s | grep -iE 'xhci|dwc3|usb' | cut -c1-160 | tail -12" | tee -a "$OUT/state.log"
sleep 5; r "$STATE" | tee -a "$OUT/state.log"   # the automatic role must not undo a manual one
log "manual: device"
r "echo device > $ROLE"; sleep 8
r "$STATE; journalctl -b -k --since -20s | grep -iE 'xhci|dwc3|gadget|udc' | cut -c1-160 | tail -12" | tee -a "$OUT/state.log"

if [ "${HANDS:-0}" = 1 ]; then
	echo; echo "=== Owner: unplug the charger, plug the OTG adapter with the device now. Enter when done. ==="
	read -r _
	for i in 1 2 3 4 5; do r "$STATE" | tee -a "$OUT/hands.log"; sleep 2; done
	r 'lsusb; lsusb -t' | tee -a "$OUT/hands.log"
	if [ "${BOOST:-0}" = 1 ]; then
		log "VBUS output: auto"
		r "echo auto > $C/device/otg_vbus"
		for i in $(seq 1 30); do r "$STATE" | tee -a "$OUT/hands.log"; sleep 2; done
		r 'lsusb; lsusb -t; journalctl -b -k | grep -E "VBUS output|USB role" | tail -10' | tee -a "$OUT/hands.log"
		echo "=== Owner: unplug the OTG adapter (VBUS must go off). Enter when done. ==="; read -r _
		for i in 1 2 3; do r "$STATE" | tee -a "$OUT/hands.log"; sleep 2; done
		echo "=== Owner: plug the wall charger back (charging must resume). Enter when done. ==="; read -r _
		for i in 1 2 3 4 5 6; do r "$STATE" | tee -a "$OUT/hands.log"; sleep 5; done
		r "echo off > $C/device/otg_vbus"
		r 'journalctl -b -k | grep -E "VBUS output|USB role|charging" | tail -20' | tee -a "$OUT/hands.log"
	fi
fi

log "reboot to BOOT"; r 'systemd-run --on-active=2 systemctl reboot' > /dev/null 2>&1
wait_down 60; wait_up 400 || { log "not back after reboot: owner needed, lock kept"; exit 2; }
sleep 40
r "uname -r; systemctl --failed --no-legend; nmcli -t -f DEVICE,STATE dev | grep wlp; cat $C/status $B/capacity" 2>&1 | tee -a "$OUT/checks-back.txt"
: > "$SP/tablet.owner"; log "lock released ($OUT)"
