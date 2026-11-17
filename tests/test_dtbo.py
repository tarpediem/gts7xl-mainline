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


# --- no-op clone of a stock table (for the recovery_dtbo section of our RECOVERY image)
import shutil
import pytest

needs_dtc = pytest.mark.skipif(not (shutil.which("dtc") and shutil.which("fdtoverlay") and shutil.which("fdtget")),
                               reason="dtc/fdtoverlay/fdtget not installed")

STOCK_OVERLAY = """/dts-v1/; /plugin/;
/ { model = "Samsung GTS7XL PROJECT (board-id,6)"; compatible = "qcom,kona-mtp", "qcom,kona";
    qcom,board-id = <8 6>; dtbo-version = <0>;
    fragment@0 { target = <&tlmm>; __overlay__ { foo = <1>; bar { baz; }; }; };
    fragment@1 { target-path = "/"; __overlay__ { extra { }; }; }; };
"""
STOCK_TAIL = "/dts-v1/; / { dtbo-version = <1>; };"
BASE = '/dts-v1/; / { model = "base"; qcom,board-id = <0 0>; soc { a = <1>; }; };'

def _dtc(tmp_path, name, src, *flags):
    out = tmp_path / name
    subprocess.run(["dtc", "-q", "-I", "dts", "-O", "dtb", *flags, "-o", str(out), "-"],
                   input=src.encode(), check=True)
    return out.read_bytes()

def _stock_table(tmp_path):
    ov = _dtc(tmp_path, "ov.dtbo", STOCK_OVERLAY)
    tail = _dtc(tmp_path, "tail.dtbo", STOCK_TAIL)
    return dtbo.build([dtbo.Entry(0, 0, (0, 0, 0, 0), ov), dtbo.Entry(3, 4, (5, 6, 7, 8), tail)]) + b"\0" * 100

def test_fdt_root_props_reads_only_root():
    blob = dtbo.fdt_build([("a", b"\0\0\0\1"), ("s", b"x\0")], [("child", [("a", b"zz\0\0")], [])])
    assert dtbo.fdt_root(blob) == ([("a", b"\0\0\0\1"), ("s", b"x\0")], ["child"])

@needs_dtc
def test_noop_keeps_table_shape_and_ids(tmp_path):
    stock = _stock_table(tmp_path)
    out = dtbo.parse(dtbo.noop(stock))
    src = dtbo.parse(stock)
    assert [(e.id, e.rev, e.custom) for e in out] == [(e.id, e.rev, e.custom) for e in src]
    assert dtbo.noop(stock)[24:28] == stock[24:28]            # header page_size kept
    props, nodes = dtbo.fdt_root(out[0].blob)
    assert dict(props)["qcom,board-id"] == struct.pack(">II", 8, 6)
    assert dict(props)["dtbo-version"] == struct.pack(">I", 0)
    assert [n for n, _ in props] == ["model", "compatible", "qcom,board-id", "dtbo-version"]
    assert nodes == ["fragment@0"]
    assert out[1].blob == src[1].blob                          # entry without fragments: untouched

@needs_dtc
def test_noop_overlay_applies_and_changes_nothing(tmp_path):
    base = tmp_path / "base.dtb"; base.write_bytes(_dtc(tmp_path, "b.dtb", BASE))
    ov = tmp_path / "noop.dtbo"; ov.write_bytes(dtbo.parse(dtbo.noop(_stock_table(tmp_path)))[0].blob)
    merged = tmp_path / "merged.dtb"
    # base has no __symbols__: the stock overlay could not apply, the no-op one must
    subprocess.run(["fdtoverlay", "-i", str(base), "-o", str(merged), str(ov)], check=True)
    dts = lambda p: subprocess.run(["dtc", "-q", "-s", "-I", "dtb", "-O", "dts", str(p)],
                                   check=True, capture_output=True).stdout
    assert dts(merged) == dts(base)

@needs_dtc
def test_cli_noop(tmp_path):
    src = tmp_path / "stock.img"; src.write_bytes(_stock_table(tmp_path))
    out = tmp_path / "noop.img"
    tool = Path(__file__).parent.parent / "tools" / "dtbo.py"
    subprocess.run([sys.executable, str(tool), "noop", str(src), str(out)], check=True)
    assert out.read_bytes() == dtbo.noop(src.read_bytes())
