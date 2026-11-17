# tests/test_muic_hook.py
"""The initramfs hook that switches the USB data lines writes to a PMIC: check every byte.
It also waits for the i2c bus and the UDC, then binds the gadget if the initramfs could not."""
import os, subprocess, threading, time
from pathlib import Path
import pytest

HOOK = Path(__file__).parent.parent / "pmaports" / "device" / "testing" / "device-samsung-gts7xl" / "00-gts7xl-usb-muic.sh"
pytestmark = pytest.mark.skipif(not HOOK.exists(), reason="pmaports fork not checked out")

ADAPTER = "9c0000.geniqup/980000.i2c/i2c-0"
# Stand-in for /init_functions.sh: same names, same contract, every call logged.
FUNCTIONS = '''
CONFIGFS="{configfs}"
setup_usb_configfs_udc() {{ echo setup_usb_configfs_udc >> "{flog}"; ls "{sysfs}/class/udc" | head -1 > "$CONFIGFS/g1/UDC"; }}
setup_usb_network_configfs() {{ echo setup_usb_network_configfs >> "{flog}"; mkdir -p "$CONFIGFS/g1"; setup_usb_configfs_udc; }}
start_unudhcpd() {{ echo "start_unudhcpd udc=$(cat "$CONFIGFS/g1/UDC")" >> "{flog}"; }}
'''

class Rig:
    def __init__(self, tmp_path, fail=False):
        self.sysfs = tmp_path / "sys"
        self.configfs = tmp_path / "config" / "usb_gadget"
        (self.sysfs / "class" / "udc").mkdir(parents=True)
        (self.sysfs / "devices/platform/soc@0").mkdir(parents=True)
        self.configfs.mkdir(parents=True)
        bindir = tmp_path / "bin"; bindir.mkdir()
        self.i2c_log, self.flog = tmp_path / "calls.log", tmp_path / "functions.log"
        (bindir / "i2ctransfer").write_text(f'#!/bin/sh\necho "$*" >> "{self.i2c_log}"\nexit {1 if fail else 0}\n')
        (bindir / "i2ctransfer").chmod(0o755)
        self.functions = tmp_path / "init_functions.sh"
        self.functions.write_text(FUNCTIONS.format(configfs=self.configfs, flog=self.flog, sysfs=self.sysfs))
        self.env = {"PATH": f"{bindir}:/usr/bin:/bin", "MUIC_SYSFS": str(self.sysfs),
                    "MUIC_INIT_FUNCTIONS": str(self.functions), "MUIC_WAIT": "3", "MUIC_POLL": "0.05"}

    def add_adapter(self, a=ADAPTER):
        (self.sysfs / "devices/platform/soc@0" / a).mkdir(parents=True)

    def add_udc(self, name="a600000.usb"):
        (self.sysfs / "class" / "udc" / name).mkdir()

    def gadget(self, udc=""):
        """The gadget as the initramfs leaves it: created, bound to `udc` or to nothing."""
        (self.configfs / "g1").mkdir()
        (self.configfs / "g1" / "UDC").write_text(udc + "\n" if udc else "")

    def later(self, delay, fn):
        t = threading.Timer(delay, fn); t.start(); return t

    def run(self, **env):
        t0 = time.monotonic()
        self.res = subprocess.run(["sh", str(HOOK)], capture_output=True, text=True, env={**self.env, **env})
        self.elapsed = time.monotonic() - t0
        self.calls = self.i2c_log.read_text().splitlines() if self.i2c_log.exists() else []
        self.fcalls = self.flog.read_text().splitlines() if self.flog.exists() else []
        return self

def ready(tmp_path, **kw):
    """Everything there from the start, gadget already bound by the initramfs."""
    rig = Rig(tmp_path, **kw); rig.add_adapter(); rig.add_udc(); rig.gadget("a600000.usb")
    return rig

SEQUENCE = ["-f -y 0 w3@0x25 0x21 0x06 0x09", "-f -y 0 w2@0x25 0x41 0x00"]

def test_sends_exactly_the_vendor_com_usb_sequence(tmp_path):
    """OPCODE_WRITE (0x21) <- COMMAND_CONTROL1_WRITE (0x06), COM_USB (0x09); then OPCODE_WRITE_END (0x41) <- 0."""
    rig = ready(tmp_path).run()
    assert rig.res.returncode == 0
    assert rig.calls == SEQUENCE
    assert "switched to the SoC (i2c-0" in rig.res.stdout

def test_uses_the_bus_number_the_kernel_gave_to_i2c_980000(tmp_path):
    rig = Rig(tmp_path); rig.add_adapter("9c0000.geniqup/980000.i2c/i2c-7"); rig.add_udc(); rig.gadget("a600000.usb")
    assert [c.split()[2] for c in rig.run().calls] == ["7", "7"]

def test_other_buses_are_never_written(tmp_path):
    rig = Rig(tmp_path); rig.add_udc(); rig.gadget("a600000.usb")
    rig.add_adapter("9c0000.geniqup/984000.i2c/i2c-1"); rig.add_adapter("ac0000.geniqup/a84000.i2c/i2c-9")
    rig.run()
    assert rig.calls == [] and rig.res.returncode == 0
    assert "not found" in rig.res.stdout

def test_a_failed_write_stops_the_sequence_and_is_reported(tmp_path):
    rig = ready(tmp_path, fail=True).run()
    assert rig.calls == SEQUENCE[:1]                                   # no WRITE_END after a failed command
    assert "failed" in rig.res.stdout and rig.res.returncode == 0      # never stops the boot

def test_no_noise_when_kmsg_is_not_writable(tmp_path):
    rig = ready(tmp_path).run()
    assert rig.res.stderr == "" or os.geteuid() == 0

def test_nothing_to_do_does_not_wait_and_leaves_the_gadget_alone(tmp_path):
    rig = ready(tmp_path).run(MUIC_WAIT="30", MUIC_POLL="1")
    assert rig.elapsed < 0.9
    assert rig.fcalls == ["start_unudhcpd udc=a600000.usb"]           # no rebind; DHCP start is a no-op if running
    assert "already bound" in rig.res.stdout

def test_waits_for_a_late_i2c_adapter(tmp_path):
    rig = Rig(tmp_path); rig.add_udc(); rig.gadget("a600000.usb")
    t = rig.later(0.3, rig.add_adapter)
    rig.run(MUIC_WAIT="100"); t.join()
    assert rig.calls == SEQUENCE                                       # written once, not once per poll
    assert 0.25 < rig.elapsed < 3

def test_late_udc_with_no_gadget_creates_it_and_starts_dhcp(tmp_path):
    """The initramfs found no UDC and created nothing: the hook does the whole gadget setup."""
    rig = Rig(tmp_path); rig.add_adapter()
    t = rig.later(0.3, rig.add_udc)
    rig.run(MUIC_WAIT="100"); t.join()
    assert rig.calls == SEQUENCE
    assert rig.fcalls == ["setup_usb_network_configfs", "setup_usb_configfs_udc", "start_unudhcpd udc=a600000.usb"]
    assert "gadget bound to: a600000.usb" in rig.res.stdout

def test_unbound_gadget_is_rebound(tmp_path):
    rig = Rig(tmp_path); rig.add_adapter(); rig.add_udc(); rig.gadget("")
    rig.run()
    assert rig.fcalls == ["setup_usb_configfs_udc", "start_unudhcpd udc=a600000.usb"]

def test_gives_up_after_the_bound_and_says_what_is_missing(tmp_path):
    rig = Rig(tmp_path).run(MUIC_WAIT="4")
    assert rig.res.returncode == 0 and rig.calls == [] and rig.fcalls == []
    assert "adapter not found after 4s" in rig.res.stdout and "no UDC after 4s" in rig.res.stdout
    assert rig.elapsed < 2

def test_udc_without_i2c_still_gets_a_gadget(tmp_path):
    rig = Rig(tmp_path); rig.add_udc()
    rig.run()
    assert rig.calls == [] and rig.fcalls[-1] == "start_unudhcpd udc=a600000.usb"
    assert "not found" in rig.res.stdout and "no UDC" not in rig.res.stdout

def test_default_bound_is_30_polls_of_one_second():
    text = HOOK.read_text()
    assert 'tries="${MUIC_WAIT:-30}"' in text and 'poll="${MUIC_POLL:-1}"' in text

def test_only_address_0x25_is_ever_written():
    writes = [l for l in HOOK.read_text().splitlines() if "i2ctransfer" in l and not l.lstrip().startswith("#")]
    assert len(writes) == 2 and all("@0x25 " in l for l in writes)
