# tests/test_sign_boot.py
import struct, subprocess, sys
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import sign_boot

def mkimg(path, os_version, board, ramdisk_offset, cmdline=None):
    k = path.parent / "k"; r = path.parent / "r"; d = path.parent / "d"
    k.write_bytes(b"K" * 4096); r.write_bytes(b"R" * 4096); d.write_bytes(b"D" * 64)
    subprocess.run(["mkbootimg", "--kernel", str(k), "--ramdisk", str(r), "--dtb", str(d), "--header_version", "2",
                    "--os_version", os_version[0], "--os_patch_level", os_version[1],
                    "--board", board, "--ramdisk_offset", ramdisk_offset, "--pagesize", "4096",
                    *(["--cmdline", cmdline] if cmdline is not None else []),
                    "-o", str(path)], check=True)

PMOS_CMDLINE = ("console=ttyMSM0,115200 console=tty0  pmos_boot_uuid=2b0b362c-be29-4b04-9355-3fb9a5c435d7 "
                "pmos_root_uuid=443f37c0-4db7-4ce5-b7e8-f537bd15892a pmos_rootfsopts=defaults")

def run_cli(tmp_path, *extra, cmdline=PMOS_CMDLINE, check=True):
    mkimg(tmp_path / "stock.img", ("13.0.0", "2024-08"), "STOCKBOARD", "0x02000000", "console=null stock=1")
    mkimg(tmp_path / "pmos.img", ("16.0.0", "2026-11"), "PMOS", "0x01000000", cmdline)
    out = tmp_path / "boot-signed.img"
    r = subprocess.run([sys.executable, "tools/sign_boot.py", "--stock", str(tmp_path / "stock.img"), *extra,
                        str(tmp_path / "pmos.img"), str(out)], capture_output=True, text=True)
    if check:
        assert r.returncode == 0, r.stderr
    return r, out

def cmdline_of(path):
    return sign_boot.get_cmdline(Path(path).read_bytes())

def test_cli_keeps_input_cmdline_by_default(tmp_path):
    _, out = run_cli(tmp_path)
    assert cmdline_of(out) == PMOS_CMDLINE
    assert out.read_bytes()[64:64 + len(PMOS_CMDLINE)] == PMOS_CMDLINE.encode()

def test_cli_append_cmdline_keeps_pmos_args(tmp_path):
    _, out = run_cli(tmp_path, "--append-cmdline", "panic=5 pmos.debug-shell")
    assert cmdline_of(out) == PMOS_CMDLINE + " panic=5 pmos.debug-shell"

def test_cli_append_skips_args_already_present(tmp_path):
    _, out = run_cli(tmp_path, "--append-cmdline", "console=tty0 panic=5")
    assert cmdline_of(out) == PMOS_CMDLINE + " panic=5"

def test_cli_replace_cmdline(tmp_path):
    _, out = run_cli(tmp_path, "--replace-cmdline", "console=ttyMSM0 pmos_debug")
    assert cmdline_of(out) == "console=ttyMSM0 pmos_debug"

def test_cli_append_and_replace_are_exclusive(tmp_path):
    r, out = run_cli(tmp_path, "--append-cmdline", "a=1", "--replace-cmdline", "b=2", check=False)
    assert r.returncode != 0 and not out.exists()

def test_cli_old_cmdline_option_is_rejected(tmp_path):
    r, out = run_cli(tmp_path, "--cmdline", "console=tty0", check=False)
    assert r.returncode != 0 and not out.exists()

def test_cmdline_spills_into_extra_cmdline(tmp_path):
    long = " ".join(f"arg{i:03d}=xxxxxxxxxxxxxxxx" for i in range(40))  # 999 bytes
    assert 512 <= len(long) < 1535
    r, out = run_cli(tmp_path, "--replace-cmdline", long)
    data = out.read_bytes()
    assert data[64:64 + 511] == long.encode()[:511] and data[64 + 511] == 0
    assert data[608:608 + len(long) - 511] == long.encode()[511:]
    assert cmdline_of(out) == long
    assert "extra_cmdline" in r.stderr
    unpacked = subprocess.run(["unpack_bootimg", "--boot_img", str(out), "--out", str(tmp_path / "u")],
                              capture_output=True, text=True, check=True).stdout
    assert long[:511] in unpacked and long[511:] in unpacked  # printed as two fields

def test_cli_fails_when_cmdline_exceeds_header(tmp_path):
    r, out = run_cli(tmp_path, "--append-cmdline", "x" * 1400, check=False)
    assert r.returncode != 0 and "too long" in r.stderr and not out.exists()

def test_set_cmdline_limits():
    img = bytearray(4096)
    sign_boot.set_cmdline(img, "a" * 1534)
    assert sign_boot.get_cmdline(bytes(img)) == "a" * 1534
    with pytest.raises(ValueError):
        sign_boot.set_cmdline(img, "a" * 1535)
    with pytest.raises(ValueError):
        sign_boot.set_cmdline(img, "caf\u00e9=1")

def test_copy_fields(tmp_path):
    mkimg(tmp_path / "stock.img", ("13.0.0", "2024-08"), "STOCKBOARD", "0x02000000")
    mkimg(tmp_path / "pmos.img", ("16.0.0", "2026-11"), "PMOS", "0x01000000")
    src = (tmp_path / "stock.img").read_bytes(); dst = bytearray((tmp_path / "pmos.img").read_bytes())
    sign_boot.copy_abl_fields(src, dst)
    for off in (20, 28, 32, 44):
        assert dst[off:off + 4] == src[off:off + 4]
    assert dst[48:64] == src[48:64]

def test_cli_signs(tmp_path):
    _, out = run_cli(tmp_path)
    data = out.read_bytes()
    assert len(data) == 71303168
    info = subprocess.run(["avbtool", "info_image", "--image", out], capture_output=True, text=True, check=True).stdout
    assert "Partition Name:        boot" in info and "SHA256_RSA4096" in info

def test_rejects_non_bootimg(tmp_path):
    with pytest.raises(ValueError):
        sign_boot.copy_abl_fields(b"\0" * 4096, bytearray(b"\0" * 4096))

KEY = Path(__file__).parent.parent / "tools" / "keys" / "testkey_rsa4096.pem"

def add_footer(path, rollback):
    subprocess.run(["avbtool", "add_hash_footer", "--image", str(path), "--partition_size", "1048576",
                    "--partition_name", "boot", "--algorithm", "SHA256_RSA4096", "--key", str(KEY),
                    "--rollback_index", str(rollback)], check=True)

def rollback_of(path):
    info = subprocess.run(["avbtool", "info_image", "--image", str(path)], capture_output=True, text=True, check=True).stdout
    return int(next(l for l in info.splitlines() if l.startswith("Rollback Index:")).split(":")[1])

def sign(tmp_path, *extra):
    out = tmp_path / "boot-signed.img"
    subprocess.run([sys.executable, "tools/sign_boot.py", "--stock", str(tmp_path / "stock.img"),
                    *extra, str(tmp_path / "pmos.img"), str(out)], check=True)
    return out

def test_rollback_index_from_stock_footer(tmp_path):
    mkimg(tmp_path / "stock.img", ("13.0.0", "2024-08"), "STOCKBOARD", "0x02000000")
    add_footer(tmp_path / "stock.img", 7)
    mkimg(tmp_path / "pmos.img", ("16.0.0", "2026-11"), "PMOS", "0x01000000")
    assert rollback_of(sign(tmp_path)) == 7

def test_rollback_index_override(tmp_path):
    mkimg(tmp_path / "stock.img", ("13.0.0", "2024-08"), "STOCKBOARD", "0x02000000")
    add_footer(tmp_path / "stock.img", 7)
    mkimg(tmp_path / "pmos.img", ("16.0.0", "2026-11"), "PMOS", "0x01000000")
    assert rollback_of(sign(tmp_path, "--rollback-index", "42")) == 42

def test_rollback_index_zero_without_stock_footer(tmp_path):
    mkimg(tmp_path / "stock.img", ("13.0.0", "2024-08"), "STOCKBOARD", "0x02000000")
    mkimg(tmp_path / "pmos.img", ("16.0.0", "2026-11"), "PMOS", "0x01000000")
    assert rollback_of(sign(tmp_path)) == 0

@pytest.mark.parametrize("which", ["src", "dst"])
def test_rejects_header_version_not_2(tmp_path, which):
    mkimg(tmp_path / "stock.img", ("13.0.0", "2024-08"), "STOCKBOARD", "0x02000000")
    good = (tmp_path / "stock.img").read_bytes()
    bad = bytearray(good); bad[40:44] = struct.pack("<I", 1)
    src, dst = (bytes(bad), bytearray(good)) if which == "src" else (good, bad)
    with pytest.raises(ValueError):
        sign_boot.copy_abl_fields(src, dst)
