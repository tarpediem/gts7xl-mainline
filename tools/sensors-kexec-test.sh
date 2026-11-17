#!/usr/bin/env bash
# Test the sensor DSP (SLPI, accelerometer for GNOME auto-rotation) and the hall sensors on the
# running Omarchy tablet: install the userspace bits, kexec the r21 kernel with the
# gts7xl-sensors DTB, collect checks, reboot back to the BOOT kernel. Nothing is flashed.
#
# usage: tools/sensors-kexec-test.sh ROOT_RUNNER
#   ROOT_RUNNER  a command that runs its single argument as root on the tablet over USB
#                (the owner's choice; the agents do not type the sudo password)
#
# Needs on the tablet (staged by the sensors agent, as the user, no root):
#   ~/staging-sensors/{firmware-slpi,hexagonfs-gts7xl,kout-sensors/sm8250-samsung-gts7xl-sensors.dtb}
#   ~/src/hexagonrpc/out/hexagonrpcd (built from linux-msm/hexagonrpc da7a374 on the tablet)
#   /usr/lib/modules/7.3.4-r21 (installed by the r21 test)
# The SLPI and hall changes are device tree only: the r21 Image and modules are enough.
# The S Pen driver (wacom_w90xx) and the camera need a kernel built from pmaports
# gts7xl-sensors (new modules).
set -uo pipefail
[ $# -eq 1 ] || { sed -n '2,17p' "$0"; exit 2; }
ROOTRUN=$1
SP=${SP:-/tmp/claude-1000/-home-tarpediem-Work-samsung-gts7xl-mainline/8218a82d-737f-4327-a27f-5970ee3d04e8/scratchpad}
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
OUT=$ROOT/build/sensors-test-$(date +%H%M%S); mkdir -p "$OUT"
O=(-i "$HOME/.ssh/gts7xl_ed25519" -o IdentitiesOnly=yes -o "UserKnownHostsFile=$SP/gts7xl_known_hosts" -o ConnectTimeout=5)
T=tarpediem@172.16.42.1
s() { ssh "${O[@]}" "$T" "$@"; }
r() { "$ROOTRUN" "$1"; }
log() { echo "[$(date +%T)] $*" | tee -a "$OUT/run.log"; }
wait_up() { local i; for ((i=0;i<$1;i+=5)); do s true 2>/dev/null && return 0; sleep 5; done; return 1; }
wait_down() { local i; for ((i=0;i<$1;i+=2)); do s true 2>/dev/null || return 0; sleep 2; done; return 1; }

APK=$(ls -v ~/.local/var/pmbootstrap/packages/edge/aarch64/linux-samsung-gts7xl-7.3.4-r21.apk)
K=$OUT/k; mkdir -p "$K"; tar xzf "$APK" -C "$K" boot 2>/dev/null
exec 9>"$SP/tablet.lock"; flock -w 3600 9 || exit 1
echo "sensors test: SLPI + hall, kexec r21 + sensors DTB, then reboot ($(date +%T))" > "$SP/tablet.owner"
log "lock taken"
[ "$(s 'uname -r')" = 7.3.4-r20 ] || { log "not on r20"; : > "$SP/tablet.owner"; exit 1; }
s 'test -d /usr/lib/modules/7.3.4-r21 && test -x ~/src/hexagonrpc/out/hexagonrpcd && test -d ~/staging-sensors' ||
	{ log "missing r21 modules, hexagonrpcd or staging"; : > "$SP/tablet.owner"; exit 1; }

# 1. userspace, persistent (harmless on r20: no /dev/fastrpc-sdsp there).
scp -q "${O[@]}" "$ROOT/tools/install-sensors.sh" "$ROOT/arch/hexagonrpcd/hexagonrpcd-sdsp.service" \
	"$ROOT/arch/hexagonrpcd/hexagonrpcd.sysusers" "$ROOT/arch/hexagonrpcd/hexagonrpcd.tmpfiles" \
	"$ROOT/arch/hexagonrpcd/80-fastrpc.rules" "$ROOT/arch/gts7xl-device/files/79-gts7xl-sensors.rules" \
	"$ROOT/arch/gts7xl-device/files/logind-lid.conf" "$T:staging-sensors/"
r 'set -e; H=/home/tarpediem/staging-sensors
install -m755 /home/tarpediem/src/hexagonrpc/out/hexagonrpcd /usr/local/bin/hexagonrpcd
sed "s|/usr/bin/hexagonrpcd|/usr/local/bin/hexagonrpcd|" $H/hexagonrpcd-sdsp.service > /etc/systemd/system/hexagonrpcd-sdsp.service
install -Dm644 $H/hexagonrpcd.sysusers /etc/sysusers.d/hexagonrpcd.conf
install -Dm644 $H/hexagonrpcd.tmpfiles /etc/tmpfiles.d/hexagonrpcd.conf
install -Dm644 $H/80-fastrpc.rules /etc/udev/rules.d/80-fastrpc.rules
install -Dm644 $H/79-gts7xl-sensors.rules /etc/udev/rules.d/79-gts7xl-sensors.rules
install -Dm644 $H/logind-lid.conf /etc/systemd/logind.conf.d/40-gts7xl-lid.conf
systemd-sysusers; systemd-tmpfiles --create /etc/tmpfiles.d/hexagonrpcd.conf
bash $H/install-sensors.sh / $H/firmware-slpi $H/hexagonfs-gts7xl
systemctl daemon-reload; systemctl enable hexagonrpcd-sdsp.service
systemctl reload systemd-logind 2>/dev/null || true; echo userspace-ok' 2>&1 | tee -a "$OUT/run.log"

# 2. kexec r21 + sensors DTB (memory layout from the running FDT).
r 'cat /sys/firmware/fdt' > "$OUT/running.fdt"
s 'cat ~/staging-sensors/kout-sensors/sm8250-samsung-gts7xl-sensors.dtb' > "$OUT/sensors.dtb"
python3 "$ROOT/tools/kexec_dtb.py" --new "$OUT/sensors.dtb" --running "$OUT/running.fdt" -o "$OUT/kexec.dtb" || exit 1
zcat "$K/boot/vmlinuz" > "$OUT/Image"
scp -q "${O[@]}" "$OUT/Image" "$OUT/kexec.dtb" "$T:/tmp/" && scp -q "${O[@]}" "$(realpath "$ROOT/build/initramfs")" "$T:/tmp/initramfs-r21"
r 'kexec -c -l /tmp/Image --dtb=/tmp/kexec.dtb --initrd=/tmp/initramfs-r21 --reuse-cmdline 2>&1 | grep -v kcore; cat /sys/kernel/kexec_loaded' | tee -a "$OUT/run.log"
log "systemctl kexec"; r 'systemd-run --on-active=2 systemctl kexec' > /dev/null 2>&1
wait_down 60; wait_up 300 || { log "NOT BACK: owner needed, lock kept"; exit 2; }
log back; sleep 40

# 3. checks
r 'uname -r; for p in /sys/class/remoteproc/*; do echo "$p $(cat $p/name) $(cat $p/state)"; done
ls -la /dev/fastrpc*; systemctl is-active hexagonrpcd-sdsp iio-sensor-proxy
journalctl -b -k | grep -iE "slpi|remoteproc|fastrpc|qcom_q6v5|gpio-keys|hall" | tail -30
journalctl -b -u hexagonrpcd-sdsp | tail -30; journalctl -b -u iio-sensor-proxy | tail -20
udevadm info /dev/fastrpc-sdsp | grep -E "IIO_SENSOR|MOUNT"
grep -A5 -i "hall\|cover" /proc/bus/input/devices
timeout 20 ssccli -h 2>&1 | head -5
ls /var/lib/hexagonrpcd/sensors-registry | wc -l
journalctl -b -k | grep -c "BTF: -22"; systemctl --failed --no-legend' 2>&1 | tee -a "$OUT/checks.txt"
s 'export DBUS_SYSTEM_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket; timeout 15 monitor-sensor --accel 2>&1 | head -20' 2>&1 | tee -a "$OUT/checks.txt"

log "reboot to r20"; r 'systemd-run --on-active=2 systemctl reboot' > /dev/null 2>&1
wait_down 60; wait_up 400 || { log "not back after reboot: owner needed, lock kept"; exit 2; }
sleep 30; s 'uname -r; systemctl --failed --no-legend' 2>&1 | tee -a "$OUT/checks-back.txt"
: > "$SP/tablet.owner"; log "lock released ($OUT)"
