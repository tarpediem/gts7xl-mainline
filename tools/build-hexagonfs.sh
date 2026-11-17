#!/usr/bin/env bash
# Build the file tree hexagonrpcd serves to the sensor DSP (SLPI) of the gts7xl.
# Nothing here talks to the tablet, nothing is mounted (debugfs/tar read the images).
#
# usage: tools/build-hexagonfs.sh BL_<...>.tar.md5 VENDOR_IMG PERSIST_TAR OUTDIR
#
#   BL tar       stock BL package: dspso.bin (ext4) -> /sdsp (fastrpc_shell_2, skels)
#   VENDOR_IMG   stock vendor.img (tools/extract-qca6390-vendor.sh keeps one in its
#                work dir): /etc/sensors/config/*.json, /etc/sensors/sns_reg_config
#   PERSIST_TAR  tar of the stock /mnt/vendor/persist (backup of 2026-11-17):
#                sensors/registry/registry/* = the registry the stock SLPI generated on
#                THIS tablet (factory calibration included)
#   OUTDIR       gets the hexagonrpcd root (-R): dsp/sdsp, sensors/{config,registry},
#                sensors/sns_reg.conf, socinfo
#
# Install on the tablet as /usr/share/qcom/sm8250/Samsung/gts7xl/ (hexagonrpcd -R).
# The registry records the mtime of every config file it was built from
# (sns_reg_config, 1230735600 here); the configs keep that mtime so the SLPI reuses the
# stock registry instead of rebuilding it from the json files.
# These are Samsung/Qualcomm files and per-device calibration: OUTDIR stays out of git.
set -euo pipefail

[ $# -eq 4 ] || { sed -n '2,20p' "$0"; exit 2; }
bl=$1 vendor=$2 persist=$3 out=$4
for t in tar lz4 debugfs; do
	command -v "$t" > /dev/null || { echo "missing tool: $t" >&2; exit 1; }
done
umask 077
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$out"/dsp/sdsp "$out"/sensors/config "$out"/sensors/registry "$out"/socinfo

tar xOf "$bl" dspso.bin.lz4 | lz4 -dc > "$work/dspso.bin"
for f in $(debugfs -R "ls /sdsp" "$work/dspso.bin" 2> /dev/null | tr -s ' ' '\n' |
	grep -vE '^(\.|\.\.|\([0-9]+\)|[0-9]+|)$'); do
	debugfs -R "dump -p /sdsp/$f $out/dsp/sdsp/$f" "$work/dspso.bin" 2> /dev/null
done

for f in $(debugfs -R "ls /etc/sensors/config" "$vendor" 2> /dev/null | tr -s ' ' '\n' |
	grep -E '\.json$'); do
	debugfs -R "dump -p /etc/sensors/config/$f $out/sensors/config/$f" "$vendor" 2> /dev/null
done
debugfs -R "dump -p /etc/sensors/sns_reg_config $out/sensors/sns_reg.conf" "$vendor" 2> /dev/null

tar xf "$persist" -C "$work" persist/sensors/registry/registry
cp -p "$work"/persist/sensors/registry/registry/* "$out"/sensors/registry/

# SoC info the stock sns_reg_config reads (/sys/devices/soc0/*): SM8250 = soc_id 356,
# the registry was built from the MTP configs (kona_lsm6dso_0_0.json, not the QRD one).
printf '356\n' > "$out"/socinfo/soc_id
printf 'MTP\n' > "$out"/socinfo/hw_platform
printf '0\n' > "$out"/socinfo/platform_subtype_id
printf 'Unknown\n' > "$out"/socinfo/platform_subtype
printf '65536\n' > "$out"/socinfo/platform_version

[ -s "$out"/dsp/sdsp/fastrpc_shell_2 ] || { echo "no /sdsp/fastrpc_shell_2 in dspso.bin" >&2; exit 1; }
[ -s "$out"/sensors/registry/lsm6dso_0_platform ] || { echo "no lsm6dso registry in $persist" >&2; exit 1; }
find "$out" -type d -exec chmod 755 {} + ; find "$out" -type f -exec chmod 644 {} +
echo "$(find "$out" -type f | wc -l) files in $out"
