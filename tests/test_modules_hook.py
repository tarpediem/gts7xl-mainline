# tests/test_modules_hook.py
"""The initramfs hook that loads the touchscreen module must never block the hooks (the
debug shell starts after them), must wait for telnetd before loading, and must honour
gts7xl.nomodules."""
import subprocess, time
from pathlib import Path
import pytest

HOOK = Path(__file__).parent.parent / "pmaports" / "device" / "testing" / "device-samsung-gts7xl" / "50-gts7xl-modules.sh"
pytestmark = pytest.mark.skipif(not HOOK.exists(), reason="pmaports fork not checked out")


class Rig:
    def __init__(self, tmp_path, telnetd=True, buffyboard=False, modprobe_rc=0):
        self.tmp = tmp_path
        self.bin = tmp_path / "bin"; self.bin.mkdir()
        self.log = tmp_path / "calls.log"
        self.telnetd_flag = tmp_path / "telnetd"
        if telnetd:
            self.telnetd_flag.touch()
        running = {"telnetd": self.telnetd_flag, "buffyboard": tmp_path / "buffy"}
        if buffyboard:
            running["buffyboard"].touch()
        self.cmdline = tmp_path / "cmdline"
        self.cmdline.write_text("console=tty0 pmos.debug-shell\n")
        self._tool("modprobe", f'echo "modprobe $*" >> "{self.log}"; exit {modprobe_rc}')
        self._tool("pgrep", f'for p in "$@"; do case "$p" in telnetd) [ -e "{running["telnetd"]}" ] && exit 0;; '
                            f'buffyboard) [ -e "{running["buffyboard"]}" ] && exit 0;; esac; done; exit 1')
        self._tool("pkill", f'echo "pkill $*" >> "{self.log}"')
        self._tool("buffyboard", f'echo buffyboard >> "{self.log}"')
        self.env = {"PATH": f"{self.bin}:/usr/bin:/bin", "GTS7XL_CMDLINE": str(self.cmdline),
                    "GTS7XL_WAIT": "3", "GTS7XL_POLL": "0.05", "GTS7XL_SETTLE": "0",
                    "GTS7XL_WIRELESS_MODULES": ""}

    def _tool(self, name, body):
        p = self.bin / name
        p.write_text("#!/bin/sh\n" + body + "\n"); p.chmod(0o755)

    def run(self, **env):
        t0 = time.monotonic()
        self.res = subprocess.run(["sh", str(HOOK)], capture_output=True, text=True, env={**self.env, **env})
        self.elapsed = time.monotonic() - t0
        return self

    def calls(self, settle=1.5):
        deadline = time.monotonic() + settle
        while time.monotonic() < deadline:
            time.sleep(0.05)
        return self.log.read_text().splitlines() if self.log.exists() else []


def test_returns_at_once_and_loads_in_background(tmp_path):
    rig = Rig(tmp_path).run()
    assert rig.res.returncode == 0
    assert rig.elapsed < 0.5
    assert rig.calls() == ["modprobe stmfts1b"]


def test_waits_for_telnetd(tmp_path):
    rig = Rig(tmp_path, telnetd=False).run(GTS7XL_WAIT="100")
    assert rig.calls(settle=0.3) == []          # still waiting
    rig.telnetd_flag.touch()
    assert rig.calls() == ["modprobe stmfts1b"]


def test_loads_anyway_after_timeout(tmp_path):
    rig = Rig(tmp_path, telnetd=False).run(GTS7XL_WAIT="10")   # 10 polls of 0.05 s
    assert rig.calls(settle=1.5) == ["modprobe stmfts1b"]


def test_nomodules_on_cmdline(tmp_path):
    rig = Rig(tmp_path)
    rig.cmdline.write_text("console=tty0 gts7xl.nomodules pmos.debug-shell\n")
    rig.run()
    assert rig.res.returncode == 0
    assert rig.calls() == []


def test_restarts_buffyboard(tmp_path):
    rig = Rig(tmp_path, buffyboard=True).run()
    assert rig.calls(settle=2.5) == ["modprobe stmfts1b", "pkill buffyboard", "buffyboard"]


def test_modprobe_failure_is_not_fatal(tmp_path):
    rig = Rig(tmp_path, modprobe_rc=1).run()
    assert rig.res.returncode == 0
    assert rig.calls() == ["modprobe stmfts1b"]


WIRELESS = ["pwrseq_qcom_wcn", "pci_pwrctrl_pwrseq", "ath11k_pci", "qrtr_mhi", "hci_uart"]


def test_default_wireless_modules_in_power_up_order(tmp_path):
    rig = Rig(tmp_path)
    del rig.env["GTS7XL_WIRELESS_MODULES"]
    rig.run()
    assert rig.calls() == ["modprobe stmfts1b"] + [f"modprobe {m}" for m in WIRELESS]


def test_wireless_after_buffyboard_restart(tmp_path):
    rig = Rig(tmp_path, buffyboard=True).run(GTS7XL_WIRELESS_MODULES="ath11k_pci hci_uart")
    assert rig.calls(settle=2.5) == ["modprobe stmfts1b", "pkill buffyboard", "buffyboard",
                                     "modprobe ath11k_pci", "modprobe hci_uart"]


def test_nowireless_on_cmdline(tmp_path):
    rig = Rig(tmp_path)
    rig.cmdline.write_text("console=tty0 gts7xl.nowireless pmos.debug-shell\n")
    rig.run(GTS7XL_WIRELESS_MODULES="ath11k_pci hci_uart")
    assert rig.calls() == ["modprobe stmfts1b"]


def test_nomodules_skips_wireless_too(tmp_path):
    rig = Rig(tmp_path)
    rig.cmdline.write_text("console=tty0 gts7xl.nomodules pmos.debug-shell\n")
    rig.run(GTS7XL_WIRELESS_MODULES="ath11k_pci hci_uart")
    assert rig.calls() == []


def test_initramfs_lists_and_blacklists_wireless():
    pkg = HOOK.parent
    mods = (pkg / "30-gts7xl.modules").read_text().split()
    conf = (pkg / "initramfs-modprobe.conf").read_text()
    for m in WIRELESS:
        assert m in [x.replace("-", "_") for x in mods], m
    for m in ["pwrseq_qcom_wcn", "pci_pwrctrl_pwrseq", "ath11k_pci", "hci_uart"]:
        assert f"blacklist {m}" in conf
    files = (pkg / "30-gts7xl.files").read_text()
    for fw in ["ath11k/QCA6390/hw2.0/amss.bin", "ath11k/QCA6390/hw2.0/m3.bin",
               "ath11k/QCA6390/hw2.0/board-2.bin", "qca/htbtfw20.tlv", "qca/htnv20.bin"]:
        assert f"/lib/firmware/{fw}.zst" in files
