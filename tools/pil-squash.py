#!/usr/bin/env python3
"""Join a split Qualcomm PIL image (name.mdt + name.bNN) into one .mbn file.

usage: tools/pil-squash.py path/to/a650_zap.mdt out.mbn

Each program header with a file size is placed at its p_offset; segment N comes from
name.bNN when present, otherwise from the .mdt itself (the .mdt carries the ELF header,
the program headers and usually the hash segment). Same output as linaro pil-squasher.
"""
import struct
import sys
from pathlib import Path


def main(mdt_path: str, out_path: str) -> int:
    mdt = Path(mdt_path)
    data = mdt.read_bytes()
    if data[:4] != b"\x7fELF":
        sys.exit(f"{mdt}: not an ELF file")
    is64 = data[4] == 2
    if is64:
        phoff, = struct.unpack_from("<Q", data, 0x20)
        phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
    else:
        phoff, = struct.unpack_from("<I", data, 0x1C)
        phentsize, phnum = struct.unpack_from("<HH", data, 0x2A)
    out = bytearray()
    for i in range(phnum):
        ph = phoff + i * phentsize
        if is64:
            _, _, off, _, _, filesz = struct.unpack_from("<IIQQQQ", data, ph)
        else:
            _, off, _, _, filesz = struct.unpack_from("<IIIII", data, ph)
        if not filesz:
            continue
        seg = mdt.with_suffix(f".b{i:02d}")
        if seg.exists():
            blob = seg.read_bytes()
        else:
            blob = data[off:off + filesz]
        if len(blob) != filesz:
            sys.exit(f"segment {i}: {len(blob)} bytes, program header says {filesz}")
        if len(out) < off + filesz:
            out.extend(b"\0" * (off + filesz - len(out)))
        out[off:off + filesz] = blob
    Path(out_path).write_bytes(out)
    print(f"{out_path}: {len(out)} bytes, {phnum} program headers")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
