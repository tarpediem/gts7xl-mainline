# tests/test_kexec_tools.py
"""kexec over USB: the DTB patch (memory layout from the running kernel) and the dry runs
of tools/kexec-push.sh and tools/module-push.sh (no tablet involved)."""
import importlib.util, shutil, subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
TOOLS = ROOT / "tools"
pytestmark = pytest.mark.skipif(not (shutil.which("dtc") and shutil.which("fdtput")), reason="needs dtc/fdtput")

spec = importlib.util.spec_from_file_location("kexec_dtb", TOOLS / "kexec_dtb.py")
kexec_dtb = importlib.util.module_from_spec(spec); spec.loader.exec_module(kexec_dtb)

NEW = """/dts-v1/;
/ { #address-cells = <2>; #size-cells = <2>; model = "new";
    chosen { };
    memory@80000000 { device_type = "memory"; reg = <0x0 0x80000000 0x0 0x0>; };
    soc { compatible = "simple-bus"; };
};"""
RUNNING = """/dts-v1/;
/ { #address-cells = <2>; #size-cells = <2>; model = "running";
    chosen { bootargs = "console=tty0"; };
    memory@80000000 { device_type = "memory";
        reg = <0x0 0x80000000 0x0 0x3a00000>, <0x0 0x8bc00000 0x0 0x15d0000>,
              <0x1 0x80000000 0x1 0x00000000>; };
};"""


def dtb(tmp_path, name, src):
    s = tmp_path / f"{name}.dts"; s.write_text(src)
    out = tmp_path / f"{name}.dtb"
    subprocess.run(["dtc", "-q", "-I", "dts", "-O", "dtb", "-o", str(out), str(s)], check=True)
    return out


def get(path, node, prop, t="x"):
    return subprocess.run(["fdtget", "-t", t, str(path), node, prop], capture_output=True,
                          text=True, check=True).stdout.split()


def test_memory_copied_rest_kept(tmp_path):
    new, running, out = dtb(tmp_path, "new", NEW), dtb(tmp_path, "running", RUNNING), tmp_path / "out.dtb"
    kexec_dtb.patch(str(new), str(running), str(out))
    assert get(out, "/memory@80000000", "reg") == get(running, "/memory@80000000", "reg")
    assert get(out, "/", "model", "s") == ["new"]
    assert get(new, "/memory@80000000", "reg") == ["0", "80000000", "0", "0"]     # input untouched


def test_no_memory_node_fails(tmp_path):
    new = dtb(tmp_path, "new", NEW)
    bad = dtb(tmp_path, "bad", '/dts-v1/;\n/ { #address-cells = <2>; #size-cells = <2>; };')
    with pytest.raises(SystemExit):
        kexec_dtb.patch(str(new), str(bad), str(tmp_path / "o.dtb"))


def fake_artefacts(tmp_path):
    k = tmp_path / "vmlinuz"; k.write_bytes(b"x")
    d = tmp_path / "a.dtb"; d.write_bytes(b"x")
    i = tmp_path / "initramfs"; i.write_bytes(b"x")
    return ["--kernel", str(k), "--dtb", str(d), "--initramfs", str(i)]


def test_kexec_push_dry_run(tmp_path):
    r = subprocess.run(["bash", str(TOOLS / "kexec-push.sh"), "--dry-run", "--host", "192.0.2.1",
                        "--append", "gts7xl.nomodules", *fake_artefacts(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "pull 192.0.2.1:/sys/firmware/fdt" in out
    assert "kexec -l /tmp/kx/Image --dtb=/tmp/kx/kexec.dtb --initrd=/tmp/kx/initramfs " \
           "--reuse-cmdline --append='gts7xl.nomodules'" in out
    assert "kexec -e" in out


def test_kexec_push_no_exec_and_cmdline(tmp_path):
    r = subprocess.run(["bash", str(TOOLS / "kexec-push.sh"), "--dry-run", "--no-exec",
                        "--cmdline", "console=tty0 it's", *fake_artefacts(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "--command-line='console=tty0 it'\\''s'" in r.stdout
    assert "kexec -e" not in r.stdout


def test_kexec_push_rejects_both_cmdlines(tmp_path):
    r = subprocess.run(["bash", str(TOOLS / "kexec-push.sh"), "--dry-run", "--cmdline", "a",
                        "--append", "b", *fake_artefacts(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 2


@pytest.mark.skipif(not shutil.which("zstd"), reason="needs zstd")
def test_module_push_dry_run_from_zst(tmp_path):
    ko = tmp_path / "stmfts1b.ko"
    ko.write_bytes(b"\x7fELF....\0vermagic=7.3.4 SMP preempt mod_unload aarch64\0")
    subprocess.run(["zstd", "-q", str(ko), "-o", str(tmp_path / "stmfts1b.ko.zst")], check=True)
    r = subprocess.run(["bash", str(TOOLS / "module-push.sh"), "--dry-run", "--host", "192.0.2.1",
                        "--ko", str(tmp_path / "stmfts1b.ko.zst")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "vermagic: 7.3.4 SMP preempt mod_unload aarch64" in r.stdout
    assert "rmmod stmfts1b 2>/dev/null; insmod /tmp/stmfts1b.ko" in r.stdout


def fake_fdtget(tmp_path, real):
    """An fdtget that behaves like it does on the ABL-built /sys/firmware/fdt (r10): `-l`
    prints part of the node list, without /memory, and exits 1. Everything else is real."""
    bin_ = tmp_path / "bin"; bin_.mkdir()
    f = bin_ / "fdtget"
    f.write_text(f"""#!/bin/sh
if [ "$1" = -l ]; then echo chosen; echo soc; echo 'Error at node' >&2; exit 1; fi
exec {real} "$@"
""")
    f.chmod(0o755)
    return bin_


def test_listing_exits_1_memory_found_directly(tmp_path, monkeypatch):
    new, running, out = dtb(tmp_path, "new", NEW), dtb(tmp_path, "running", RUNNING), tmp_path / "out.dtb"
    monkeypatch.setenv("PATH", f"{fake_fdtget(tmp_path, shutil.which('fdtget'))}:{__import__('os').environ['PATH']}")
    assert kexec_dtb.memory_node(str(running)) == "/memory@80000000"
    kexec_dtb.patch(str(new), str(running), str(out))
    assert get(out, "/memory@80000000", "reg") == get(running, "/memory@80000000", "reg")


def test_fdtget_failure_without_output_still_raises(tmp_path):
    bad = tmp_path / "garbage.dtb"; bad.write_bytes(b"not a dtb")
    with pytest.raises((subprocess.CalledProcessError, SystemExit)):
        kexec_dtb.memory_node(str(bad))


def fake_usbsh_tools(tmp_path, uname_v):
    """Copy of tools/ whose usbsh.py answers `uname -v` and fails on anything else, so a
    real (non-dry) kexec-push.sh run can only reach the version check."""
    t = tmp_path / "tools"; t.mkdir()
    shutil.copy(TOOLS / "kexec-push.sh", t / "kexec-push.sh")
    (t / "usbsh.py").write_text(f"""import sys
args = sys.argv[1:]
if args[-2:] == ["run", "uname -v"]:
    print({uname_v!r}); sys.exit(0)
open({str(tmp_path / 'calls')!r}, "a").write(" ".join(args) + "\\n")
sys.exit(3)
""")
    return t


@pytest.mark.parametrize("uname_v", ["#11-samsung-gts7xl SMP PREEMPT Tue Nov 17 05:03:18 UTC 2026",
                                     "#12-samsung-gts7xl SMP PREEMPT", "something else"])
def test_kexec_push_refuses_old_running_kernel(tmp_path, uname_v):
    t = fake_usbsh_tools(tmp_path, uname_v)
    r = subprocess.run(["bash", str(t / "kexec-push.sh"), *fake_artefacts(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 1
    assert "oops in machine_kexec()" in r.stderr
    assert not (tmp_path / "calls").exists()          # nothing pulled, pushed or loaded


def test_kexec_push_accepts_r12_running_kernel(tmp_path):
    t = fake_usbsh_tools(tmp_path, "#13-samsung-gts7xl SMP PREEMPT")
    r = subprocess.run(["bash", str(t / "kexec-push.sh"), *fake_artefacts(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode != 0                           # the fake usbsh fails the next step
    assert "oops in machine_kexec()" not in r.stderr
    assert "pull /sys/firmware/fdt" in (tmp_path / "calls").read_text()


def test_kexec_jump_detached(tmp_path):
    r = subprocess.run(["bash", str(TOOLS / "kexec-push.sh"), "--dry-run", *fake_artefacts(tmp_path)],
                       capture_output=True, text=True)
    jump = [l for l in r.stdout.splitlines() if "kexec -e" in l][0]
    assert "exec setsid sh -c" in jump and "trap '' HUP" in jump
    assert jump.endswith("& true")                   # usbsh appends `; echo`; `&;` is a syntax error
    assert "timeout 300 s): kexec -l" in r.stdout


NATIVE = Path(__import__("os").environ.get("PMB_NATIVE", Path.home() / ".local/var/pmbootstrap/chroot_native"))
LDSO, BUSYBOX = NATIVE / "lib" / "ld-musl-x86_64.so.1", NATIVE / "bin" / "busybox"


@pytest.mark.skipif(not (BUSYBOX.exists() and shutil.which("setsid")), reason="no pmbootstrap native chroot")
def test_kexec_jump_survives_the_session_under_busybox_ash(tmp_path):
    """The jump line, followed by usbsh's `; echo`, parses in ash, returns at once, and the
    detached `kexec -e` still runs after the shell's process group got SIGHUP (telnet closed)."""
    import os, signal, time
    r = subprocess.run(["bash", str(TOOLS / "kexec-push.sh"), "--dry-run", *fake_artefacts(tmp_path)],
                       capture_output=True, text=True)
    jump = [l for l in r.stdout.splitlines() if "kexec -e" in l][0].split("run: ", 1)[1]
    bin_ = tmp_path / "bin"; bin_.mkdir()
    (bin_ / "kexec").write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" > {tmp_path}/jumped\n'); (bin_ / "kexec").chmod(0o755)
    env = dict(os.environ, PATH=f"{bin_}:{os.environ['PATH']}")
    t0 = time.monotonic()
    p = subprocess.Popen([str(LDSO), str(BUSYBOX), "sh", "-c", jump + '; echo "__E""ND__ $?"'],
                         stdout=subprocess.PIPE, text=True, env=env, start_new_session=True)
    out, _ = p.communicate(timeout=5)
    assert "__END__ 0" in out and time.monotonic() - t0 < 1.5
    try:
        os.killpg(p.pid, signal.SIGHUP)                 # what a closing telnet session does
    except ProcessLookupError:
        pass
    for _ in range(50):
        if (tmp_path / "jumped").exists():
            break
        time.sleep(0.1)
    assert (tmp_path / "jumped").read_text().strip() == "-e"
