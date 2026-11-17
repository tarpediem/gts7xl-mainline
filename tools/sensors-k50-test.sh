#!/usr/bin/env bash
# kexec test of the gts7xl-sensors kernel (pmaports gts7xl-sensors, release 7.3.4-r50): S Pen
# (wacom_w90xx), rear camera probe (rearcam DTB: S5K3M5 at the stock 19.2 MHz MCLK, no
# streaming), SLPI sensors and hall switches again; then reboot to the BOOT kernel.
# Nothing is flashed. Runs as the user; root on the tablet through its passwordless sudo.
#
# usage: tools/sensors-k50-test.sh [APK]   (default: newest linux-samsung-gts7xl-7.3.4-r50.apk)
set -uo pipefail
SP=${SP:-/tmp/claude-1000/-home-tarpediem-Work-samsung-gts7xl-mainline/8218a82d-737f-4327-a27f-5970ee3d04e8/scratchpad}
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
APK=${1:-$HOME/.local/var/pmbootstrap/packages/edge/aarch64/linux-samsung-gts7xl-7.3.4-r50.apk}
REL=7.3.4-r50
OUT=$ROOT/build/sensors-k50-test-$(date +%H%M%S); mkdir -p "$OUT"
O=(-i "$HOME/.ssh/gts7xl_ed25519" -o IdentitiesOnly=yes -o "UserKnownHostsFile=$SP/gts7xl_known_hosts" -o ConnectTimeout=5)
T=tarpediem@172.16.42.1
s() { ssh "${O[@]}" "$T" "$@"; }
r() { ssh "${O[@]}" "$T" "sudo -n sh -c $(printf '%q' "$1")"; }
log() { echo "[$(date +%T)] $*" | tee -a "$OUT/run.log"; }
wait_up() { local i; for ((i=0;i<$1;i+=5)); do s true 2>/dev/null && return 0; sleep 5; done; return 1; }
wait_down() { local i; for ((i=0;i<$1;i+=2)); do s true 2>/dev/null || return 0; sleep 2; done; return 1; }

K=$OUT/k; mkdir -p "$K"; tar xzf "$APK" -C "$K" boot usr/lib/modules 2>/dev/null
[ -d "$K/usr/lib/modules/$REL" ] || { echo "no $REL modules in $APK" >&2; exit 1; }
exec 9>"$SP/tablet.lock"; flock -w 3600 9 || exit 1
echo "sensors agent: kexec $REL (S Pen, rear camera probe), then reboot to BOOT ($(date +%T))" > "$SP/tablet.owner"
log "lock taken"
[ "$(s 'uname -r')" = 7.3.4-r20 ] || { log "not on r20"; : > "$SP/tablet.owner"; exit 1; }

# libcamera's cam tool for "cam -l" (Arch repo packages)
r 'pacman -Q libcamera-tools >/dev/null 2>&1 || pacman -S --noconfirm --needed --disable-sandbox libcamera libcamera-ipa libcamera-tools 2>&1 | tail -2' | tee -a "$OUT/run.log"
tar -C "$K/usr/lib/modules" -cf - "$REL" | s "rm -rf /tmp/m50; mkdir /tmp/m50; tar -C /tmp/m50 -xf -"
r "rm -rf /usr/lib/modules/$REL; cp -a /tmp/m50/$REL /usr/lib/modules/; chown -R root:root /usr/lib/modules/$REL; depmod -a $REL; rm -rf /tmp/m50; ls /usr/lib/modules" | tee -a "$OUT/run.log"
r 'cat /sys/firmware/fdt' > "$OUT/running.fdt"
python3 "$ROOT/tools/kexec_dtb.py" --new "$K/boot/dtbs/qcom/sm8250-samsung-gts7xl-rearcam.dtb" --running "$OUT/running.fdt" -o "$OUT/kexec.dtb" || exit 1
zcat "$K/boot/vmlinuz" > "$OUT/Image"
scp -q "${O[@]}" "$OUT/Image" "$OUT/kexec.dtb" "$T:/tmp/" && scp -q "${O[@]}" "$(realpath "$ROOT/build/initramfs")" "$T:/tmp/initramfs-r50"
r 'kexec -c -l /tmp/Image --dtb=/tmp/kexec.dtb --initrd=/tmp/initramfs-r50 --reuse-cmdline 2>&1 | grep -v kcore; cat /sys/kernel/kexec_loaded' | tee -a "$OUT/run.log"
log "systemctl kexec"; r 'systemd-run --on-active=2 systemctl kexec' > /dev/null 2>&1
wait_down 60; wait_up 300 || { log "NOT BACK: owner needed, lock kept"; exit 2; }
log back; sleep 40

r 'uname -r; journalctl -b -k | grep -iE "wacom|w90xx|i2c17|88c000|gpi" | tail -20
grep -B1 -A9 -i "w90xx" /proc/bus/input/devices
libinput list-devices 2>/dev/null | grep -A12 -i "w90xx"
journalctl -b -k | grep -iE "camss|cci|s5k3m5|csiphy|camcc" | tail -20
ls /dev/media* /dev/video* /dev/v4l-subdev* 2>/dev/null | tr "\n" " "; echo
command -v cam >/dev/null && timeout 20 cam -l 2>&1 | tail -8; command -v cam >/dev/null && timeout 20 cam -c 1 -I 2>&1 | tail -15
for p in /sys/class/remoteproc/*; do echo "$(cat $p/name) $(cat $p/state)"; done
systemctl is-active hexagonrpcd-sdsp iio-sensor-proxy
timeout 8 ssccli --sensor accelerometer --timeout 2 2>&1 | grep measurement | head -2
journalctl -b -k | grep -c "BTF: -22"; systemctl --failed --no-legend' 2>&1 | tee -a "$OUT/checks.txt"

log "reboot to BOOT"; r 'systemd-run --on-active=2 systemctl reboot' > /dev/null 2>&1
wait_down 60; wait_up 400 || { log "not back after reboot: owner needed, lock kept"; exit 2; }
sleep 30; s 'uname -r; systemctl --failed --no-legend' 2>&1 | tee -a "$OUT/checks-back.txt"
: > "$SP/tablet.owner"; log "lock released ($OUT)"
