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
