# tests/test_dts_regulators.py
"""Every RPMh regulator voltage in our DTS must sit on its hardware voltage grid.

r7 regression: L13A was given 3300000 uV (the stock value), which is not a multiple of the
PMIC5 PLDO step (1504000 + n * 8000). The regulator core then rejected the constraints, the
whole PM8150 RPMh regulator device failed to probe, and the board lost DSI and USB.

The grids are read from linux/drivers/regulator/qcom-rpmh-regulator.c (compatible ->
vreg_data table -> hw_data -> REGULATOR_LINEAR_RANGE), the values from the board DTS source.
"""
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
DRIVER = ROOT / "linux" / "drivers" / "regulator" / "qcom-rpmh-regulator.c"
DTS = ROOT / "linux" / "arch" / "arm64" / "boot" / "dts" / "qcom" / "sm8250-samsung-gts7xl.dts"

pytestmark = pytest.mark.skipif(not (DRIVER.exists() and DTS.exists()),
                                reason="needs the linux/ checkout")


def driver_tables(src):
    """{compatible: {regulator node name: [(min_uV, min_sel, max_sel, step_uV), ...]}}"""
    hw = {}
    for m in re.finditer(r"static const struct rpmh_vreg_hw_data (\w+) = \{(.*?)\n\};", src, re.S):
        ranges = [tuple(int(x) for x in r) for r in
                  re.findall(r"REGULATOR_LINEAR_RANGE\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)", m.group(2))]
        hw[m.group(1)] = ranges
    tables = {}
    for m in re.finditer(r"static const struct rpmh_vreg_init_data (\w+)\[\] = \{(.*?)\n\};", src, re.S):
        tables[m.group(1)] = {name: hw[data] for name, data in
                              re.findall(r'RPMH_VREG\("(\w+)",\s*\w+,\s*\d+,\s*&(\w+)', m.group(2))}
    compat = {}
    for c, data in re.findall(r'\.compatible = "([^"]+)",\s*\.data = (\w+),', src):
        if data in tables:
            compat[c] = tables[data]
    return compat


def on_grid(uv, ranges):
    for base, smin, smax, step in ranges:
        if step == 0:
            if uv == base:
                return True
            continue
        if uv >= base and (uv - base) % step == 0 and smin + (uv - base) // step <= smax:
            return True
    return False


def dts_regulators(src):
    """[(compatible, node, regulator-name, min, max)] for every regulators-N block."""
    out = []
    for blk in re.finditer(r"regulators-\d+ \{(.*?)\n\t\};", src, re.S):
        body = blk.group(1)
        compat = re.search(r'compatible = "([^"]+)"', body).group(1)
        for node in re.finditer(r"\n\t\t(?:\w+: )?(\w+) \{(.*?)\n\t\t\};", body, re.S):
            props = node.group(2)
            name = re.search(r'regulator-name = "([^"]+)"', props)
            lo = re.search(r"regulator-min-microvolt = <(\d+)>", props)
            hi = re.search(r"regulator-max-microvolt = <(\d+)>", props)
            if lo and hi:
                out.append((compat, node.group(1), name.group(1) if name else node.group(1),
                            int(lo.group(1)), int(hi.group(1))))
    return out


def test_checker_catches_the_r7_value():
    tables = driver_tables(DRIVER.read_text())
    pldo = tables["qcom,pm8150-rpmh-regulators"]["ldo13"]
    assert not on_grid(3300000, pldo)
    assert on_grid(3296000, pldo)


def test_dts_has_regulators():
    assert len(dts_regulators(DTS.read_text())) >= 8


def test_all_dts_voltages_on_grid():
    tables = driver_tables(DRIVER.read_text())
    bad = []
    for compat, node, name, lo, hi in dts_regulators(DTS.read_text()):
        ranges = tables[compat][node]
        for uv in (lo, hi):
            if not on_grid(uv, ranges):
                bad.append(f"{name} ({node}): {uv} uV not on {ranges}")
        if lo > hi:
            bad.append(f"{name}: min {lo} > max {hi}")
    assert not bad, "\n".join(bad)
