# tests/test_dtbo.py
import struct, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import dtbo

FDT = struct.pack(">II", 0xD00DFEED, 40) + b"\0" * 32  # fake 40-byte FDT

def test_empty_table_is_header_only():
    data = dtbo.build([])
    magic, total, hsize, esize, count, off, page, ver = struct.unpack(">8I", data[:32])
    assert (magic, total, hsize, esize, count, off) == (0xD7B7AB1E, 32, 32, 32, 0, 32)
    assert len(data) == 32

def test_roundtrip_two_entries():
    e = [dtbo.Entry(8, 0, (0, 0, 0, 0), FDT), dtbo.Entry(8, 6, (1, 2, 3, 4), FDT + b"x" * 8)]
    out = dtbo.parse(dtbo.build(e))
    assert [(x.id, x.rev, x.custom, x.blob) for x in out] == [(x.id, x.rev, x.custom, x.blob) for x in e]

def test_parse_rejects_bad_magic():
    import pytest
    with pytest.raises(ValueError):
        dtbo.parse(b"\0" * 64)

def test_cli_empty(tmp_path):
    out = tmp_path / "e.img"
    subprocess.run([sys.executable, "tools/dtbo.py", "empty", str(out)], check=True)
    assert out.read_bytes() == dtbo.build([])
