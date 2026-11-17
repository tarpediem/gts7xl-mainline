# tests/test_bt_addr.py
"""gts7xl-bt-addr: hci0 gets a stable, locally administered unicast address derived from
/etc/machine-id, set with btmgmt public-addr; it never fails the boot."""
import hashlib, subprocess
from pathlib import Path
import pytest

SCRIPT = Path(__file__).parent.parent / "pmaports" / "device" / "testing" / "device-samsung-gts7xl" / "gts7xl-bt-addr.sh"
pytestmark = pytest.mark.skipif(not SCRIPT.exists(), reason="pmaports fork not checked out")
MID = "0123456789abcdef0123456789abcdef"


def expected(mid):
    h = bytearray(hashlib.sha256(f"gts7xl-bt-addr:{mid}".encode()).digest()[:6])
    h[0] = (h[0] & 0xFC) | 0x02
    return ":".join(f"{b:02X}" for b in h)


def run(tmp, mid=MID, hci=True, info=""):
    bin_ = tmp / "bin"; bin_.mkdir(exist_ok=True)
    log = tmp / "btmgmt.log"
    (bin_ / "btmgmt").write_text(f'#!/bin/sh\necho "$*" >> "{log}"\n'
                                 f'[ "$3" = info ] && printf "%s\\n" "{info}"\nexit 0\n')
    (bin_ / "btmgmt").chmod(0o755)
    (tmp / "machine-id").write_text(mid + "\n")
    sysfs = tmp / "sys"
    if hci:
        (sysfs / "class/bluetooth/hci0").mkdir(parents=True, exist_ok=True)
    env = {"PATH": f"{bin_}:/usr/bin:/bin", "GTS7XL_MACHINE_ID": str(tmp / "machine-id"),
           "GTS7XL_SYSFS": str(sysfs), "GTS7XL_WAIT": "2", "GTS7XL_POLL": "0.05"}
    res = subprocess.run(["sh", str(SCRIPT)], capture_output=True, text=True, env=env)
    calls = log.read_text().splitlines() if log.exists() else []
    return res, calls


def test_sets_derived_address(tmp_path):
    res, calls = run(tmp_path)
    assert res.returncode == 0
    a = expected(MID)
    assert calls == ["--index 0 info", f"--index 0 public-addr {a}"]
    first = int(a[:2], 16)
    assert first & 0x02 and not first & 0x01      # locally administered, unicast


def test_stable_and_distinct(tmp_path):
    (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir(); (tmp_path / "c").mkdir()
    _, c1 = run(tmp_path / "a")
    _, c2 = run(tmp_path / "b")
    _, c3 = run(tmp_path / "c", mid="f" * 32)
    assert c1 == c2 and c1[-1] != c3[-1]


def test_already_set(tmp_path):
    res, calls = run(tmp_path, info=f"\taddr {expected(MID)} version 11")
    assert res.returncode == 0 and calls == ["--index 0 info"]


@pytest.mark.parametrize("mid", ["", "uninitialized"])
def test_no_machine_id(tmp_path, mid):
    res, calls = run(tmp_path, mid=mid)
    assert res.returncode == 0 and calls == []


def test_no_hci0(tmp_path):
    res, calls = run(tmp_path, hci=False)
    assert res.returncode == 0 and calls == [] and "no hci0" in res.stdout
