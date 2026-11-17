# tests/test_bt_addr.py
"""gts7xl-bt-addr: hci0 gets a stable, locally administered unicast address derived from
/etc/machine-id, set with btmgmt public-addr once hci_qca setup is done; bounded wait, it
never fails the boot."""
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


UNCONF = "hci0:\tUnconfigured controller\n\tmanufacturer 29\n\tsupported options: public-address \n\tmissing options: public-address "


def run(tmp, mid=MID, hci=True, info="", ready_after=0, cfg=UNCONF, fail_set=0, wait="2"):
    """Fake btmgmt: `info` prints `info` (empty = index not configured, exit 1); `config`
    fails with Invalid Index for the first `ready_after` calls (hci_qca setup still running),
    then prints `cfg`; `public-addr` fails `fail_set` times, then succeeds."""
    bin_ = tmp / "bin"; bin_.mkdir(exist_ok=True)
    log = tmp / "btmgmt.log"
    st = tmp / "state"; st.mkdir(exist_ok=True)
    (st / "cfg").write_text(cfg)
    (bin_ / "btmgmt").write_text(f"""#!/bin/sh
echo "$*" >> "{log}"
st="{st}"
bump() {{ n=$(cat "$st/$1" 2>/dev/null || echo 0); echo $((n + 1)) > "$st/$1"; echo "$n"; }}
case "$3" in
info) [ -n "{info}" ] && {{ printf "%s\\n" "{info}"; exit 0; }}; echo "Invalid Index" >&2; exit 1 ;;
config) [ "$(bump config)" -lt {ready_after} ] && {{ echo "Invalid Index" >&2; exit 1; }}; cat "$st/cfg"; exit 0 ;;
public-addr) [ "$(bump set)" -lt {fail_set} ] && exit 1; exit 0 ;;
esac
exit 0
""")
    (bin_ / "btmgmt").chmod(0o755)
    (tmp / "machine-id").write_text(mid + "\n")
    sysfs = tmp / "sys"
    if hci:
        (sysfs / "class/bluetooth/hci0").mkdir(parents=True, exist_ok=True)
    env = {"PATH": f"{bin_}:/usr/bin:/bin", "GTS7XL_MACHINE_ID": str(tmp / "machine-id"),
           "GTS7XL_SYSFS": str(sysfs), "GTS7XL_WAIT": wait, "GTS7XL_POLL": "0.05"}
    res = subprocess.run(["sh", str(SCRIPT)], capture_output=True, text=True, env=env, timeout=30)
    calls = log.read_text().splitlines() if log.exists() else []
    return res, calls


def test_sets_derived_address(tmp_path):
    res, calls = run(tmp_path)
    assert res.returncode == 0
    a = expected(MID)
    assert calls == ["--index 0 info", "--index 0 config", f"--index 0 public-addr {a}"]
    assert f"hci0 address set to {a}" in res.stdout
    first = int(a[:2], 16)
    assert first & 0x02 and not first & 0x01      # locally administered, unicast


def test_waits_for_setup_to_end(tmp_path):
    """The boot failure: hci0 exists in sysfs but mgmt has no index 0 yet (Invalid Index).
    The address is set only once config reports it missing."""
    res, calls = run(tmp_path, ready_after=5)
    a = expected(MID)
    assert res.returncode == 0
    assert calls.count("--index 0 config") == 6
    assert calls[-1] == f"--index 0 public-addr {a}"
    assert sum(c.startswith("--index 0 public-addr") for c in calls) == 1


def test_retries_a_failed_set(tmp_path):
    res, calls = run(tmp_path, fail_set=2)
    assert res.returncode == 0
    assert sum(c.startswith("--index 0 public-addr") for c in calls) == 3
    assert "address set to" in res.stdout


def test_gives_up_bounded(tmp_path):
    res, calls = run(tmp_path, ready_after=10**6, wait="1")
    assert res.returncode == 0
    assert not any(c.startswith("--index 0 public-addr") for c in calls)
    assert "not ready for an address" in res.stdout


def test_stable_and_distinct(tmp_path):
    (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir(); (tmp_path / "c").mkdir()
    _, c1 = run(tmp_path / "a")
    _, c2 = run(tmp_path / "b")
    _, c3 = run(tmp_path / "c", mid="f" * 32)
    assert c1 == c2 and c1[-1] != c3[-1]


def test_already_set(tmp_path):
    res, calls = run(tmp_path, info=f"\taddr {expected(MID)} version 11")
    assert res.returncode == 0 and calls == ["--index 0 info"]


def test_configured_other_address(tmp_path):
    res, calls = run(tmp_path, info="\taddr 00:11:22:33:44:55 version 11")
    assert res.returncode == 0
    assert calls == ["--index 0 info", f"--index 0 public-addr {expected(MID)}"]


@pytest.mark.parametrize("mid", ["", "uninitialized"])
def test_no_machine_id(tmp_path, mid):
    res, calls = run(tmp_path, mid=mid)
    assert res.returncode == 0 and calls == []


def test_no_hci0(tmp_path):
    res, calls = run(tmp_path, hci=False, wait="1")
    assert res.returncode == 0 and calls == [] and "no hci0" in res.stdout
