#!/usr/bin/env python3
"""Make a pmOS boot.img acceptable to the Samsung ABL of the Tab S7+ 5G (gts7xl).

Copies the header fields the ABL checks from the stock T976B boot.img, keeps the
input image's kernel cmdline (pmbootstrap puts pmos_boot_uuid/pmos_root_uuid
there; --append-cmdline adds args, --replace-cmdline discards it), then adds an
AVB hash footer signed with the AOSP test key
(the vbmeta partition carries flags 0x02). Derived from the Droidian port's
build-bootimg.py, minus its Wi-Fi-specific constants.
"""
import argparse, struct, subprocess, sys
from pathlib import Path

BOOT_PARTITION_SIZE = 71303168
COPIED = [(20, 4), (28, 4), (32, 4), (44, 4), (48, 16)]  # ramdisk, second, tags, os_version, name
CMDLINE_OFF, CMDLINE_SIZE = 64, 512     # cmdline[512], NUL-terminated
EXTRA_OFF, EXTRA_SIZE = 608, 1024       # extra_cmdline[1024], after id[32]
CMDLINE_MAX = CMDLINE_SIZE - 1 + EXTRA_SIZE - 1
KEY = Path(__file__).parent / "keys" / "testkey_rsa4096.pem"

def copy_abl_fields(src: bytes, dst: bytearray) -> None:
    for img in (src, dst):
        if img[:8] != b"ANDROID!":
            raise ValueError("not an Android boot image")
        version = struct.unpack_from("<I", img, 40)[0]
        if version != 2:
            raise ValueError(f"boot image header version {version}, expected 2")
    for off, size in COPIED:
        dst[off:off + size] = src[off:off + size]

def get_cmdline(img: bytes) -> str:
    """Kernel cmdline of a header v2 image: cmdline[512] followed by extra_cmdline[1024]."""
    parts = (img[CMDLINE_OFF:CMDLINE_OFF + CMDLINE_SIZE], img[EXTRA_OFF:EXTRA_OFF + EXTRA_SIZE])
    return b"".join(p.split(b"\0", 1)[0] for p in parts).decode("ascii")

def set_cmdline(dst: bytearray, cmdline: str) -> None:
    """Write the cmdline the way mkbootimg does: 511 bytes + NUL, the rest in extra_cmdline."""
    try:
        raw = cmdline.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError("cmdline is not ASCII") from None
    if len(raw) > CMDLINE_MAX:
        raise ValueError(f"cmdline too long for header v2: {len(raw)} bytes, max {CMDLINE_MAX}")
    head, tail = raw[:CMDLINE_SIZE - 1], raw[CMDLINE_SIZE - 1:]
    dst[CMDLINE_OFF:CMDLINE_OFF + CMDLINE_SIZE] = head.ljust(CMDLINE_SIZE, b"\0")
    dst[EXTRA_OFF:EXTRA_OFF + EXTRA_SIZE] = tail.ljust(EXTRA_SIZE, b"\0")

def append_cmdline(current: str, extra: str) -> str:
    """Append the args of `extra` that are not already in `current` (exact match)."""
    present = set(current.split())
    new = [arg for arg in extra.split() if arg not in present]
    return " ".join([current.rstrip(), *new]) if new else current

def stock_rollback_index(path: str) -> int:
    """Rollback index from the stock image's AVB footer; 0 if it has no footer."""
    with open(path, "rb") as f:
        f.seek(-64, 2)
        if f.read(4) != b"AVBf":
            return 0
    info = subprocess.run(["avbtool", "info_image", "--image", path],
                          capture_output=True, text=True, check=True).stdout
    for line in info.splitlines():
        if line.startswith("Rollback Index:"):
            return int(line.split(":", 1)[1])
    raise ValueError(f"no Rollback Index in avbtool output for {path}")

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", required=True)
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--append-cmdline", metavar="ARGS",
                     help="append these args to the input image's cmdline (args already present are skipped)")
    grp.add_argument("--replace-cmdline", metavar="CMDLINE",
                     help="discard the input image's cmdline (drops pmos_root_uuid etc.) and use this one")
    ap.add_argument("--rollback-index", type=int,
                    help="AVB rollback index (default: the stock image's, 0 if it has no footer)")
    ap.add_argument("input"); ap.add_argument("output")
    a = ap.parse_args(argv)
    rollback = a.rollback_index if a.rollback_index is not None else stock_rollback_index(a.stock)
    img = bytearray(Path(a.input).read_bytes())
    copy_abl_fields(Path(a.stock).read_bytes(), img)
    cmdline = get_cmdline(img)
    if a.replace_cmdline is not None:
        cmdline = a.replace_cmdline
    elif a.append_cmdline:
        cmdline = append_cmdline(cmdline, a.append_cmdline)
    try:
        set_cmdline(img, cmdline)
    except ValueError as e:
        sys.exit(f"sign_boot.py: {e}")
    if len(cmdline) >= CMDLINE_SIZE:
        print(f"sign_boot.py: warning: cmdline is {len(cmdline)} bytes, {len(cmdline) - CMDLINE_SIZE + 1} of them "
              "go to extra_cmdline (not tested with the Samsung ABL)", file=sys.stderr)
    Path(a.output).write_bytes(img)
    subprocess.run(["avbtool", "erase_footer", "--image", a.output], stderr=subprocess.DEVNULL)
    subprocess.run(["avbtool", "add_hash_footer", "--image", a.output,
                    "--partition_size", str(BOOT_PARTITION_SIZE), "--partition_name", "boot",
                    "--algorithm", "SHA256_RSA4096", "--key", str(KEY),
                    "--rollback_index", str(rollback)], check=True)
    print(f"cmdline: {cmdline}")
    print(f"OK {a.output}")

if __name__ == "__main__":
    main()
