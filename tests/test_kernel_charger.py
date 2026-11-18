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


@needs_linux
def test_dcp_limit_only_on_positive_detection():
    src = CHG.read_text()
    body = re.search(r"static unsigned int max77705_cable_input_limit\(.*?\n}\n", src, re.S).group(0)
    # default is the SDP value; DCP only with VBUS present and CHGTYP == DCP
    assert "unsigned int ua = chg->chgin_sdp_ua;" in body
    assert "(data.byte & MAX77705_BC_VBUSDET)" in body
    assert body.count("ua = chg->chgin_dcp_ua") == 1
    assert "case MAX77705_BC_CHGTYP_DCP:" in body


def test_dts_dcp_limit_within_stock():
    dts = (LINUX / "arch" / "arm64" / "boot" / "dts" / "qcom" / "sm8250-samsung-gts7xl.dts")
    if not dts.exists():
        pytest.skip("needs the linux/ checkout")
    m = re.search(r"maxim,dcp-input-current-limit-microamp = <(\d+)>;", dts.read_text())
    # stock cable-info default_input_current 0x708 = 1800 mA
    assert m and int(m.group(1)) <= 1800000


@needs_linux
def test_dcp_charge_current_only_on_positive_detection():
    src = CHG.read_text()
    body = re.search(r"static unsigned int max77705_cable_charge_current\(.*?\n}\n", src, re.S).group(0)
    # 1.5 A only when online, configured and BC1.2 says DCP; the battery's value otherwise
    assert "online && chg->cc_dcp_ua" in body
    assert "== POWER_SUPPLY_USB_TYPE_DCP" in body
    assert body.count("return chg->cc_dcp_ua;") == 1
    assert body.rstrip().endswith("return chg->cc_sdp_ua;\n}")
    # hard ceiling, a larger DT value is dropped (0 = not used)
    assert "#define MAX77705_CC_DCP_CEIL_UA	1500000" in src
    assert "chg->cc_dcp_ua > MAX77705_CC_DCP_CEIL_UA" in src
    assert "chg->cc_dcp_ua = 0;" in src


@needs_linux
def test_charge_current_reference_follows_cable():
    body = re.search(r"static void max77705_safety_check\(.*?\n}\n", CHG.read_text(), re.S).group(0)
    sel = body.index("max77705_cable_charge_current(chg, online)")
    # the per-cable value becomes the reference before the limits check that enforces it
    assert body.index("chg->cc_max_ua = ref;") > sel
    assert body.index("max77705_safety_limits_ok(chg)") > sel
    lim = re.search(r"static int max77705_safety_limits_ok\(.*?\n}\n", CHG.read_text(), re.S).group(0)
    assert "cc <= max77705_cc_ua_to_reg(chg->cc_max_ua)" in lim


def test_dts_dcp_charge_current_within_stock():
    dts = (LINUX / "arch" / "arm64" / "boot" / "dts" / "qcom" / "sm8250-samsung-gts7xl.dts")
    if not dts.exists():
        pytest.skip("needs the linux/ checkout")
    text = dts.read_text()
    m = re.search(r"maxim,dcp-constant-charge-current-microamp = <(\d+)>;", text)
    # stock TA (cable 3, in no current_group): cable-info default_charging_current 0x834 = 2100 mA
    stock = re.search(r"default_charging_current = <(0x\w+)>;",
                      (ROOT / "reference" / "stock-overlay-01-id0-rev0.dts").read_text())
    assert stock and int(stock.group(1), 16) == 2100
    assert m and int(m.group(1)) <= 1500000 <= 2100 * 1000
    # every other cable keeps the battery's 450 mA
    assert re.search(r"constant-charge-current-max-microamp = <450000>;", text)


@needs_linux
def test_typec_input_limit_sink_only_and_never_lowers():
    src = CHG.read_text()
    tc = re.search(r"static unsigned int max77705_typec_input_limit\(.*?\n}\n", src, re.S).group(0)
    # read-only CC_STATUS0 read, only as the sink; 1.5 A / 3 A only, anything else 0
    assert "I2C_SMBUS_READ" in tc and "I2C_SMBUS_WRITE" not in tc
    assert "== MAX77705_CC_CCSTAT_SINK" in tc
    assert "unsigned int ua = 0" in tc
    assert tc.count("ua = chg->chgin_typec") == 2
    cable = re.search(r"static unsigned int max77705_cable_input_limit\(.*?\n}\n", src, re.S).group(0)
    # used only with VBUS present, combined with max(): never lowers the BC1.2 value
    assert "ua = max(ua, max77705_typec_input_limit(chg));" in cable
    assert cable.index("MAX77705_BC_VBUSDET") < cable.index("max77705_typec_input_limit")
    # driver ceilings = stock rp_current_rp2 / rp3
    assert "#define MAX77705_TYPEC15_CEIL_UA	1400000" in src
    assert "#define MAX77705_TYPEC30_CEIL_UA	3000000" in src
    assert "chg->chgin_typec15_ua = 0;" in src and "chg->chgin_typec30_ua = 0;" in src
    # the charge current does not look at Type-C
    cc = re.search(r"static unsigned int max77705_cable_charge_current\(.*?\n}\n", src, re.S).group(0)
    assert "typec" not in cc


def test_dts_typec_limits_within_stock():
    dts = (LINUX / "arch" / "arm64" / "boot" / "dts" / "qcom" / "sm8250-samsung-gts7xl.dts")
    if not dts.exists():
        pytest.skip("needs the linux/ checkout")
    text = dts.read_text()
    stock = (ROOT / "reference" / "stock-overlay-01-id0-rev0.dts").read_text()
    rp2 = int(re.search(r"battery,rp_current_rp2 = <(0x\w+)>;", stock).group(1), 16)
    rp3 = int(re.search(r"battery,rp_current_rp3 = <(0x\w+)>;", stock).group(1), 16)
    assert (rp2, rp3) == (1400, 3000)
    t15 = int(re.search(r"maxim,typec-1500ma-input-current-limit-microamp = <(\d+)>;", text).group(1))
    t30 = int(re.search(r"maxim,typec-3000ma-input-current-limit-microamp = <(\d+)>;", text).group(1))
    assert t15 <= rp2 * 1000 and t30 <= rp3 * 1000
    # 3200 mA is the CHGIN register maximum
    assert t30 <= 3200000


def _fn(src, name, ret="static [a-z ]+"):
    m = re.search(r"\n" + ret + r"\b" + name + r"\(.*?\n}\n", src, re.S)
    assert m, name
    return m.group(0)


@needs_linux
def test_otg_boost_only_through_checked_path():
    src = CHG.read_text()
    # MODE 0x0a (OTG boost) is written in exactly one place
    assert src.count("rfield[MAX77705_MODE], MAX77705_OTG_CTRL)") == 1
    on = _fn(src, "max77705_boost_on")
    assert "rfield[MAX77705_MODE], MAX77705_OTG_CTRL)" in on
    # all gates before the first register write
    first_write = on.index("regmap_field_write")
    for gate in ("!chg->usbc_ready", "chg->boost_fault", "!chg->otg_vbus_auto",
                 "max77705_no_vbus_input(chg) != 1", "!max77705_boost_battery_ok(chg)"):
        assert on.index(gate) < first_write, gate
    # charger off (CHG_EN 0) before the boost mode; 900 mA as stock; read back
    assert on.index("MAX77705_CHG_EN], MAX77705_CHG_DISABLE") < on.index("MAX77705_OTG_CTRL)")
    assert "MAX77705_OTG_ILIM], MAX77705_OTG_ILIM_900" in on
    assert "max77705_boost_state_ok(chg) != 1" in on
    assert "MAX77705_OTG_ILIM_1200" not in src and "MAX77705_OTG_ILIM_1500" not in src.replace(
        "#define MAX77705_OTG_ILIM_1500", "")


@needs_linux
def test_otg_boost_default_off_and_no_input():
    src = CHG.read_text()
    assert "chg->otg_vbus_auto = false;" in src
    nv = _fn(src, "max77705_no_vbus_input")
    assert "MAX77705_BC_VBUSDET" in nv and "MAX77705_CHGIN_OK" in nv
    assert "FIELD_GET(MAX77705_CHGIN_DTLS, dtls) == 0" in nv
    bat = _fn(src, "max77705_boost_battery_ok", ret="static bool ")
    assert "iio_read_channel_processed(chg->temp_chan" in bat
    assert "chg->otg_soc_min" in bat and "temp_alert_max" in bat and "temp_alert_min" in bat


@needs_linux
def test_otg_boost_monitored_and_switched_off():
    src = CHG.read_text()
    mon = _fn(src, "max77705_boost_monitor")
    assert "cc_stat != MAX77705_CC_CCSTAT_SOURCE" in mon
    assert "max77705_boost_state_ok(chg)" in mon and "!max77705_boost_battery_ok(chg)" in mon
    assert mon.count("max77705_boost_off(") >= 4
    st = _fn(src, "max77705_boost_state_ok", ret="static int ")
    assert "MAX77705_BYP_DTLS_OTG_OVC" in st and "mode == MAX77705_OTG_CTRL && !en" in st
    off = _fn(src, "max77705_boost_off")
    assert "max77705_charger_force_off(chg)" in off and "MAX77705_BOOST_MASK" in off
    # off on unbind and shutdown
    assert 'max77705_boost_off(chg, "driver stop")' in _fn(src, "max77705_usbc_stop")
    assert 'max77705_boost_off(chg, "shutdown")' in _fn(src, "max77705_charger_shutdown")
    assert ".shutdown = max77705_charger_shutdown," in src


@needs_linux
def test_never_charge_while_boosting():
    src = CHG.read_text()
    chk = _fn(src, "max77705_safety_check")
    # the monitor leaves the charger alone (no CHG_EN 1) while the boost is on
    assert chk.index("if (chg->boost_on) {") < chk.index("regmap_field_write(chg->rfield[MAX77705_CHG_EN], 1)")
    aicl = re.search(r"static irqreturn_t max77705_aicl_irq\(.*?\n}\n", src, re.S).group(0)
    assert "if (chg->boost_on)" in aicl


@needs_linux
def test_role_from_debounced_cc_status():
    src = CHG.read_text()
    w = _fn(src, "max77705_usbc_work")
    assert "chg->cc_stat_count >= MAX77705_CC_DEBOUNCE" in w
    # the boost check runs on every poll before the debounce
    assert w.index("max77705_boost_monitor(chg, raw)") < w.index("MAX77705_CC_DEBOUNCE && raw")
    # host only for SOURCE; detach clears the fault latch and turns VBUS off before the role
    src_branch = w[w.index("if (raw == MAX77705_CC_CCSTAT_SOURCE)"):]
    assert src_branch.index("USB_ROLE_HOST") < src_branch.index("} else {")
    els = src_branch[src_branch.index("} else {"):]
    assert els.index("max77705_boost_off") < els.index("USB_ROLE_DEVICE")


def test_dts_dual_role_device_default():
    dts = (LINUX / "arch" / "arm64" / "boot" / "dts" / "qcom" / "sm8250-samsung-gts7xl.dts")
    if not dts.exists():
        pytest.skip("needs the linux/ checkout")
    text = dts.read_text()
    m = re.search(r"&usb_1_dwc3 \{(.*?)\n\};", text, re.S).group(1)
    assert 'dr_mode = "otg";' in m and "usb-role-switch;" in m
    assert 'role-switch-default-mode = "peripheral";' in m
    assert "usb-role-switch = <&usb_1_dwc3>;" in text
    assert int(re.search(r"maxim,otg-min-capacity-percent = <(\d+)>;", text).group(1)) >= 15
