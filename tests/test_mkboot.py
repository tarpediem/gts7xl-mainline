# tests/test_mkboot.py
import shutil, struct, subprocess, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import mkboot, mkrecovery

pytestmark = pytest.mark.skipif(
    not all(shutil.which(t) for t in ("mkbootimg", "unpack_bootimg", "avbtool")),
    reason="mkbootimg/unpack_bootimg/avbtool not installed")

PART = 4 << 20
CMDLINE = "console=tty0 pmos_boot_uuid=1234 pmos_root_uuid=5678"


def mkimg(tmp_path, name, kernel, ramdisk, dtb, cmdline):
    for suffix, data in (("k", kernel), ("r", ramdisk), ("d", dtb)):
        (tmp_path / f"{name}.{suffix}").write_bytes(data)
    out = tmp_path / f"{name}.img"
    subprocess.run(["mkbootimg", "--header_version", "2", "--kernel", str(tmp_path / f"{name}.k"),
                    "--ramdisk", str(tmp_path / f"{name}.r"), "--dtb", str(tmp_path / f"{name}.d"),
                    "--pagesize", "4096", "--base", "0", "--kernel_offset", "0x8000",
                    "--ramdisk_offset", "0x2000000", "--tags_offset", "0x1e00000", "--dtb_offset", "0x1f00000",
                    "--board", "SRPTC16A007", "--os_version", "11.0.0", "--os_patch_level", "2024-08",
                    "--cmdline", cmdline, "--output", str(out)], check=True)
    return out


def make_inputs(tmp_path, stock_kernel=b"STOCKK" * 1000):
    """Signed input (ramdisk + cmdline), stock boot with an AVB footer, shim payload."""
    signed = mkimg(tmp_path, "signed", b"PMOSKERNEL" * 100, b"RAMDISK" * 3000, b"PMOSDTB" * 100, CMDLINE)
    stock = mkimg(tmp_path, "stock", stock_kernel, b"STOCKRD" * 100, b"VENDORDTB" * 300, "console=null")
    subprocess.run(["avbtool", "add_hash_footer", "--image", str(stock), "--partition_size", str(PART),
                    "--partition_name", "boot", "--algorithm", "SHA256_RSA4096",
                    "--key", str(mkrecovery.KEY)], check=True)
    shim = tmp_path / "shim"; shim.write_bytes(b"SHIM" * 20000)
    return signed, stock, shim


def run(tmp_path, signed, stock, shim, *extra):
    out = tmp_path / "boot-shim.img"
    mkboot.main(["--stock-boot", str(stock), "--kernel", str(shim), *extra, str(signed), str(out)])
    return out


def footer(img):
    return struct.unpack_from(">QQQ", img, len(img) - 64 + 12)   # original size, vbmeta offset, size


def check_common(tmp_path, out, stock, shim):
    o, s = out.read_bytes(), stock.read_bytes()
    assert len(o) == PART
    parts = tmp_path / "parts"
    subprocess.run(["unpack_bootimg", "--boot_img", str(out), "--out", str(parts)], check=True, capture_output=True)
    assert (parts / "kernel").read_bytes() == shim.read_bytes()
    assert (parts / "ramdisk").read_bytes() == (tmp_path / "signed.r").read_bytes()
    assert (parts / "dtb").read_bytes() == (tmp_path / "stock.d").read_bytes()     # vendor DTB, not ours
    assert not (parts / "recovery_dtbo").exists() or (parts / "recovery_dtbo").stat().st_size == 0
    assert o[64:64 + len(CMDLINE)].decode() == CMDLINE
    orig, voff, vsize = footer(o)
    so, ss = struct.unpack_from(">QQ", s, PART - 64 + 20)
    assert o[voff:voff + vsize] == s[so:so + ss]                 # stock vbmeta blob, byte for byte
    assert o[orig - 16:orig] == b"SEANDROIDENFORCE" and o.count(b"SEANDROIDENFORCE") == 1
    assert set(o[orig:voff]) <= {0} and set(o[voff + vsize:PART - 64]) <= {0}
    subprocess.run(["avbtool", "info_image", "--image", str(out)], check=True, capture_output=True)
    return o, s, orig, voff


def test_small_image_keeps_the_stock_vbmeta_offset(tmp_path):
    signed, stock, shim = make_inputs(tmp_path, stock_kernel=b"STOCKK" * 300000)
    out = run(tmp_path, signed, stock, shim)
    o, s, orig, voff = check_common(tmp_path, out, stock, shim)
    fs, fo = s[-64:], o[-64:]
    assert all(12 <= i < 20 for i in range(64) if fs[i] != fo[i])    # only original_image_size changes
    assert voff == struct.unpack_from(">Q", s, PART - 64 + 20)[0]


def test_big_image_needs_relocate_vbmeta(tmp_path):
    signed, stock, shim = make_inputs(tmp_path)
    with pytest.raises(SystemExit) as e:
        run(tmp_path, signed, stock, shim)
    assert "--relocate-vbmeta" in str(e.value)


def test_relocated_vbmeta_follows_the_image_like_magiskboot(tmp_path):
    """The Magisk BOOT shape: blob at the first 4096 boundary after the trailer; the footer
    differs from stock only in original_image_size and vbmeta_offset."""
    signed, stock, shim = make_inputs(tmp_path)
    out = run(tmp_path, signed, stock, shim, "--relocate-vbmeta")
    o, s, orig, voff = check_common(tmp_path, out, stock, shim)
    assert voff == (orig + 4095) // 4096 * 4096
    fs, fo = s[-64:], o[-64:]
    assert all(12 <= i < 28 for i in range(64) if fs[i] != fo[i])
    assert (orig - 16) % 4096 == 0


def test_refuses_an_image_without_room_for_the_blob(tmp_path):
    signed, stock, shim = make_inputs(tmp_path)
    shim.write_bytes(b"S" * (PART - 8192))
    with pytest.raises(SystemExit):
        run(tmp_path, signed, stock, shim, "--relocate-vbmeta")


def test_refuses_a_stock_boot_without_footer(tmp_path):
    signed, stock, shim = make_inputs(tmp_path)
    stock.write_bytes(stock.read_bytes()[:-64] + b"\0" * 64)
    with pytest.raises(SystemExit):
        run(tmp_path, signed, stock, shim, "--relocate-vbmeta")
