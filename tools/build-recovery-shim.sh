#!/usr/bin/env bash
# Build the RECOVERY candidates that carry the boot shim, from a pmbootstrap export.
#
#   tools/build-recovery-shim.sh [BUILD_DIR]        (default: build/)
#
# Needs in BUILD_DIR: boot.img, vmlinuz, dtbs/sm8250-samsung-gts7xl.dtb (pmbootstrap export)
# and stock/boot-stock.img, stock/recovery.img (stock T976B firmware).
# Writes: shim-Image, boot-xz.img and boot-signed.img (intermediates, never flashed), and
#   recovery-shim.img         stock vbmeta blob kept, Samsung trailer -> flash with --keep-vbmeta (attempt A)
#   recovery-shim-signed.img  test-key AVB footer     -> flash with the disabled vbmeta (attempt B)
# Offline: nothing here talks to the tablet.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
build=$(realpath "${1:-$root/build}")
tools=$root/tools

for f in boot.img vmlinuz dtbs/sm8250-samsung-gts7xl.dtb stock/boot-stock.img stock/recovery.img; do
    [ -e "$build/$f" ] || { echo "build-recovery-shim.sh: missing $build/$f" >&2; exit 1; }
done

python3 "$tools/mkshim.py" --kernel "$build/vmlinuz" --dtb "$build/dtbs/sm8250-samsung-gts7xl.dtb" \
    -o "$build/shim-Image"
# Same initramfs, recompressed as xz: the zstd one no longer fits before the stock vbmeta
# blob since the QCA6390 firmware and modules went in (tools/xz_ramdisk.py).
python3 "$tools/xz_ramdisk.py" "$build/boot.img" "$build/boot-xz.img"
# Header fields of the stock boot image + the pmbootstrap cmdline (root/boot UUIDs).
python3 "$tools/sign_boot.py" --stock "$build/stock/boot-stock.img" "$build/boot-xz.img" "$build/boot-signed.img"
# Kernel slot = shim; dtb and recovery_dtbo = the stock recovery's own, byte for byte.
python3 "$tools/mkrecovery.py" --stock-recovery "$build/stock/recovery.img" --stock-dt \
    --kernel "$build/shim-Image" --stock-footer "$build/boot-signed.img" "$build/recovery-shim.img"
python3 "$tools/mkrecovery.py" --stock-recovery "$build/stock/recovery.img" --stock-dt \
    --kernel "$build/shim-Image" "$build/boot-signed.img" "$build/recovery-shim-signed.img"

(cd "$build" && sha256sum shim-Image recovery-shim.img recovery-shim-signed.img dtbs/sm8250-samsung-gts7xl.dtb)
