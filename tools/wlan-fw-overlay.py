#!/usr/bin/env python3
"""Build a small initramfs overlay (newc cpio) with the gts7xl QCA6390 board data.

The Samsung board data file (bdwlan.*, from the stock vendor partition) is not
redistributable, so it never goes into a package or a git repo. This tool takes the
linux-firmware board-2.bin, adds one entry built from the stock BDF under the name ath11k
asks for on this board, and writes a cpio that is appended to the pmOS initramfs (the
kernel unpacks concatenated cpio archives in order). The plain board-2.bin it contains is
found before the board-2.bin.zst of the package: the firmware loader tries the name
without a compression suffix first.

usage: tools/wlan-fw-overlay.py --board-2 /lib/firmware/.../board-2.bin[.zst]
           --bdf build/firmware-vendor/bdwlan.elf
           --name 'bus=pci,qmi-chip-id=0,qmi-board-id=255,variant=Samsung_gts7xl'
           [--file SRC:DEST ...] -o build/wlan-overlay.cpio

ath11k prints the name it looks for: "failed to fetch board data for <name>" (or, with
debug, "boot using board name <name>").
"""
import argparse
import os
import struct
import subprocess
import sys

MAGIC = b"QCA-ATH11K-BOARD\0"
IE_BOARD = 0
IE_NAME = 0
IE_DATA = 1
# usr/lib: in the pmOS initramfs /lib is a symlink to usr/lib (usrmerge)
FW_DIR = "usr/lib/firmware/ath11k/QCA6390/hw2.0"


def pad4(b):
    return b + b"\0" * (-len(b) % 4)


def ie(kind, body):
    return struct.pack("<II", kind, len(body)) + pad4(body)


def parse_board2(data):
    """[(names, bdf)] from a board-2.bin."""
    if not data.startswith(MAGIC):
        raise ValueError("not a board-2.bin (magic)")
    off = len(pad4(MAGIC))
    out = []
    while off < len(data):
        kind, length = struct.unpack_from("<II", data, off)
        off += 8
        body = data[off:off + length]
        off += length + (-length % 4)
        if kind != IE_BOARD:
            continue
        names, bdf, o = [], None, 0
        while o < len(body):
            t, ln = struct.unpack_from("<II", body, o)
            o += 8
            if t == IE_NAME:
                names.append(body[o:o + ln].decode())
            elif t == IE_DATA:
                bdf = body[o:o + ln]
            o += ln + (-ln % 4)
        out.append((names, bdf))
    return out


def build_board2(entries):
    out = pad4(MAGIC)
    for names, bdf in entries:
        body = b"".join(ie(IE_NAME, n.encode()) for n in names) + ie(IE_DATA, bdf)
        out += ie(IE_BOARD, body)
    return out


def cpio(files):
    """newc archive; files = [(path, bytes)]. Parent directories are added."""
    dirs, entries = set(), []
    for path, _ in files:
        parts = path.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            dirs.add("/".join(parts[:i]))
    ino = 1

    def hdr(name, mode, data):
        nonlocal ino
        n = name.encode() + b"\0"
        h = b"070701" + b"".join(b"%08X" % v for v in (
            ino, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(n), 0))
        ino += 1
        rec = h + n
        rec += b"\0" * (-len(rec) % 4)
        return rec + data + b"\0" * (-len(data) % 4)

    for d in sorted(dirs):
        entries.append(hdr(d, 0o040755, b""))
    for path, data in files:
        entries.append(hdr(path, 0o100644, data))
    entries.append(hdr("TRAILER!!!", 0, b""))
    return b"".join(entries)


def read_maybe_zst(path):
    if path.endswith(".zst"):
        return subprocess.run(["zstd", "-dc", path], check=True, capture_output=True).stdout
    with open(path, "rb") as f:
        return f.read()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--board-2", required=True)
    ap.add_argument("--bdf", required=True)
    ap.add_argument("--name", action="append", required=True)
    ap.add_argument("--file", action="append", default=[], help="SRC:DEST (DEST relative to /)")
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args(argv)

    entries = parse_board2(read_maybe_zst(a.board_2))
    taken = {n for names, _ in entries for n in names}
    clash = taken.intersection(a.name)
    if clash:
        sys.exit(f"wlan-fw-overlay: already in board-2.bin: {sorted(clash)}")
    with open(a.bdf, "rb") as f:
        bdf = f.read()
    entries.append((a.name, bdf))
    files = [(f"{FW_DIR}/board-2.bin", build_board2(entries))]
    for spec in a.file:
        src, dest = spec.split(":", 1)
        with open(src, "rb") as f:
            files.append((dest.lstrip("/"), f.read()))
    with open(a.output, "wb") as f:
        f.write(cpio(files))
    os.chmod(a.output, 0o600)
    print(f"{a.output}: board-2.bin with {len(entries)} entries ({', '.join(a.name)} added)")


if __name__ == "__main__":
    main()
