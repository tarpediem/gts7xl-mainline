#!/usr/bin/env python3
"""Read and write Android DT-table images (dtbo.img).

`noop` clones a stock table (same entry count, id/rev/custom, root properties such as
qcom,board-id and dtbo-version) with overlays that change nothing. It is meant for the
recovery_dtbo section of our own RECOVERY image, never for the DTBO partition: One UI
needs the stock overlays there.
"""
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

FDT_MAGIC, FDT_BEGIN, FDT_END_NODE, FDT_PROP, FDT_NOP, FDT_END = 0xD00DFEED, 1, 2, 3, 4, 9

def _pad4(b: bytes) -> bytes:
    return b + b"\0" * (-len(b) % 4)

def fdt_root(blob: bytes):
    """Return (root properties in order, names of the root's child nodes) of a flat DT."""
    magic, _total, off_struct, off_strings = struct.unpack_from(">4I", blob, 0)
    if magic != FDT_MAGIC:
        raise ValueError(f"bad FDT magic {magic:#x}")
    props, children, depth, pos = [], [], 0, off_struct
    while True:
        (tok,) = struct.unpack_from(">I", blob, pos); pos += 4
        if tok == FDT_BEGIN:
            end = blob.index(b"\0", pos)
            if depth == 1:
                children.append(blob[pos:end].decode())
            depth += 1; pos = (end + 4) & ~3
        elif tok == FDT_END_NODE:
            depth -= 1
            if depth == 0:
                return props, children
        elif tok == FDT_PROP:
            size, nameoff = struct.unpack_from(">II", blob, pos); pos += 8
            if depth == 1:
                name = blob[off_strings + nameoff:blob.index(b"\0", off_strings + nameoff)].decode()
                props.append((name, blob[pos:pos + size]))
            pos = (pos + size + 3) & ~3
        elif tok == FDT_END:
            raise ValueError("FDT ends inside the root node")
        elif tok != FDT_NOP:
            raise ValueError(f"bad FDT token {tok:#x}")

def fdt_build(props: list, children: list) -> bytes:
    """Build a flat DT (v17). props: [(name, bytes)]; children: [(name, props, children)]."""
    strings, offsets = b"", {}
    def node(name, props, children):
        nonlocal strings
        out = struct.pack(">I", FDT_BEGIN) + _pad4(name.encode() + b"\0")
        for pname, value in props:
            if pname not in offsets:
                offsets[pname] = len(strings); strings += pname.encode() + b"\0"
            out += struct.pack(">III", FDT_PROP, len(value), offsets[pname]) + _pad4(value)
        for child in children:
            out += node(*child)
        return out + struct.pack(">I", FDT_END_NODE)
    body = node("", props, children) + struct.pack(">I", FDT_END)
    off_rsv = 40; off_struct = off_rsv + 16; off_strings = off_struct + len(body)
    total = off_strings + len(strings)
    hdr = struct.pack(">10I", FDT_MAGIC, total, off_struct, off_strings, off_rsv, 17, 16, 0,
                      len(strings), len(body))
    return hdr + b"\0" * 16 + body + strings

def noop_overlay(blob: bytes) -> bytes:
    """Overlay with the stock root properties and one fragment that changes nothing."""
    props, children = fdt_root(blob)
    if not children:
        return blob  # already has no fragment (stock tail entry): keep it byte for byte
    fragment = ("fragment@0", [("target-path", b"/\0")], [("__overlay__", [], [])])
    return fdt_build(props, [fragment])

def noop(data: bytes) -> bytes:
    page_size = HDR.unpack_from(data, 0)[6]
    entries = [Entry(e.id, e.rev, e.custom, noop_overlay(e.blob)) for e in parse(data)]
    return build(entries, page_size)

def main(argv):
    if argv[:1] == ["empty"] and len(argv) == 2:
        Path(argv[1]).write_bytes(build([]))
    elif argv[:1] == ["split"] and len(argv) == 3:
        outdir = Path(argv[2]); outdir.mkdir(parents=True, exist_ok=True)
        for i, e in enumerate(parse(Path(argv[1]).read_bytes())):
            name = f"{i:02d}-id{e.id}-rev{e.rev}.dtbo"
            (outdir / name).write_bytes(e.blob)
            print(name, "custom=" + ",".join(map(str, e.custom)))
    elif argv[:1] == ["noop"] and len(argv) == 3:
        Path(argv[2]).write_bytes(noop(Path(argv[1]).read_bytes()))
    else:
        sys.exit("usage: dtbo.py empty OUT | dtbo.py split DTBO OUTDIR | dtbo.py noop STOCK_DTBO OUT")

if __name__ == "__main__":
    main(sys.argv[1:])
