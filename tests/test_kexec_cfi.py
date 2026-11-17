# tests/test_kexec_cfi.py
"""kexec -e must not run a kCFI check on the jump to the relocation code.

r10 (#11): with CONFIG_CFI=y, machine_kexec+0x12c is `ldur w16, [x8, #-4]` with
x8 = kern_reloc (a physical address mapped only by the kexec idmap in TTBR0): the type
hash load hits the unmapped page before the relocation page -> level 3 translation fault,
oops, panic. Fix: machine_kexec() is __nocfi (linux-samsung-gts7xl r12, patch 0018).
"""
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
SRC = ROOT / "linux" / "arch" / "arm64" / "kernel" / "machine_kexec.c"
APORT = ROOT / "pmaports" / "device" / "testing" / "linux-samsung-gts7xl"
CONFIG = APORT / "config-samsung-gts7xl.aarch64"


@pytest.mark.skipif(not SRC.exists(), reason="needs the linux/ checkout")
def test_machine_kexec_is_nocfi():
    assert re.search(r"^void __nocfi machine_kexec\(struct kimage \*kimage\)$", SRC.read_text(), re.M)


@pytest.mark.skipif(not APORT.exists(), reason="pmaports fork not checked out")
def test_aport_carries_the_fix():
    if not re.search(r"^CONFIG_CFI=y$", CONFIG.read_text(), re.M):
        pytest.skip("kCFI off: the fix is not needed")
    patches = [p for p in APORT.glob("*.patch") if "void __nocfi machine_kexec(" in p.read_text()]
    assert len(patches) == 1
    assert patches[0].name in (APORT / "APKBUILD").read_text()
