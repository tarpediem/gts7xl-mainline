#!/usr/bin/env bash
# Extract readable references from the stock T976B firmware. Read-only on inputs.
set -euo pipefail
FW=${FW:-$HOME/Work/samsung/stock-t976b/fw}
OUT=${OUT:-$(dirname "$0")/../reference}
RAW=$OUT/raw
mkdir -p "$RAW"

# 1. stock boot.img header (mkbootimg arg format) + its DTB
unpack_bootimg --boot_img "$FW/boot.img" --out "$RAW/boot" --format=mkbootimg > "$OUT/stock-boot-header.txt"
unpack_bootimg --boot_img "$FW/boot.img" --out "$RAW/boot" > "$RAW/boot-info.txt"

# 2. stock dtbo.img from the AP tarball
tar -xf "$FW"/AP_*.tar.md5 -C "$RAW" dtbo.img.lz4
lz4 -dfq "$RAW/dtbo.img.lz4" "$RAW/dtbo.img"
python3 "$(dirname "$0")/dtbo.py" split "$RAW/dtbo.img" "$RAW/overlays" > "$OUT/stock-overlays.txt"

# 3. decompile: base DTBs (the boot.img dtb may hold several concatenated FDTs)
python3 - "$RAW/boot/dtb" "$RAW/base" <<'PY'
import sys, struct, pathlib
data = pathlib.Path(sys.argv[1]).read_bytes(); out = pathlib.Path(sys.argv[2]); out.mkdir(exist_ok=True)
i = n = 0
while i + 8 <= len(data):
    magic, size = struct.unpack_from(">II", data, i)
    if magic != 0xD00DFEED: break
    (out / f"{n:02d}.dtb").write_bytes(data[i:i+size]); i += size; n += 1
print(n, "base dtbs")
PY
for f in "$RAW"/base/*.dtb;     do dtc -q -I dtb -O dts -o "$OUT/stock-base-$(basename "$f" .dtb).dts" "$f"; done
for f in "$RAW"/overlays/*.dtbo; do dtc -q -I dtb -O dts -o "$OUT/stock-overlay-$(basename "$f" .dtbo).dts" "$f"; done

# 4. ids actually used for DTB/DTBO selection
: > "$OUT/ids.txt"
for f in "$OUT"/stock-*.dts; do
  ids=$(grep -hoE 'qcom,(msm|board|pmic)-id = <[^>]*>' "$f" | tr '\n' ' ' || true)
  [ -n "$ids" ] && echo "$(basename "$f"): $ids" >> "$OUT/ids.txt"
done
cat "$OUT/ids.txt"
