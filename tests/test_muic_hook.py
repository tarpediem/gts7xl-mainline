# tests/test_muic_hook.py
"""The initramfs hook that switches the USB data lines writes to a PMIC: check every byte."""
import os, subprocess
from pathlib import Path
import pytest

HOOK = Path(__file__).parent.parent / "pmaports" / "device" / "testing" / "device-samsung-gts7xl" / "00-gts7xl-usb-muic.sh"
pytestmark = pytest.mark.skipif(not HOOK.exists(), reason="pmaports fork not checked out")

def run_hook(tmp_path, adapters=("9c0000.geniqup/980000.i2c/i2c-0",), fail=False):
    sysfs = tmp_path / "sys"
    for a in adapters:
        (sysfs / "devices/platform/soc@0" / a).mkdir(parents=True)
    bindir = tmp_path / "bin"; bindir.mkdir()
    log = tmp_path / "calls.log"
    (bindir / "i2ctransfer").write_text(f'#!/bin/sh\necho "$*" >> "{log}"\nexit {1 if fail else 0}\n')
    (bindir / "i2ctransfer").chmod(0o755)
    res = subprocess.run(["sh", str(HOOK)], capture_output=True, text=True,
                         env={"PATH": f"{bindir}:/usr/bin:/bin", "MUIC_SYSFS": str(sysfs)})
    calls = log.read_text().splitlines() if log.exists() else []
    return res, calls

def test_sends_exactly_the_vendor_com_usb_sequence(tmp_path):
    """OPCODE_WRITE (0x21) <- COMMAND_CONTROL1_WRITE (0x06), COM_USB (0x09); then OPCODE_WRITE_END (0x41) <- 0."""
    res, calls = run_hook(tmp_path)
    assert res.returncode == 0
    assert calls == ["-f -y 0 w3@0x25 0x21 0x06 0x09", "-f -y 0 w2@0x25 0x41 0x00"]
    assert "switched to the SoC (i2c-0)" in res.stdout

def test_uses_the_bus_number_the_kernel_gave_to_i2c_980000(tmp_path):
    _, calls = run_hook(tmp_path, adapters=("9c0000.geniqup/980000.i2c/i2c-7",))
    assert [c.split()[2] for c in calls] == ["7", "7"]

def test_other_buses_are_never_written(tmp_path):
    res, calls = run_hook(tmp_path, adapters=("9c0000.geniqup/984000.i2c/i2c-1", "ac0000.geniqup/a84000.i2c/i2c-9"))
    assert calls == [] and res.returncode == 0
    assert "not found" in res.stdout

def test_a_failed_write_stops_the_sequence_and_is_reported(tmp_path):
    res, calls = run_hook(tmp_path, fail=True)
    assert calls == ["-f -y 0 w3@0x25 0x21 0x06 0x09"]          # no WRITE_END after a failed command
    assert "failed" in res.stdout and res.returncode == 0       # never stops the boot

def test_no_noise_when_kmsg_is_not_writable(tmp_path):
    res, _ = run_hook(tmp_path)
    assert res.stderr == "" or os.geteuid() == 0
