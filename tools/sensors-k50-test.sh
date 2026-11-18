#!/usr/bin/env bash
# kexec test of the gts7xl-sensors kernel (pmaports gts7xl-sensors, release 7.3.4-r50): S Pen
# (wacom_w90xx), rear camera probe (rearcam DTB: S5K3M5 at the stock 19.2 MHz MCLK, no
# streaming), SLPI sensors and hall switches again; then reboot to the BOOT kernel.
# Nothing is flashed. Runs as the user; root on the tablet through its passwordless sudo.
#
# usage: tools/sensors-k50-test.sh [APK]   (default: build/sensors-k50/linux-samsung-gts7xl-7.3.4-r50.apk, kept out of the pmbootstrap repo)
set -uo pipefail
SP=${SP:-/tmp/claude-1000/-home-tarpediem-Work-samsung-gts7xl-mainline/8218a82d-737f-4327-a27f-5970ee3d04e8/scratchpad}
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
APK=${1:-$(ls -v "$ROOT"/build/sensors-k50/linux-samsung-gts7xl-7.3.4-r5*.apk | tail -1)}
REL=$(basename "$APK" .apk); REL=${REL#linux-samsung-gts7xl-}
PEN_SECS=${PEN_SECS:-60}
DTB_NAME=${DTB_NAME:-sm8250-samsung-gts7xl-rearcam.dtb}   # BOOT tree: DTB_NAME=sm8250-samsung-gts7xl.dtb
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
case "$(s 'uname -r')" in 7.3.4-r20|7.3.4-r21) ;; *) false;; esac || { log "not on the BOOT kernel (r20/r21)"; : > "$SP/tablet.owner"; exit 1; }

# libcamera's cam tool for "cam -l" (Arch repo packages)
r 'pacman -Q libcamera-tools >/dev/null 2>&1 || pacman -S --noconfirm --needed --disable-sandbox libcamera libcamera-ipa libcamera-tools 2>&1 | tail -2' | tee -a "$OUT/run.log"
tar -C "$K/usr/lib/modules" -cf - "$REL" | s "rm -rf /tmp/m50; mkdir /tmp/m50; tar -C /tmp/m50 -xf -"
r "rm -rf /usr/lib/modules/$REL; cp -a /tmp/m50/$REL /usr/lib/modules/; chown -R root:root /usr/lib/modules/$REL; depmod -a $REL; rm -rf /tmp/m50; ls /usr/lib/modules" | tee -a "$OUT/run.log"
r 'cat /sys/firmware/fdt' > "$OUT/running.fdt"
python3 "$ROOT/tools/kexec_dtb.py" --new "$K/boot/dtbs/qcom/$DTB_NAME" --running "$OUT/running.fdt" -o "$OUT/kexec.dtb" || exit 1
zcat "$K/boot/vmlinuz" > "$OUT/Image"
scp -q "${O[@]}" "$OUT/Image" "$OUT/kexec.dtb" "$T:/tmp/" && scp -q "${O[@]}" "$(realpath "$ROOT/build/initramfs")" "$T:/tmp/initramfs-r50"
r 'kexec -c -l /tmp/Image --dtb=/tmp/kexec.dtb --initrd=/tmp/initramfs-r50 --reuse-cmdline 2>&1 | grep -v kcore; cat /sys/kernel/kexec_loaded' | tee -a "$OUT/run.log"
log "systemctl kexec"; r 'systemd-run --on-active=2 systemctl kexec' > /dev/null 2>&1
wait_down 60; wait_up 300 || { log "NOT BACK: owner needed, lock kept"; exit 2; }
log back; sleep 40

r 'uname -r; journalctl -b -k | grep -iE "wacom|w90xx|i2c17|88c000|gpi" | tail -20
grep -B1 -A9 -i "w90xx" /proc/bus/input/devices; for a in 0 1 24 25; do cat /sys/class/input/input*/device/../*/w90xx 2>/dev/null; done; python3 -c "import fcntl,struct,glob
for e in glob.glob(\"/dev/input/event*\"):
  n=open(\"/sys/class/input/\"+e.split(\"/\")[-1]+\"/device/name\").read().strip()
  if \"W90xx\" not in n: continue
  f=open(e,\"rb\")
  for c,nm in ((0,\"X\"),(1,\"Y\"),(0x18,\"P\")):
    b=bytearray(24); fcntl.ioctl(f,0x80184540+c,b); print(nm,struct.unpack(\"6i\",b)[:3])"
libinput list-devices 2>/dev/null | grep -A12 -i "w90xx"
journalctl -b -k | grep -iE "camss|cci|s5k3m5|csiphy|camcc" | tail -20
ls /dev/media* /dev/video* /dev/v4l-subdev* 2>/dev/null | tr "\n" " "; echo
command -v cam >/dev/null && timeout 20 cam -l 2>&1 | tail -8; command -v cam >/dev/null && timeout 20 cam -c 1 -I 2>&1 | tail -15
for p in /sys/class/remoteproc/*; do echo "$(cat $p/name) $(cat $p/state)"; done
systemctl is-active hexagonrpcd-sdsp iio-sensor-proxy
timeout 8 ssccli --sensor accelerometer --timeout 2 2>&1 | grep measurement | head -2
journalctl -b -k | grep -c "BTF: -22"; systemctl --failed --no-legend
echo scm_assign_errors=$(journalctl -b -k | grep -c "Assign memory protection")
journalctl -b -k | grep -E "safety monitor" | cut -c1-140
cat /sys/class/power_supply/max77705-charger/usb_type /sys/class/power_supply/max77705-charger/input_current_limit
nmcli -t -f DEVICE,STATE dev | grep wlp; bluetoothctl list
journalctl -b -k | grep -c -E "adsp is now up|Loaded GMU"
grep -B1 -A3 -i "hall" /proc/bus/input/devices | grep -E "Name|SW="' 2>&1 | tee -a "$OUT/checks.txt"
s 'export XDG_RUNTIME_DIR=/run/user/1000; wpctl status 2>/dev/null | grep -iE "speaker|protected" | head -3' 2>&1 | tee -a "$OUT/checks.txt"

# Hands-on part (owner): pen and rotation, then Enter to go back to the BOOT kernel.
cat <<MSG

=== On the tablet now (test kernel $REL) ===
1. S Pen: within the next $PEN_SECS seconds, hover the pen over the screen, then draw a few
   strokes, touch the four corners, press the side button.
2. Then turn the tablet: landscape, portrait both ways, upside down; watch GNOME rotate.
MSG
r "P=\$(grep -l 'W90xx' /sys/class/input/event*/device/name | head -1 | sed 's|/device/name||; s|.*/||'); echo pen=/dev/input/\$P
grep w9021 /proc/interrupts | awk '{s=0; for(i=2;i<=9;i++) s+=\$i; print \"irq before:\", s}'
timeout $PEN_SECS python3 - /dev/input/\$P <<'PY'
import struct,sys,time
f=open(sys.argv[1],'rb'); n={}; mn=[1<<30]*2; mx=[0]*2; pmax=0; keys=set()
try:
    while True:
        t1,t2,ty,co,v=struct.unpack('llHHi',f.read(24))
        n[(ty,co)]=n.get((ty,co),0)+1
        if ty==3 and co in (0,1): mn[co]=min(mn[co],v); mx[co]=max(mx[co],v)
        if ty==3 and co==24: pmax=max(pmax,v)
        if ty==1 and v: keys.add(co)
        if sum(n.values())%200==1: print('events', sum(n.values()), 'x', mn[0], mx[0], 'y', mn[1], mx[1], 'pmax', pmax, 'keys', sorted(keys), flush=True)
except Exception: pass
PY
grep w9021 /proc/interrupts | awk '{s=0; for(i=2;i<=9;i++) s+=\$i; print \"irq after:\", s}'
journalctl -b -k | grep -i 'w90xx' | tail -5" 2>&1 | tee -a "$OUT/pen.txt"
echo "Rotation (iio-sensor-proxy), 30 s:" | tee -a "$OUT/rotation.txt"
r 'timeout 30 monitor-sensor --accel 2>&1' | tee -a "$OUT/rotation.txt"
if [ -t 0 ]; then read -r -p "Press Enter to reboot back to the BOOT kernel... " _; fi

log "reboot to BOOT"; r 'systemd-run --on-active=2 systemctl reboot' > /dev/null 2>&1
wait_down 60; wait_up 400 || { log "not back after reboot: owner needed, lock kept"; exit 2; }
sleep 30; s 'uname -r; systemctl --failed --no-legend' 2>&1 | tee -a "$OUT/checks-back.txt"
: > "$SP/tablet.owner"; log "lock released ($OUT)"
