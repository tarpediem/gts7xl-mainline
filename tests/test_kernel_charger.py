# tests/test_kernel_charger.py
"""Guards for the MAX77705 charger safety work (r17).

- The MFD accepts PMICID 0x15 / rev 2 (gts7xl, "MD15 PASS2") and still nothing else new.
- The charger switches off through CNFG_00 MODE (vendor method), not CHG_EN alone.
- The watchdog is kicked only from a verified state.
- Each kernel package revision has its own module directory (BTF-tied modules).
"""
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
LINUX = ROOT / "linux"
MFD = LINUX / "drivers" / "mfd" / "max77705.c"
CHG = LINUX / "drivers" / "power" / "supply" / "max77705_charger.c"
APKBUILD = ROOT / "pmaports" / "device" / "testing" / "linux-samsung-gts7xl" / "APKBUILD"

needs_linux = pytest.mark.skipif(not CHG.exists(), reason="needs the linux/ checkout")


@needs_linux
def test_mfd_accepts_md15_rev2_only():
    src = MFD.read_text()
    assert "MAX77705_PMICID_MD15 && pmic_rev == MAX77705_PASS2" in src
    assert "pmic_rev != MAX77705_PASS3 &&" in src


@needs_linux
def test_force_off_uses_mode_and_chg_en():
    body = re.search(r"static int max77705_charger_force_off\(.*?\n}\n", CHG.read_text(), re.S).group(0)
    assert "MAX77705_MODE], MAX77705_BUCK_MASK" in body
    assert "MAX77705_CHG_EN], MAX77705_CHG_DISABLE" in body


@needs_linux
def test_watchdog_kick_only_when_safe():
    body = re.search(r"static void max77705_safety_check\(.*?\n}\n", CHG.read_text(), re.S).group(0)
    kick = body.index("MAX77705_WDTCLR_MASK, MAX77705_WDTCLR")
    assert "if (safe) {" in body[:kick]
    # a watchdog expiry forces the charger off before the limits check
    assert body.index("MAX77705_CHG_DTLS_WDT_EXPIRED") < body.index("max77705_safety_limits_ok(chg);")


@needs_linux
def test_aicl_has_lower_bound():
    src = CHG.read_text()
    assert "regval <= MAX77705_CHGIN_LIM_REG_MIN" in src


@needs_linux
def test_capacity_window_defaults():
    src = CHG.read_text()
    assert re.search(r"#define MAX77705_SOC_END_DEFAULT\s+80\b", src)
    assert re.search(r"#define MAX77705_SOC_START_DEFAULT\s+75\b", src)


@pytest.mark.skipif(not APKBUILD.exists(), reason="pmaports fork not checked out")
def test_per_revision_kernel_release():
    s = APKBUILD.read_text()
    assert '_localversion="-r$pkgrel"' in s
    assert s.count('LOCALVERSION="$_localversion"') == 2
