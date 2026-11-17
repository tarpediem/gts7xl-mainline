#!/usr/bin/env python3
"""Repack a boot image with its ramdisk recompressed as xz (same cpio content).

From device-samsung-gts7xl r9 on (QCA6390 firmware, ath11k/bluetooth modules, iw, btmgmt)
the pmbootstrap initramfs (zstd, ~19 MB) no longer fits in the RECOVERY image before the
stock vbmeta blob (tools/mkrecovery.py --stock-footer). The same cpio as single-threaded
`xz --check=crc32 --lzma2=preset=9e,dict=32MiB` is ~15 MB and the kernel unpacks it (CONFIG_RD_XZ). pmbootstrap's
own "lzma" initfs compression (Go xz) only reaches ~17 MB, too big, so the package keeps
zstd and only the flashed RECOVERY image is recompressed here. xz is deterministic for a
given input: two runs give the same bytes.

usage: tools/xz_ramdisk.py IN.img OUT.img
Needs unpack_bootimg, mkbootimg, xz, zstd (or gzip/xz for other input compressions).
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ZSTD = b"\x28\xb5\x2f\xfd"
GZIP = b"\x1f\x8b"
XZ = b"\xfd7zXZ\x00"


def die(msg):
    sys.exit(f"xz_ramdisk: {msg}")


def unpack(image, outdir):
    res = subprocess.run(["unpack_bootimg", "--boot_img", str(image), "--out", str(outdir),
                          "--format=mkbootimg", "-0"], check=True, capture_output=True)
    words = [w.decode() for w in res.stdout.split(b"\0")]
    if words and words[-1] == "":
        words.pop()
    if len(words) % 2:
        die("unexpected unpack_bootimg output")
    return dict(zip(words[::2], words[1::2]))


def decompress(data):
    if data.startswith(ZSTD):
        cmd = ["zstd", "-dcq"]
    elif data.startswith(GZIP):
        cmd = ["gzip", "-dc"]
    elif data.startswith(XZ):
        cmd = ["xz", "-dc"]
    elif data[:6] in (b"070701", b"070702"):
        return data
    else:
        die("ramdisk: unknown compression")
    return subprocess.run(cmd, input=data, check=True, capture_output=True).stdout


def xz(cpio):
    # As Documentation/staging/xz.rst recommends for an initramfs: crc32 (the kernel's
    # decoder skips other checks), dictionary at most 32 MiB.
    return subprocess.run(["xz", "--check=crc32", "--lzma2=preset=9e,dict=32MiB", "-T1", "-c"],
                          input=cpio,
                          check=True, capture_output=True).stdout


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input")
    ap.add_argument("output")
    a = ap.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        opts = unpack(Path(a.input), tmp / "in")
        if "--ramdisk" not in opts:
            die("no ramdisk in the input image")
        old = Path(opts["--ramdisk"]).read_bytes()
        cpio = decompress(old)
        new = xz(cpio)
        (tmp / "ramdisk.xz").write_bytes(new)
        opts["--ramdisk"] = str(tmp / "ramdisk.xz")
        subprocess.run(["mkbootimg", *[w for kv in opts.items() for w in kv], "--output", a.output],
                       check=True)
        back = unpack(Path(a.output), tmp / "out")
        if decompress(Path(back["--ramdisk"]).read_bytes()) != cpio:
            die("repacked ramdisk differs")
        for comp in ("kernel", "dtb"):
            if (tmp / "in" / comp).exists() and \
                    (tmp / "in" / comp).read_bytes() != (tmp / "out" / comp).read_bytes():
                die(f"repack changed {comp}")
    print(f"{a.output}: ramdisk {len(old)} -> {len(new)} bytes (xz, same cpio)")


if __name__ == "__main__":
    main()
