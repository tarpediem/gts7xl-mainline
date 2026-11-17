# tests/test_kconfig_pon.py
"""The power key and volume down (PM8150 PON pwrkey/resin) must be input devices.

r10: CONFIG_POWER_RESET_QCOM_PON=m, and the module was not in the initramfs. The pwrkey
and resin nodes are children of pon@800; only the qcom-pon driver populates them
(devm_of_platform_populate), so pm8941-pwrkey (built in) never saw a device. Both
drivers must be built in, and both DT nodes enabled.
"""
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
CONFIG = ROOT / "pmaports" / "device" / "testing" / "linux-samsung-gts7xl" / "config-samsung-gts7xl.aarch64"
DTS = ROOT / "linux" / "arch" / "arm64" / "boot" / "dts" / "qcom" / "sm8250-samsung-gts7xl.dts"


@pytest.mark.skipif(not CONFIG.exists(), reason="pmaports fork not checked out")
@pytest.mark.parametrize("sym", ["POWER_RESET_QCOM_PON", "INPUT_PM8941_PWRKEY", "MFD_SPMI_PMIC"])
def test_built_in(sym):
    assert re.search(rf"^CONFIG_{sym}=y$", CONFIG.read_text(), re.M), f"CONFIG_{sym} must be =y"


@pytest.mark.skipif(not DTS.exists(), reason="needs the linux/ checkout")
@pytest.mark.parametrize("label,code", [("pon_pwrkey", None), ("pon_resin", "KEY_VOLUMEDOWN")])
def test_dt_nodes_enabled(label, code):
    m = re.search(r"^&" + label + r" \{\n(.*?)^\};", DTS.read_text(), re.S | re.M)
    assert m, label
    assert 'status = "okay";' in m.group(1)
    if code:
        assert f"linux,code = <{code}>;" in m.group(1)
