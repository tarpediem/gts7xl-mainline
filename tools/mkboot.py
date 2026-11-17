#!/usr/bin/env python3
"""Turn our signed boot image into an image for the BOOT partition of the gts7xl.

The BOOT counterpart of tools/mkrecovery.py --stock-dt --stock-footer: a normal power-on then
starts Linux instead of One UI.

Sections: header v2 fields, ramdisk and cmdline of the input image (tools/sign_boot.py already
copied the ABL header fields from the stock boot.img); kernel slot = --kernel (the boot shim);
dtb = the stock boot.img's own, byte for byte. No recovery_dtbo section (the stock boot.img has
none): on a normal boot the ABL applies the overlays of the DTBO partition, which stays stock.

AVB, like the Magisk-patched BOOT this bootloader already boots: the image ends with the 16-byte
Samsung trailer SEANDROIDENFORCE, the footer's original_image_size is the end of that trailer,
the stock vbmeta blob is kept byte for byte, so the stock vbmeta partition stays as it is
(flash with --keep-vbmeta).

Where the blob goes: at its stock offset when the image ends before it and inside the stock
hashed size; otherwise only with --relocate-vbmeta, at the first 4096-byte boundary after the
trailer, with the footer's vbmeta_offset updated -- exactly what magiskboot does (the Magisk
BOOT on this tablet has its blob at 56143872 instead of 56000512, and its last section, the
dtb, ends 142832 bytes past the stock hashed size). That relies on libavb loading the whole
partition when verification errors are allowed (unlocked bootloader), not just the hashed size.
"""
import argparse, struct, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mkrecovery import SAMSUNG_TRAILER, hash_descriptor_image_size, unpack  # read-only reuse

ALIGN = 4096


def die(msg):
    sys.exit(f"mkboot.py: {msg}")


def place_footer(img: bytes, stock: bytes, relocate: bool) -> tuple[bytes, int, int]:
    """Partition image for `img` (already ending with the trailer): (bytes, vbmeta_offset, hashed)."""
    partition_size = len(stock)
    footer = stock[-64:]
    if footer[:4] != b"AVBf":
        die("stock boot has no AVB footer")
    voff, vsize = struct.unpack_from(">QQ", footer, 20)
    blob = stock[voff:voff + vsize]
    hashed = hash_descriptor_image_size(blob)
    fits_stock = len(img) <= voff and (hashed is None or len(img) <= hashed)
    if not fits_stock:
        if not relocate:
            die(f"image ({len(img)} bytes) does not end before the stock vbmeta blob ({voff}) and inside "
                f"the stock hashed size ({hashed}); --relocate-vbmeta moves the blob like magiskboot")
        voff = (len(img) + ALIGN - 1) // ALIGN * ALIGN
    if voff + vsize > partition_size - 64:
        die(f"image ({len(img)} bytes) leaves no room for the vbmeta blob in the partition ({partition_size})")
    footer = footer[:12] + struct.pack(">QQ", len(img), voff) + footer[28:]
    out = img + b"\0" * (voff - len(img)) + blob + b"\0" * (partition_size - 64 - voff - vsize) + footer
    return out, voff, hashed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stock-boot", required=True, help="stock boot.img: partition size, dtb, footer and vbmeta blob")
    ap.add_argument("--kernel", required=True, help="kernel slot payload (the boot shim, tools/mkshim.py)")
    ap.add_argument("--relocate-vbmeta", action="store_true",
                    help="allow moving the stock vbmeta blob after an image too big for its stock offset")
    ap.add_argument("input", help="signed boot image: header fields, ramdisk and cmdline")
    ap.add_argument("output")
    a = ap.parse_args(argv)
    out = Path(a.output)
    stock_path = Path(a.stock_boot)
    if not Path(a.kernel).is_file():
        die(f"{a.kernel}: no such file")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        stock_opts = unpack(stock_path, tmp / "stock")
        if stock_opts.get("--header_version") != "2":
            die(f"stock boot header version {stock_opts.get('--header_version')}, expected 2")
        if not (tmp / "stock" / "dtb").is_file():
            die("stock boot has no dtb section")
        opts = unpack(Path(a.input), tmp / "in")
        if opts.get("--header_version") != "2":
            die(f"input header version {opts.get('--header_version')}, expected 2")
        opts.pop("--recovery_dtbo", None)
        opts["--kernel"] = a.kernel
        opts["--dtb"] = str(tmp / "stock" / "dtb")
        subprocess.run(["mkbootimg", *[w for kv in opts.items() for w in kv], "--output", str(out)], check=True)
        unpack(out, tmp / "out")
        expect = {"kernel": Path(a.kernel), "ramdisk": tmp / "in" / "ramdisk", "dtb": tmp / "stock" / "dtb"}
        for comp, want in expect.items():
            if want.read_bytes() != (tmp / "out" / comp).read_bytes():
                out.unlink(); die(f"repack changed {comp}")
        if (tmp / "out" / "recovery_dtbo").exists() and (tmp / "out" / "recovery_dtbo").stat().st_size:
            out.unlink(); die("output has a recovery_dtbo section")
        raw = out.read_bytes()
        stock_hdr = stock_path.read_bytes()[:64]
        # kernel/ramdisk/second/tags addresses, page size, os version, board name: the stock boot's
        for off, size in ((12, 4), (20, 4), (28, 4), (32, 4), (36, 4), (44, 4), (48, 16)):
            if raw[off:off + size] != stock_hdr[off:off + size]:
                out.unlink(); die(f"header bytes {off}..{off + size} differ from the stock boot")
    stock = stock_path.read_bytes()
    img, voff, hashed = place_footer(raw + SAMSUNG_TRAILER, stock, a.relocate_vbmeta)
    out.write_bytes(img)
    end = len(raw) + len(SAMSUNG_TRAILER)
    beyond = f", {end - hashed} bytes past the stock hashed size" if hashed is not None and end > hashed else ""
    print(f"OK {out} ({len(img)} bytes, stock vbmeta blob at {voff}, Samsung trailer at {end - 16}{beyond})")


if __name__ == "__main__":
    main()
