#!/usr/bin/env bash
# E1-E3 of docs/max77705-usbc-pd-design.md (owner-approved, owner present for E3):
#   E1  mailbox READ commands: CCCTRL1/2/3, CTRL1, CTRL3 (configuration dump)
#   E2  SAMSUNG_FACTORY_TEST (0x54) = 0x00: firmware auto VBUS off (stock boot state)
#   E3  SET_ALTERNATEMODE (0x55) = 0x01 (source capability), later 0x03 (+ VDM)
# Runs on the r25 kernel (kexec from BOOT; dual role, VBUS output OFF and never enabled here),
# then reboots to BOOT and re-reads the configuration (does the firmware state survive a reboot?).
# Mailbox (vendor max77705_usbc.c): write [0x21]=opcode,[0x22..]=data, then [0x41]=0x00; answer at
# 0x51 (echo of the opcode + data). Charger registers are only read. Nothing is flashed.
#
#   tools/usbc-mailbox-test.sh APK     (r25 apk); owner steps are read from stdin (one line each)
# Env: HOST (default 192.168.100.166), BOOT_REL (default 7.3.4-r24).
set -uo pipefail
SP=${SP:-/tmp/claude-1000/-home-tarpediem-Work-samsung-gts7xl-mainline/8218a82d-737f-4327-a27f-5970ee3d04e8/scratchpad}
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
APK=$1
REL=$(basename "$APK" .apk); REL=${REL#linux-samsung-gts7xl-}
BOOT_REL=${BOOT_REL:-7.3.4-r24}
H=${HOST:-192.168.100.166}
OUT=$ROOT/build/usbc-mailbox-test-$(date +%H%M%S); mkdir -p "$OUT"
O=(-i "$HOME/.ssh/gts7xl_ed25519" -o IdentitiesOnly=yes -o HostKeyAlias=172.16.42.1 -o ConnectTimeout=5)
s() { ssh "${O[@]}" "tarpediem@$H" "$@"; }
r() { ssh "${O[@]}" "tarpediem@$H" "sudo -n sh -c $(printf '%q' "$1")"; }
log() { echo "[$(date +%T)] $*" | tee -a "$OUT/run.log"; }
owner() { echo; echo "=== OWNER: $* -- then a line on stdin ==="; read -r ans; log "owner: ${ans:-done}"; }
wait_up() { local i; for ((i=0;i<$1;i+=5)); do s true 2>/dev/null && return 0; sleep 5; done; return 1; }
wait_down() { local i; for ((i=0;i<$1;i+=2)); do s true 2>/dev/null || return 0; sleep 2; done; return 1; }

# mailbox helpers, run on the tablet as root (i2c bus 0 = i2c@980000)
MB='mb_cmd() { i2ctransfer -f -y 0 w$(( $# + 1 ))@0x25 0x21 "$@" && i2ctransfer -f -y 0 w2@0x25 0x41 0x00; }
mb_ans() { sleep 0.3; i2ctransfer -f -y 0 w1@0x25 0x51 r10; }
mb_read() { mb_cmd "$1"; echo "$1 -> $(mb_ans)"; }'
E1="$MB
for o in 0x0b 0x0d 0x0f 0x05 0x09; do mb_read \$o; done"
# VBUS must stay off: BC_STATUS bit 7, charger CHG_INT_OK bit 6 (CHGIN_OK), DTLS_00 bits 6:5,
# CNFG_00 bit 3 (boost); plus the attach state and our role / VBUS-output policy
ST='echo "$(date +%T) CCST0=$(i2cget -f -y 0 0x25 0x0a) CCST1=$(i2cget -f -y 0 0x25 0x0b) BC=$(i2cget -f -y 0 0x25 0x08) STAT2=$(i2cget -f -y 0 0x25 0x07) PD1=$(i2cget -f -y 0 0x25 0x0d) INTOK=$(i2cget -f -y 0 0x69 0xb2) DTLS00=$(i2cget -f -y 0 0x69 0xb3) CNFG00=$(i2cget -f -y 0 0x69 0xb7) role=$(cat /sys/class/usb_role/*-role-switch/role) vbus=\"$(cat /sys/class/power_supply/max77705-charger/device/otg_vbus)\" st=$(cat /sys/class/power_supply/max77705-charger/status) cap=$(cat /sys/class/power_supply/max170xx_battery/capacity)"'
# returns non-zero if VBUS/boost is seen
VB='bc=$(i2cget -f -y 0 0x25 0x08); ok=$(i2cget -f -y 0 0x69 0xb2); d0=$(i2cget -f -y 0 0x69 0xb3); c0=$(i2cget -f -y 0 0x69 0xb7)
[ $((bc & 0x80)) = 0 ] && [ $((ok & 0x40)) = 0 ] && [ $(((d0 >> 5) & 3)) = 0 ] && [ $((c0 & 0x08)) = 0 ]'
watch_vbus() {  # $1 = seconds; ABORT on VBUS
	local i
	for ((i=0;i<$1;i++)); do
		r "$ST" | tee -a "$OUT/state.log"
		if ! r "$VB"; then
			log "ABORT: VBUS or boost seen with nothing that should supply it"
			echo "=== OWNER: UNPLUG THE OTG ADAPTER NOW ==="
			r "$MB
mb_cmd 0x54 0x00; mb_ans" | tee -a "$OUT/run.log"
			return 1
		fi
		sleep 1
	done
}

K=$OUT/k; mkdir -p "$K"; tar xzf "$APK" -C "$K" boot 2>/dev/null
[ -f "$K/boot/vmlinuz" ] || { echo "no kernel in $APK" >&2; exit 1; }
exec 9>"$SP/tablet.lock"; flock -w 3600 9 || exit 1
echo "battery agent: USB-C mailbox E1-E3 on $REL (owner present), then reboot to $BOOT_REL ($(date +%T))" > "$SP/tablet.owner"
log "lock taken"
s 'uname -r' | grep -qx "$BOOT_REL" || { log "not on $BOOT_REL"; : > "$SP/tablet.owner"; exit 1; }
r "test -d /usr/lib/modules/$REL" || { log "no /usr/lib/modules/$REL"; : > "$SP/tablet.owner"; exit 1; }
cap=$(s 'cat /sys/class/power_supply/max170xx_battery/capacity'); [ "${cap:-0}" -ge 20 ] || { log "battery $cap %"; : > "$SP/tablet.owner"; exit 3; }

owner "nothing plugged into the USB-C port (no charger, no adapter)"
log "E1 on $BOOT_REL (before anything is written)"; r "$E1" | tee -a "$OUT/e1-boot-before.txt"

r 'cat /sys/firmware/fdt' > "$OUT/running.fdt"
python3 "$ROOT/tools/kexec_dtb.py" --new "$K/boot/dtbs/qcom/sm8250-samsung-gts7xl.dtb" --running "$OUT/running.fdt" -o "$OUT/kexec.dtb" || exit 1
zcat "$K/boot/vmlinuz" > "$OUT/Image"
scp -q "${O[@]}" "$OUT/Image" "$OUT/kexec.dtb" "tarpediem@$H:/tmp/" && scp -q "${O[@]}" "$(realpath "$ROOT/build/initramfs")" "tarpediem@$H:/tmp/initramfs-test"
r 'kexec -c -l /tmp/Image --dtb=/tmp/kexec.dtb --initrd=/tmp/initramfs-test --reuse-cmdline 2>&1 | grep -v kcore; cat /sys/kernel/kexec_loaded' | tee -a "$OUT/run.log"
log "systemctl kexec"; r 'systemd-run --on-active=2 systemctl kexec' > /dev/null 2>&1
wait_down 60; wait_up 400 || { log "NOT BACK: owner needed, lock kept"; exit 2; }
log back; sleep 40
s 'uname -r' | grep -qx "$REL" || { log "not on $REL"; exit 2; }
r "$ST" | tee -a "$OUT/state.log"
r 'cat /sys/class/power_supply/max77705-charger/device/otg_vbus' | grep -q '^off' || { log "otg_vbus not off: stop"; exit 2; }

log "E1 on $REL"; r "$E1" | tee -a "$OUT/e1.txt"
log "E2: FACTORY_TEST 0x00 (firmware auto VBUS off)"
r "$MB
mb_cmd 0x54 0x00; echo \"0x54 -> \$(mb_ans)\"" | tee -a "$OUT/e2.txt"
watch_vbus 5 || exit 4
log "E3a: SET_ALTERNATEMODE 0x01"
r "$MB
mb_cmd 0x55 0x01; echo \"0x55 -> \$(mb_ans)\"" | tee -a "$OUT/e3.txt"
watch_vbus 10 || exit 4
r "$E1" | tee -a "$OUT/e1-after-e3a.txt"

owner "plug the OTG adapter WITH the USB keyboard into the USB-C port (no charger)"
watch_vbus 15 || exit 4
r 'journalctl -b -k --since -30s | grep -E "USB role|VBUS output|xhci|usb [0-9]" | tail -10' | tee -a "$OUT/run.log"
owner "unplug the OTG adapter"
watch_vbus 6 || exit 4

log "E3b: SET_ALTERNATEMODE 0x03 (source + VDM)"
r "$MB
mb_cmd 0x55 0x03; echo \"0x55 -> \$(mb_ans)\"" | tee -a "$OUT/e3.txt"
watch_vbus 6 || exit 4
owner "plug the OTG adapter WITH the keyboard again"
watch_vbus 15 || exit 4
owner "unplug the OTG adapter, then plug the WALL CHARGER"
for i in 1 2 3 4 5 6 7 8; do r "$ST" | tee -a "$OUT/state.log"; sleep 3; done
r 'cat /sys/class/power_supply/max77705-charger/usb_type /sys/class/power_supply/max77705-charger/input_current_limit; journalctl -b -k | grep -E "USB role|VBUS output|input limit|charge current" | tail -12' | tee -a "$OUT/run.log"

log "reboot to BOOT"; r 'systemd-run --on-active=2 systemctl reboot' > /dev/null 2>&1
wait_down 60; wait_up 400 || { log "not back after reboot: owner needed, lock kept"; exit 2; }
sleep 40
r "uname -r; systemctl --failed --no-legend; nmcli -t -f DEVICE,STATE dev | grep wlp1; $ST" | tee -a "$OUT/checks-back.txt"
log "E1 after the reboot (did the firmware keep E2/E3?)"; r "$E1" | tee -a "$OUT/e1-after-reboot.txt"
: > "$SP/tablet.owner"; log "lock released ($OUT)"
