# tests/test_mkrecovery.py
import shutil, struct, subprocess, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import mkrecovery, dtbo

pytestmark = pytest.mark.skipif(
    not all(shutil.which(t) for t in ("mkbootimg", "unpack_bootimg", "avbtool")),
    reason="mkbootimg/unpack_bootimg/avbtool not installed")

PART = 4 << 20
CMDLINE = "console=tty0 pmos_boot_uuid=1234 it's=\"quoted\""

def make_inputs(tmp_path, header_version=2):
    for name, data in (("k", b"KERNEL" * 1000), ("r", b"RAMDISK" * 500), ("d", b"DTB" * 300),
                       ("t", dtbo.build([dtbo.Entry(0, 0, (0, 0, 0, 0), b"OVERLAY" * 30)]))):
        (tmp_path / name).write_bytes(data)
    boot = tmp_path / "boot.img"
    cmd = ["mkbootimg", "--header_version", str(header_version), "--kernel", str(tmp_path / "k"),
           "--ramdisk", str(tmp_path / "r"), "--pagesize", "4096", "--base", "0",
           "--kernel_offset", "0x8000", "--ramdisk_offset", "0x2000000", "--tags_offset", "0x1e00000",
           "--board", "SRPTC16A007", "--os_version", "11.0.0", "--os_patch_level", "2024-08",
           "--cmdline", CMDLINE, "--output", str(boot)]
    if header_version == 2:
        cmd += ["--dtb", str(tmp_path / "d"), "--dtb_offset", "0x1f00000"]
    subprocess.run(cmd, check=True)
    stock = tmp_path / "stock-recovery.img"; stock.write_bytes(b"\0" * PART)
    return boot, stock

def run(tmp_path, boot, stock):
    out = tmp_path / "recovery.img"
    mkrecovery.main(["--stock-recovery", str(stock), "--recovery-dtbo", str(tmp_path / "t"), str(boot), str(out)])
    return out

def test_recovery_image_layout_and_footer(tmp_path):
    boot, stock = make_inputs(tmp_path)
    out = run(tmp_path, boot, stock)
    assert out.stat().st_size == PART                      # footer sits at the end of the partition
    info = subprocess.run(["avbtool", "info_image", "--image", str(out)], capture_output=True, text=True, check=True).stdout
    assert "Partition Name:        recovery" in info and "SHA256_RSA4096" in info
    assert "Rollback Index:           0" in info
    parts = tmp_path / "parts"
    subprocess.run(["unpack_bootimg", "--boot_img", str(out), "--out", str(parts)], check=True, capture_output=True)
    for comp, src in (("kernel", "k"), ("ramdisk", "r"), ("dtb", "d"), ("recovery_dtbo", "t")):
        assert (parts / comp).read_bytes() == (tmp_path / src).read_bytes(), comp
    a, b = boot.read_bytes(), out.read_bytes()
    assert a[8:64] == b[8:64]                              # sizes, load addresses, os version, board name
    assert a[64:576] == b[64:576] and a[608:1632] == b[608:1632]   # cmdline untouched
    assert struct.unpack_from("<I", b, 1632)[0] == len((tmp_path / "t").read_bytes())
    assert struct.unpack_from("<I", b, 40)[0] == 2

def test_refuses_other_header_versions(tmp_path):
    boot, stock = make_inputs(tmp_path, header_version=1)
    with pytest.raises(SystemExit):
        run(tmp_path, boot, stock)

def test_refuses_image_larger_than_partition(tmp_path):
    boot, stock = make_inputs(tmp_path)
    stock.write_bytes(b"\0" * 8192)
    with pytest.raises(SystemExit):
        run(tmp_path, boot, stock)

def test_refuses_table_without_dt_table_magic(tmp_path):
    boot, stock = make_inputs(tmp_path)
    (tmp_path / "t").write_bytes(b"junk" * 10)
    with pytest.raises(SystemExit):
        run(tmp_path, boot, stock)

def test_stock_footer_is_grafted_unchanged(tmp_path):
    """--stock-footer keeps the stock recovery's own vbmeta blob and footer, byte for byte."""
    boot, stock = make_inputs(tmp_path)
    stock.write_bytes(b"S" * (1 << 20))
    subprocess.run(["avbtool", "add_hash_footer", "--image", str(stock), "--partition_size", str(PART),
                    "--partition_name", "recovery", "--algorithm", "SHA256_RSA4096",
                    "--key", str(mkrecovery.KEY), "--rollback_index", "7"], check=True)
    out = tmp_path / "recovery.img"
    mkrecovery.main(["--stock-recovery", str(stock), "--recovery-dtbo", str(tmp_path / "t"),
                     "--stock-footer", str(boot), str(out)])
    s, o = stock.read_bytes(), out.read_bytes()
    assert len(o) == PART and o[-64:] == s[-64:]
    voff, vsize = struct.unpack_from(">QQ", s, PART - 64 + 20)
    assert o[voff:voff + vsize] == s[voff:voff + vsize]
    assert o[:8] == b"ANDROID!" and set(o[voff + vsize:PART - 64]) <= {0}
    parts = tmp_path / "parts"
    subprocess.run(["unpack_bootimg", "--boot_img", str(out), "--out", str(parts)], check=True, capture_output=True)
    assert (parts / "kernel").read_bytes() == (tmp_path / "k").read_bytes()

def test_stock_footer_needs_room_before_stock_vbmeta(tmp_path):
    boot, stock = make_inputs(tmp_path)
    stock.write_bytes(b"S" * 4096)   # stock vbmeta would sit at 4096: inside our image
    subprocess.run(["avbtool", "add_hash_footer", "--image", str(stock), "--partition_size", str(PART),
                    "--partition_name", "recovery", "--algorithm", "SHA256_RSA4096",
                    "--key", str(mkrecovery.KEY)], check=True)
    with pytest.raises(SystemExit):
        mkrecovery.main(["--stock-recovery", str(stock), "--recovery-dtbo", str(tmp_path / "t"),
                         "--stock-footer", str(boot), str(tmp_path / "o.img")])
