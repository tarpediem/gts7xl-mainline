# tests/test_powerkey_hook.py
"""The initramfs power-key hook: a short press toggles fb0 blank and the touchscreen
inhibit, a long press does nothing, other events are ignored, the hook returns at once.

Runs the hook on a fake /sys and a regular file of 24-byte arm64 input_event records.
With the pmbootstrap native chroot present, the hook runs under its busybox (ash, dd, od:
the same tools as on the tablet); otherwise under the host sh."""
import os, struct, subprocess, time
from pathlib import Path
import pytest

HOOK = Path(__file__).parent.parent / "pmaports" / "device" / "testing" / "device-samsung-gts7xl" / "60-gts7xl-powerkey.sh"
pytestmark = pytest.mark.skipif(not HOOK.exists(), reason="pmaports fork not checked out")

NATIVE = Path(os.environ.get("PMB_NATIVE", Path.home() / ".local/var/pmbootstrap/chroot_native"))
LDSO = NATIVE / "lib" / "ld-musl-x86_64.so.1"
BUSYBOX = NATIVE / "bin" / "busybox"

EV_SYN, EV_KEY = 0, 1
KEY_POWER, KEY_VOLUMEDOWN = 116, 114
TOUCH = "STM FTS1BA90A Touchscreen"


def ev(t, type_, code, value):
    sec = int(t)
    usec = int(round((t - sec) * 1e6))
    return struct.pack("<QQHHi", sec, usec, type_, code, value)


def press(t, held, code=KEY_POWER):
    return (ev(t, EV_KEY, code, 1) + ev(t, EV_SYN, 0, 0)
            + ev(t + held, EV_KEY, code, 0) + ev(t + held, EV_SYN, 0, 0))


class Rig:
    def __init__(self, tmp_path, touch=True):
        self.tmp = tmp_path
        self.sys = tmp_path / "sys"
        self.dev = tmp_path / "dev"; self.dev.mkdir()
        self._input("input0", "gpio-keys", "event0")
        self._input("input1", "pm8941_pwrkey", "event1")
        self._input("input4", "pm8941_resin", "event4")
        if touch:
            self.inhibited = self._input("input2", TOUCH, "event2") / "inhibited"
            self.inhibited.write_text("0\n")
        fb = self.sys / "class" / "graphics" / "fb0"; fb.mkdir(parents=True)
        self.blank = fb / "blank"; self.blank.write_text("0\n")
        self.cmdline = tmp_path / "cmdline"
        self.cmdline.write_text("console=tty0 pmos.debug-shell\n")
        self.events = self.dev / "event1"
        self.env = {"GTS7XL_SYSFS": str(self.sys), "GTS7XL_DEVINPUT": str(self.dev),
                    "GTS7XL_CMDLINE": str(self.cmdline), "GTS7XL_WAIT": "2", "GTS7XL_POLL": "0.05",
                    "GTS7XL_EOF_EXIT": "1", "GTS7XL_FOREGROUND": "1"}
        self.shell = ["sh"]
        self.env["PATH"] = "/usr/bin:/bin"
        if LDSO.exists() and BUSYBOX.exists():
            bb = tmp_path / "bb"; bb.mkdir()
            for applet in ("sh", "dd", "od", "cat", "grep", "sleep"):
                p = bb / applet
                p.write_text(f'#!/bin/sh\nexec "{LDSO}" "{BUSYBOX}" {applet} "$@"\n'); p.chmod(0o755)
            self.shell = [str(LDSO), str(BUSYBOX), "sh"]
            self.env["PATH"] = f"{bb}:/usr/bin:/bin"

    def _input(self, inp, name, event):
        d = self.sys / "class" / "input" / inp
        (d / event).mkdir(parents=True)
        (d / "name").write_text(name + "\n")
        return d

    def run(self, data, **env):
        self.events.write_bytes(data)
        t0 = time.monotonic()
        self.res = subprocess.run(self.shell + [str(HOOK)], capture_output=True, text=True,
                                  env={**self.env, **env}, timeout=30)
        self.elapsed = time.monotonic() - t0
        return self

    def lines(self):
        return [l.removeprefix("gts7xl-powerkey: ") for l in self.res.stdout.splitlines()
                if not l.startswith("gts7xl-powerkey: watching")]

    def state(self):
        inh = self.inhibited.read_text().strip() if hasattr(self, "inhibited") else None
        return self.blank.read_text().strip(), inh


@pytest.mark.skipif(not BUSYBOX.exists(), reason="no pmbootstrap native chroot")
def test_runs_under_busybox(tmp_path):
    rig = Rig(tmp_path)
    assert rig.shell[-2:] == [str(BUSYBOX), "sh"]


def test_short_press_turns_off(tmp_path):
    rig = Rig(tmp_path).run(press(100.25, 0.2))
    assert rig.res.returncode == 0, rig.res.stderr
    assert rig.lines() == ["display off"]
    assert rig.state() == ("1", "1")


def test_second_short_press_turns_on(tmp_path):
    rig = Rig(tmp_path).run(press(100.0, 0.15) + press(105.9, 0.3))
    assert rig.lines() == ["display off", "display on"]
    assert rig.state() == ("0", "0")


def test_long_press_ignored(tmp_path):
    rig = Rig(tmp_path).run(press(100.9, 3.2) + press(200.0, 2.95))
    assert rig.lines()[0].startswith("long press (32")
    assert rig.lines()[1:] == ["display off"]          # 2.95 s is still short


def test_held_across_second_boundary(tmp_path):
    # 0.4 s press from x.8 to y.2: the usec part must be used
    rig = Rig(tmp_path).run(press(99.8, 0.4))
    assert rig.lines() == ["display off"]


def test_other_keys_ignored(tmp_path):
    data = press(100.0, 0.1, KEY_VOLUMEDOWN) + ev(101.0, EV_SYN, 0, 0) + ev(102.0, 4, 4, 116)
    rig = Rig(tmp_path).run(data)
    assert rig.lines() == []
    assert rig.state() == ("0", "0")


def test_release_without_press_ignored(tmp_path):
    rig = Rig(tmp_path).run(ev(100.0, EV_KEY, KEY_POWER, 0) + press(101.0, 0.1))
    assert rig.lines() == ["display off"]


def test_without_touchscreen(tmp_path):
    rig = Rig(tmp_path, touch=False).run(press(100.0, 0.1))
    assert rig.lines() == ["no touchscreen, display only", "display off"]
    assert rig.blank.read_text().strip() == "1"


def test_nopowerkey_on_cmdline(tmp_path):
    rig = Rig(tmp_path)
    rig.cmdline.write_text("console=tty0 gts7xl.nopowerkey\n")
    rig.run(press(100.0, 0.1))
    assert rig.res.returncode == 0
    assert rig.state() == ("0", "0")


def test_no_pwrkey_device(tmp_path):
    rig = Rig(tmp_path)
    (rig.sys / "class" / "input" / "input1" / "name").write_text("something else\n")
    rig.run(b"", GTS7XL_WAIT="3")
    assert rig.res.returncode == 1
    assert "no pm8941_pwrkey input device" in rig.res.stdout


def test_hook_returns_at_once(tmp_path):
    rig = Rig(tmp_path)
    rig.env.pop("GTS7XL_FOREGROUND")
    rig.run(press(100.0, 0.1))
    assert rig.res.returncode == 0
    assert rig.elapsed < 1.0
    deadline = time.monotonic() + 5
    while rig.blank.read_text().strip() != "1" and time.monotonic() < deadline:
        time.sleep(0.05)
    assert rig.state() == ("1", "1")
