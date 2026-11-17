#!/usr/bin/env bash
# Install the sensor DSP (SLPI) firmware and the hexagonrpcd file tree into a root tree
# (the Omarchy image build, or / on the tablet). Run as root. Nothing is mounted.
#
# usage: tools/install-sensors.sh ROOT [FW_DIR] [HEXAGONFS_DIR]
#   FW_DIR         [build/firmware-slpi]   slpi.mbn, slpir.jsn, slpius.jsn
#                                          (tools/extract-dsp.py slpi BL_<...>.tar.md5 DIR)
#   HEXAGONFS_DIR  [build/hexagonfs-gts7xl] (tools/build-hexagonfs.sh)
#
# Layout:
#   ROOT/usr/lib/firmware/qcom/sm8250/samsung/gts7xl/{slpi.mbn,slpir.jsn,slpius.jsn}
#   ROOT/usr/share/qcom/sm8250/Samsung/gts7xl/{dsp,sensors/{sns_reg.conf,sns_reg_version},socinfo}
#       (no sensors/config: see tools/build-hexagonfs.sh)
#   ROOT/var/lib/hexagonrpcd/sensors-registry/  the registry (the SLPI writes calibration
#       updates into it); sensors/registry in the tree above is a symlink to it. An existing
#       registry on the target is kept.
# Samsung-signed firmware and per-device calibration: local only, never in a package repo.
set -euo pipefail

root_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[ $# -ge 1 ] || { sed -n '2,17p' "$0"; exit 2; }
R=$1
fw=${2:-$root_dir/build/firmware-slpi}
hfs=${3:-$root_dir/build/hexagonfs-gts7xl}
[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
for f in slpi.mbn slpir.jsn slpius.jsn; do
	[ -s "$fw/$f" ] || { echo "missing $fw/$f" >&2; exit 1; }
done
[ -s "$hfs/dsp/sdsp/fastrpc_shell_2" ] || { echo "missing $hfs (tools/build-hexagonfs.sh)" >&2; exit 1; }

d=$R/usr/lib/firmware/qcom/sm8250/samsung/gts7xl
install -d -m755 "$d"
for f in slpi.mbn slpir.jsn slpius.jsn; do install -m644 "$fw/$f" "$d/$f"; done

t=$R/usr/share/qcom/sm8250/Samsung/gts7xl
install -d -m755 "$t" "$t/sensors"
rm -rf "$t/dsp" "$t/sensors/config" "$t/sensors/config.stock" "$t/socinfo"
cp -a "$hfs/dsp" "$hfs/socinfo" "$t/"
cp -a "$hfs/sensors/sns_reg.conf" "$hfs/sensors/sns_reg_version" "$t/sensors/"
chown -R 0:0 "$t"

reg=$R/var/lib/hexagonrpcd/sensors-registry
install -d -m755 "$R/var/lib/hexagonrpcd"
if [ -n "$(ls -A "$reg" 2>/dev/null)" ]; then
	echo "keeping the registry already in $reg"
else
	install -d -m750 "$reg"
	cp -a "$hfs/sensors/registry/." "$reg/"
fi
ln -sfn /var/lib/hexagonrpcd/sensors-registry "$t/sensors/registry"
# fastrpc (hexagonrpcd's user) owns its state; chown by id inside the target if it exists.
if chroot "$R" id fastrpc > /dev/null 2>&1; then
	chroot "$R" chown -R fastrpc:fastrpc /var/lib/hexagonrpcd
fi
echo "SLPI firmware -> $d, hexagonfs -> $t, registry -> $reg"
