#!/usr/bin/env bash
# Pull the QCA6390 files of the stock vendor partition out of a stock firmware package,
# for tools/wlan-fw-overlay.py. Nothing here talks to the tablet.
#
# usage: tools/extract-qca6390-vendor.sh AP_<...>.tar.md5 OUTDIR [WORKDIR]
#
# AP tar -> super.img.lz4 -> sparse -> raw (simg2img) -> vendor.img (lpunpack) ->
# /firmware/qca6390/{bdwlan.*,amss20.bin,m3.bin,regdb.bin} and /firmware/{htbtfw20.tlv,
# htnv20.bin} (debugfs, read only). Needs tar, lz4, simg2img, lpunpack, debugfs and about
# 2x the size of super.img free in WORKDIR (default: OUTDIR/work, removed at the end).
# These are Samsung/Qualcomm files: keep OUTDIR out of git (build/ is ignored).
set -euo pipefail

[ $# -ge 2 ] || { sed -n '2,12p' "$0"; exit 2; }
ap=$1 out=$2 work=${3:-$2/work}
for t in tar lz4 simg2img lpunpack debugfs; do
	command -v "$t" > /dev/null || { echo "missing tool: $t" >&2; exit 1; }
done
mkdir -p "$out" "$work"
chmod 700 "$out"

if [ ! -e "$work/vendor.img" ]; then
	tar xOf "$ap" super.img.lz4 | lz4 -dc > "$work/super.sparse"
	simg2img "$work/super.sparse" "$work/super.raw"
	rm -f "$work/super.sparse"
	lpunpack -p vendor "$work/super.raw" "$work"
	rm -f "$work/super.raw"
fi

files=$(debugfs -R "ls /firmware/qca6390" "$work/vendor.img" 2> /dev/null |
	tr -s ' ' '\n' | grep -E '^(bdwlan\.[a-z0-9]+|amss20\.bin|m3\.bin|regdb\.bin)$' || true)
[ -n "$files" ] || { echo "no /firmware/qca6390 in vendor.img" >&2; exit 1; }
for f in $files; do
	debugfs -R "dump /firmware/qca6390/$f $out/$f" "$work/vendor.img" 2> /dev/null
done
for f in htbtfw20.tlv htnv20.bin; do
	debugfs -R "dump /firmware/$f $out/$f" "$work/vendor.img" 2> /dev/null || true
done
chmod 600 "$out"/*
[ -z "${3:-}" ] && rm -rf "$work"
(cd "$out" && sha256sum -- * | cut -c1-16,65-)
