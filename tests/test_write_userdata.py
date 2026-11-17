# tests/test_write_userdata.py
"""tools/write-userdata.sh against a fake usbsh (no tablet): it must refuse every target
that is not exactly the userdata partition it expects, write only after the typed
confirmation, and verify the write by reading it back."""
import hashlib, json, os, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "tools" / "write-userdata.sh"
FAKE = Path(__file__).parent / "fake_usbsh.py"
DEV_SIZE = 256 * 1024          # 512 sysfs sectors
GOOD = "dev=sda37 parent=sda size=512 start=8 ro=0 lbs=4096 holders=0 used=0\ncount=1"
PIT = """--- Entry #36 ---
Partition Block Size/Offset: 1
Partition Block Count: 0
Partition Name: USERDATA
Flash Filename: userdata.img

--- Entry #37 ---
Partition Block Size/Offset: 9999
Partition Block Count: 1
Partition Name: OTHER
"""


def make_image(path, size=64 * 1024, gpt_at=4096):
    data = bytearray(os.urandom(size))
    data[512:520] = b"\0" * 8
    data[4096:4104] = b"\0" * 8
    if gpt_at is not None:
        data[gpt_at:gpt_at + 8] = b"EFI PART"
    path.write_bytes(bytes(data))
    return bytes(data)


class Rig:
    def __init__(self, tmp, resolve=(GOOD,), fail="", tools="tools=checked", image_kw=None):
        self.tmp = tmp
        self.fake = tmp / "fake"; self.fake.mkdir()
        self.dev = tmp / "dev.bin"
        self.dev.write_bytes(b"\xaa" * DEV_SIZE)
        self.image = tmp / "rootfs.img"
        self.data = make_image(self.image, **(image_kw or {}))
        self.pit = tmp / "gts7xl.pit"; self.pit.write_text(PIT)
        self.notes = tmp / "NOTES.md"; self.notes.write_text("# notes\n")
        (self.fake / "config.json").write_text(json.dumps({
            "resolve": list(resolve), "tools": tools, "dev": str(self.dev),
            "devname": "sda37", "fail": fail}))

    def run(self, *extra, answer="ERASE-USERDATA\n"):
        env = {**os.environ, "FAKE_DIR": str(self.fake), "WRITE_USERDATA_POLL": "0.1",
               "WRITE_USERDATA_USBSH": f"{sys.executable} {FAKE}"}
        self.res = subprocess.run(
            ["bash", str(SCRIPT), "--image", str(self.image), "--pit", str(self.pit),
             "--notes", str(self.notes), "--local-ip", "127.0.0.1", *extra],
            input=answer, capture_output=True, text=True, env=env, timeout=120)
        return self

    def calls(self):
        log = self.fake / "calls.log"
        return log.read_text().splitlines() if log.exists() else []

    def wrote(self):
        return any(c.startswith(": wu-write") for c in self.calls())

    def untouched(self):
        return self.dev.read_bytes() == b"\xaa" * DEV_SIZE


def test_dry_run_resolves_and_writes_nothing(tmp_path):
    r = Rig(tmp_path).run("--dry-run", answer="")
    assert r.res.returncode == 0, r.res.stderr
    assert "/dev/sda37" in r.res.stdout and "dry run: nothing written" in r.res.stdout
    assert hashlib.sha256(r.data).hexdigest() in r.res.stdout
    assert not r.wrote() and r.untouched()
    assert r.notes.read_text() == "# notes\n"


def test_writes_after_confirmation_and_verifies(tmp_path):
    r = Rig(tmp_path).run()
    assert r.res.returncode == 0, r.res.stderr
    dev = r.dev.read_bytes()
    assert dev[:len(r.data)] == r.data
    assert dev[len(r.data):] == b"\xaa" * (DEV_SIZE - len(r.data))
    calls = [c.split(";")[0] for c in r.calls()]
    assert calls == [": wu-resolve", ": wu-tools", ": wu-resolve", ": wu-write",
                     ": wu-poll", ": wu-readback"]
    write = next(c for c in r.calls() if c.startswith(": wu-write"))
    assert "dd of=/dev/sda37 bs=4M conv=fsync" in write and "set -o pipefail" in write
    notes = r.notes.read_text()
    assert "userdata write" in notes and "result: OK" in notes
    assert hashlib.sha256(r.data).hexdigest() in notes


def test_expect_sha256(tmp_path):
    r = Rig(tmp_path)
    r.run("--expect-sha256", "0" * 64)
    assert r.res.returncode == 1 and "not the expected" in r.res.stderr
    assert r.calls() == []
    r.run("--expect-sha256", hashlib.sha256(r.data).hexdigest().upper(), "--dry-run")
    assert r.res.returncode == 0, r.res.stderr


@pytest.mark.parametrize("answer", ["", "yes\n", "erase-userdata\n", "ERASE-USERDATA \n"])
def test_needs_the_exact_word(tmp_path, answer):
    r = Rig(tmp_path).run(answer=answer)
    assert r.res.returncode == 1 and "not confirmed" in r.res.stderr
    assert not r.wrote() and r.untouched()


@pytest.mark.parametrize("resolve, msg", [
    ("count=0", "found '0'"),
    (GOOD.replace("count=1", "dev=sdb5 parent=sdb size=512 start=8 ro=0 lbs=4096 holders=0 used=0\ncount=2"),
     "found '2'"),
    ("dev=sdb37 parent=sdb size=512 start=8 ro=0 lbs=4096 holders=0 used=0\ncount=1", "not a partition of sda"),
    ("dev=sda37 parent=sdb size=512 start=8 ro=0 lbs=4096 holders=0 used=0\ncount=1", "expected sda"),
    ("dev=sda37 parent=sda size=64 start=8 ro=0 lbs=4096 holders=0 used=0\ncount=1", "smaller than the image"),
    ("dev=sda37 parent=sda size=512 start=16 ro=0 lbs=4096 holders=0 used=0\ncount=1", "the PIT USERDATA at"),
    ("dev=sda37 parent=sda size=512 start=8 ro=1 lbs=4096 holders=0 used=0\ncount=1", "read-only"),
    ("dev=sda37 parent=sda size=512 start=8 ro=0 lbs=512 holders=0 used=0\ncount=1", "512-byte blocks"),
    ("dev=sda37 parent=sda size=512 start=8 ro=0 lbs=4096 holders=1 used=0\ncount=1", "holders"),
    ("dev=sda37 parent=sda size=512 start=8 ro=0 lbs=4096 holders=0 used=1\ncount=1", "mounted"),
    ("dev=sda37 parent=sda size=x start=8 ro=0 lbs=4096 holders=0 used=0\ncount=1", "unreadable"),
])
def test_refuses_bad_targets(tmp_path, resolve, msg):
    r = Rig(tmp_path, resolve=(resolve,)).run()
    assert r.res.returncode == 1 and msg in r.res.stderr, r.res.stderr
    assert not r.wrote() and r.untouched()


def test_refuses_missing_tools(tmp_path):
    r = Rig(tmp_path, tools="missing=setsid\ntools=checked").run()
    assert r.res.returncode == 1 and "lacks: missing=setsid" in r.res.stderr
    assert not r.wrote() and r.untouched()


def test_pit_size_checked_when_given(tmp_path):
    r = Rig(tmp_path)
    r.pit.write_text(PIT.replace("Partition Block Count: 0", "Partition Block Count: 63", 1))
    r.run()
    assert r.res.returncode == 1 and "the PIT USERDATA 258048" in r.res.stderr
    assert not r.wrote()


def test_without_pit(tmp_path):
    r = Rig(tmp_path)
    r.pit.unlink()
    r.run("--dry-run", answer="")
    assert r.res.returncode == 0 and "not cross-checked" in r.res.stdout


@pytest.mark.parametrize("image_kw, msg", [
    ({"gpt_at": None}, "no GPT header at byte 4096"),
    ({"gpt_at": 512}, "no GPT header at byte 4096"),
    ({"size": 64 * 1024 + 512}, "not a multiple of 4096"),
])
def test_refuses_bad_images(tmp_path, image_kw, msg):
    r = Rig(tmp_path, image_kw=image_kw).run()
    assert r.res.returncode == 1 and msg in r.res.stderr, r.res.stderr
    assert not r.wrote() and r.untouched()


def test_refuses_sparse_image(tmp_path):
    r = Rig(tmp_path)
    data = bytearray(r.data); data[:4] = bytes.fromhex("3aff26ed")
    r.image.write_bytes(bytes(data))
    r.run()
    assert r.res.returncode == 1 and "sparse" in r.res.stderr
    assert r.calls() == []


def test_target_changed_after_plan(tmp_path):
    other = GOOD.replace("sda37", "sda36")
    r = Rig(tmp_path, resolve=(GOOD, other)).run()
    assert r.res.returncode == 1 and "target changed" in r.res.stderr
    assert not r.wrote() and r.untouched()


def test_readback_mismatch(tmp_path):
    r = Rig(tmp_path, fail="corrupt").run()
    assert r.res.returncode == 3 and "read back sha256" in r.res.stderr
    assert "READBACK MISMATCH" in r.notes.read_text()


def test_write_failure_logged(tmp_path):
    r = Rig(tmp_path, fail="write").run()
    assert r.res.returncode == 1 and "write failed" in r.res.stderr
    assert "WRITE FAILED" in r.notes.read_text()
    assert not any(c.startswith(": wu-readback") for c in r.calls())


def test_short_write(tmp_path):
    r = Rig(tmp_path, fail="short").run()
    assert r.res.returncode == 1 and "bytes written, expected" in r.res.stderr
    assert "SHORT WRITE" in r.notes.read_text()


def test_requires_image(tmp_path):
    res = subprocess.run(["bash", str(SCRIPT), "--dry-run"], capture_output=True, text=True)
    assert res.returncode == 1 and "--image is required" in res.stderr
