# tests/test_dts_battery.py
"""Charging limits in our DTS must never exceed the stock ones.

The stock values come from the device tree of the running stock kernel
(reference/live/live.dts, local only: sec-battery "battery", "cable-info"). When it is
absent, the stock numbers recorded in NOTES.md (2026-11-17, battery and charging) are used.
Also: the PCA9468 direct charger must not be described, and the drivers must be built in
(they must not come from the root filesystem's modules of another build).
"""
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
DTS = ROOT / "linux" / "arch" / "arm64" / "boot" / "dts" / "qcom" / "sm8250-samsung-gts7xl.dts"
LIVE = ROOT / "reference" / "live" / "live.dts"
CONFIG = ROOT / "pmaports" / "device" / "testing" / "linux-samsung-gts7xl" / "config-samsung-gts7xl.aarch64"

pytestmark = pytest.mark.skipif(not DTS.exists(), reason="needs the linux/ checkout")

# Stock values (live DT, T976BXXS7DXH1) used when reference/live/ is not there.
STOCK = {
    "float_mv": 4380,             # battery,chg_float_voltage
    "age_float_min_mv": 4270,     # lowest float of battery,age_data
    "charging_ma_min": 450,       # lowest charging_current of cable-info
    "input_ma_min": 475,          # lowest input_current of cable-info
    "temp_low_dc": 0,             # battery,temp_low_threshold_normal (0.1 C)
    "swelling_high_dc": 420,      # battery,swelling_high_temp_block (0.1 C)
    "usb_total_s": 36000,         # battery,usb_charging_total_time
    "capacity_mah": 10090,        # battery,battery_full_capacity
}


def cells(text, prop):
    m = re.search(rf"^\s*{re.escape(prop)} = <([^>]*)>;", text, re.M)
    assert m, prop
    return [int(x, 0) for x in m.group(1).split()]


def node(text, header):
    m = re.search(re.escape(header) + r" \{\n(.*?)\n\t\};", text, re.S)
    assert m, header
    return m.group(1)


@pytest.fixture(scope="module")
def stock():
    if not LIVE.exists():
        return STOCK
    live = LIVE.read_text()
    bat = re.search(r'compatible = "samsung,sec-battery";(.*?)\n\t\t\};', live, re.S).group(1)
    age = cells(bat, "battery,age_data")
    cable = re.search(r"cable-info \{(.*?)\n\t\t\};\n\n\t\tqcom", live, re.S).group(1)
    s = {
        "float_mv": cells(bat, "battery,chg_float_voltage")[0],
        "age_float_min_mv": min(age[1::5]),
        "charging_ma_min": min(int(x, 0) for x in re.findall(r"\tcharging_current = <(\w+)>", cable)),
        "input_ma_min": min(int(x, 0) for x in re.findall(r"\tinput_current = <(\w+)>", cable)),
        "temp_low_dc": cells(bat, "battery,temp_low_threshold_normal")[0],
        "swelling_high_dc": cells(bat, "battery,swelling_high_temp_block")[0],
        "usb_total_s": cells(bat, "battery,usb_charging_total_time")[0],
        "capacity_mah": cells(bat, "battery,battery_full_capacity")[0],
    }
    # the fallback table must stay in step with the live tree
    assert s == STOCK
    return s


def test_battery_limits(stock):
    bat = node(DTS.read_text(), "battery: battery")
    assert cells(bat, "constant-charge-voltage-max-microvolt")[0] <= stock["age_float_min_mv"] * 1000
    assert cells(bat, "voltage-max-design-microvolt")[0] <= stock["float_mv"] * 1000
    assert cells(bat, "constant-charge-current-max-microamp")[0] <= stock["charging_ma_min"] * 1000
    assert cells(bat, "charge-full-design-microamp-hours")[0] == stock["capacity_mah"] * 1000
    lo, hi = cells(bat, "alert-celsius")
    assert lo * 10 >= stock["temp_low_dc"]
    assert hi * 10 < stock["swelling_high_dc"]


def test_charger_node(stock):
    chg = node(DTS.read_text(), "max77705_charger: charger@69")
    assert cells(chg, "input-current-limit-microamp")[0] <= stock["input_ma_min"] * 1000
    assert 0 < cells(chg, "maxim,safety-timer-sec")[0] <= stock["usb_total_s"]
    assert 'io-channel-names = "battery-temp";' in chg
    assert "monitored-battery = <&battery>;" in chg


def test_no_direct_charger():
    assert "pca9468" not in DTS.read_text().lower().replace("pca9468 direct charger", "")


@pytest.mark.skipif(not CONFIG.exists(), reason="pmaports fork not checked out")
@pytest.mark.parametrize("sym", ["MFD_MAX77705", "CHARGER_MAX77705", "BATTERY_MAX17042",
                                 "QCOM_SPMI_ADC5"])
def test_built_in(sym):
    assert re.search(rf"^CONFIG_{sym}=y$", CONFIG.read_text(), re.M), f"CONFIG_{sym} must be =y"
