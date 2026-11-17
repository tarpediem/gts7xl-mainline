# tests/test_xz_ramdisk.py
"""tools/xz_ramdisk.py: same cpio in an xz ramdisk, header fields and the other sections
unchanged, kernel-friendly xz (crc32 check), deterministic."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import xz_ramdisk  # noqa: E402

pytestmark = pytest.mark.skipif(
    not all(shutil.which(t) for t in ("mkbootimg", "unpack_bootimg", "xz", "zstd", "cpio")),
    reason="mkbootimg/unpack_bootimg/xz/zstd/cpio not installed")


def make_boot(tmp_path):
    root = tmp_path / "root"
    (root / "etc").mkdir(parents=True)
    (root / "etc" / "hello").write_text("hello\n" * 2000)
    cpio = subprocess.run("find . | cpio -o -H newc --quiet", shell=True, cwd=root,
                          check=True, capture_output=True).stdout
    rd = tmp_path / "rd.zst"
    rd.write_bytes(subprocess.run(["zstd", "-q", "-c"], input=cpio, check=True, capture_output=True).stdout)
    (tmp_path / "k").write_bytes(b"KERNEL" * 1000)
    (tmp_path / "d").write_bytes(b"DTB" * 300)
    boot = tmp_path / "boot.img"
    subprocess.run(["mkbootimg", "--header_version", "2", "--kernel", str(tmp_path / "k"),
                    "--ramdisk", str(rd), "--dtb", str(tmp_path / "d"), "--pagesize", "4096",
                    "--base", "0", "--kernel_offset", "0x8000", "--ramdisk_offset", "0x2000000",
                    "--tags_offset", "0x1e00000", "--dtb_offset", "0x1f00000",
                    "--cmdline", "console=tty0 pmos_boot_uuid=1234", "--output", str(boot)], check=True)
    return boot, cpio


def info(img, where):
    return xz_ramdisk.unpack(img, where)


def test_recompresses_same_cpio(tmp_path):
    boot, cpio = make_boot(tmp_path)
    out = tmp_path / "out.img"
    xz_ramdisk.main([str(boot), str(out)])
    a, b = info(boot, tmp_path / "a"), info(out, tmp_path / "b")
    rd = Path(b.pop("--ramdisk")).read_bytes()
    a.pop("--ramdisk")
    for k in ("--kernel", "--dtb"):
        assert Path(a.pop(k)).read_bytes() == Path(b.pop(k)).read_bytes()
    assert a == b                                     # header fields, cmdline
    assert rd.startswith(b"\xfd7zXZ\x00")
    assert rd[6:8] == b"\x00\x01"                     # stream flags: CRC32 check
    assert subprocess.run(["xz", "-dc"], input=rd, capture_output=True, check=True).stdout == cpio


def test_deterministic(tmp_path):
    boot, _ = make_boot(tmp_path)
    xz_ramdisk.main([str(boot), str(tmp_path / "1.img")])
    xz_ramdisk.main([str(boot), str(tmp_path / "2.img")])
    assert (tmp_path / "1.img").read_bytes() == (tmp_path / "2.img").read_bytes()
