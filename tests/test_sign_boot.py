# tests/test_sign_boot.py
import struct, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import sign_boot

def mkimg(path, os_version, board, ramdisk_offset):
    k = path.parent / "k"; r = path.parent / "r"; d = path.parent / "d"
    k.write_bytes(b"K" * 4096); r.write_bytes(b"R" * 4096); d.write_bytes(b"D" * 64)
    subprocess.run(["mkbootimg", "--kernel", str(k), "--ramdisk", str(r), "--dtb", str(d), "--header_version", "2",
                    "--os_version", os_version[0], "--os_patch_level", os_version[1],
                    "--board", board, "--ramdisk_offset", ramdisk_offset, "--pagesize", "4096",
                    "-o", str(path)], check=True)

def test_copy_fields(tmp_path):
    mkimg(tmp_path / "stock.img", ("13.0.0", "2024-08"), "STOCKBOARD", "0x02000000")
    mkimg(tmp_path / "pmos.img", ("16.0.0", "2026-11"), "PMOS", "0x01000000")
    src = (tmp_path / "stock.img").read_bytes(); dst = bytearray((tmp_path / "pmos.img").read_bytes())
    sign_boot.copy_abl_fields(src, dst)
    for off in (20, 28, 32, 44):
        assert dst[off:off + 4] == src[off:off + 4]
    assert dst[48:64] == src[48:64]

def test_cli_signs_and_sets_cmdline(tmp_path):
    mkimg(tmp_path / "stock.img", ("13.0.0", "2024-08"), "STOCKBOARD", "0x02000000")
    mkimg(tmp_path / "pmos.img", ("16.0.0", "2026-11"), "PMOS", "0x01000000")
    out = tmp_path / "boot-signed.img"
    subprocess.run([sys.executable, "tools/sign_boot.py", "--stock", tmp_path / "stock.img",
                    "--cmdline", "console=ttyMSM0 pmos_debug", tmp_path / "pmos.img", out], check=True)
    data = out.read_bytes()
    assert data[64:64 + 26] == b"console=ttyMSM0 pmos_debug"
    assert len(data) == 71303168
    info = subprocess.run(["avbtool", "info_image", "--image", out], capture_output=True, text=True, check=True).stdout
    assert "Partition Name:        boot" in info and "SHA256_RSA4096" in info

def test_rejects_non_bootimg(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        sign_boot.copy_abl_fields(b"\0" * 4096, bytearray(b"\0" * 4096))
