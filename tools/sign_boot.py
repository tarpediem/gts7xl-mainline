#!/usr/bin/env python3
"""Make a pmOS boot.img acceptable to the Samsung ABL of the Tab S7+ 5G (gts7xl).

Copies the header fields the ABL checks from the stock T976B boot.img, sets the
kernel cmdline, then adds an AVB hash footer signed with the AOSP test key
(the vbmeta partition carries flags 0x02). Derived from the Droidian port's
build-bootimg.py, minus its Wi-Fi-specific constants.
"""
import argparse, shutil, subprocess, sys
from pathlib import Path

BOOT_PARTITION_SIZE = 71303168
ROLLBACK_INDEX = 1900000000          # >= fused minimum (Droidian finding)
COPIED = [(20, 4), (28, 4), (32, 4), (44, 4), (48, 16)]  # ramdisk, second, tags, os_version, name
KEY = Path(__file__).parent / "keys" / "testkey_rsa4096.pem"

def copy_abl_fields(src: bytes, dst: bytearray) -> None:
    for img in (src, dst):
        if img[:8] != b"ANDROID!":
            raise ValueError("not an Android boot image")
    for off, size in COPIED:
        dst[off:off + size] = src[off:off + size]

def set_cmdline(dst: bytearray, cmdline: str) -> None:
    raw = cmdline.encode()
    if len(raw) >= 512:
        raise ValueError("cmdline too long for header v2")
    dst[64:64 + 512] = raw.ljust(512, b"\0")

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", required=True); ap.add_argument("--cmdline", required=True)
    ap.add_argument("input"); ap.add_argument("output")
    a = ap.parse_args(argv)
    img = bytearray(Path(a.input).read_bytes())
    copy_abl_fields(Path(a.stock).read_bytes(), img)
    set_cmdline(img, a.cmdline)
    Path(a.output).write_bytes(img)
    subprocess.run(["avbtool", "erase_footer", "--image", a.output], stderr=subprocess.DEVNULL)
    subprocess.run(["avbtool", "add_hash_footer", "--image", a.output,
                    "--partition_size", str(BOOT_PARTITION_SIZE), "--partition_name", "boot",
                    "--algorithm", "SHA256_RSA4096", "--key", str(KEY),
                    "--rollback_index", str(ROLLBACK_INDEX)], check=True)
    print(f"OK {a.output}")

if __name__ == "__main__":
    main()
