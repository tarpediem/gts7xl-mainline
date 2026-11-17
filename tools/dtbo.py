#!/usr/bin/env python3
"""Read and write Android DT-table images (dtbo.img)."""
import struct, sys
from dataclasses import dataclass
from pathlib import Path

MAGIC = 0xD7B7AB1E
HDR = struct.Struct(">8I")
ENT = struct.Struct(">8I")

@dataclass
class Entry:
    id: int
    rev: int
    custom: tuple
    blob: bytes

def parse(data: bytes) -> list:
    magic, total, hsize, esize, count, off, _page, _ver = HDR.unpack_from(data, 0)
    if magic != MAGIC:
        raise ValueError(f"bad DT table magic {magic:#x}")
    out = []
    for i in range(count):
        size, doff, eid, rev, *custom = ENT.unpack_from(data, off + i * esize)
        out.append(Entry(eid, rev, tuple(custom), data[doff:doff + size]))
    return out

def build(entries: list, page_size: int = 4096) -> bytes:
    off = HDR.size + ENT.size * len(entries)
    table, blobs = b"", b""
    for e in entries:
        table += ENT.pack(len(e.blob), off + len(blobs), e.id, e.rev, *e.custom)
        blobs += e.blob
    total = HDR.size + len(table) + len(blobs)
    return HDR.pack(MAGIC, total, HDR.size, ENT.size, len(entries), HDR.size, page_size, 0) + table + blobs

def main(argv):
    if argv[:1] == ["empty"] and len(argv) == 2:
        Path(argv[1]).write_bytes(build([]))
    elif argv[:1] == ["split"] and len(argv) == 3:
        outdir = Path(argv[2]); outdir.mkdir(parents=True, exist_ok=True)
        for i, e in enumerate(parse(Path(argv[1]).read_bytes())):
            name = f"{i:02d}-id{e.id}-rev{e.rev}.dtbo"
            (outdir / name).write_bytes(e.blob)
            print(name, "custom=" + ",".join(map(str, e.custom)))
    else:
        sys.exit("usage: dtbo.py empty OUT | dtbo.py split DTBO OUTDIR")

if __name__ == "__main__":
    main(sys.argv[1:])
