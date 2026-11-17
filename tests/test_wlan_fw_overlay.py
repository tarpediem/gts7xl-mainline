# tests/test_wlan_fw_overlay.py
"""tools/wlan-fw-overlay.py: board-2.bin round trip, the added entry, and a cpio that
GNU cpio can list and extract."""
import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

TOOL = Path(__file__).parent.parent / "tools" / "wlan-fw-overlay.py"
spec = importlib.util.spec_from_file_location("wlan_fw_overlay", TOOL)
ov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ov)


def sample():
    return ov.build_board2([(["bus=pci,qmi-chip-id=0,qmi-board-id=255"], b"A" * 13),
                            (["bus=pci,qmi-chip-id=0,qmi-board-id=4"], b"B" * 8)])


def test_round_trip():
    entries = ov.parse_board2(sample())
    assert entries == [(["bus=pci,qmi-chip-id=0,qmi-board-id=255"], b"A" * 13),
                       (["bus=pci,qmi-chip-id=0,qmi-board-id=4"], b"B" * 8)]
    assert ov.build_board2(entries) == sample()


def test_rejects_other_files():
    with pytest.raises(ValueError):
        ov.parse_board2(b"\x7fELF" + b"\0" * 40)


def test_adds_entry_and_writes_cpio(tmp_path):
    (tmp_path / "board-2.bin").write_bytes(sample())
    (tmp_path / "bdwlan.elf").write_bytes(b"\x7fELF" + b"C" * 9)
    (tmp_path / "nvm").write_bytes(b"nvm")
    out = tmp_path / "o.cpio"
    ov.main(["--board-2", str(tmp_path / "board-2.bin"), "--bdf", str(tmp_path / "bdwlan.elf"),
             "--name", "bus=pci,qmi-chip-id=2,qmi-board-id=5",
             "--file", f"{tmp_path / 'nvm'}:/lib/firmware/qca/htnv20.bin", "-o", str(out)])
    assert out.stat().st_mode & 0o777 == 0o600
    if shutil.which("cpio") is None:
        pytest.skip("no cpio")
    x = tmp_path / "x"
    x.mkdir()
    subprocess.run(["cpio", "-idm", "--quiet"], input=out.read_bytes(), cwd=x, check=True)
    b2 = x / "usr/lib/firmware/ath11k/QCA6390/hw2.0/board-2.bin"
    entries = ov.parse_board2(b2.read_bytes())
    assert entries[-1] == (["bus=pci,qmi-chip-id=2,qmi-board-id=5"], b"\x7fELF" + b"C" * 9)
    assert len(entries) == 3
    assert (x / "lib/firmware/qca/htnv20.bin").read_bytes() == b"nvm"


def test_refuses_existing_name(tmp_path):
    (tmp_path / "board-2.bin").write_bytes(sample())
    (tmp_path / "b").write_bytes(b"x")
    with pytest.raises(SystemExit):
        ov.main(["--board-2", str(tmp_path / "board-2.bin"), "--bdf", str(tmp_path / "b"),
                 "--name", "bus=pci,qmi-chip-id=0,qmi-board-id=4", "-o", str(tmp_path / "o")])


def test_real_linux_firmware_round_trip():
    real = Path("/usr/lib/firmware/ath11k/QCA6390/hw2.0/board-2.bin.zst")
    if not real.exists() or shutil.which("zstd") is None:
        pytest.skip("no linux-firmware board-2.bin on this host")
    data = ov.read_maybe_zst(str(real))
    entries = ov.parse_board2(data)
    rebuilt = ov.build_board2(entries)
    # same length and entries (bdencoder pads with arbitrary bytes, we pad with zeros)
    assert len(rebuilt) == len(data)
    assert ov.parse_board2(rebuilt) == entries
    assert all(bdf for _, bdf in entries)
