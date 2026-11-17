# tests/test_dts_gpi.py
"""GPI DMA 0 must use the stock EE offset, and only i2c5 (touchscreen) goes through it.

r9: SE5 runs in GSI mode (FIFO disabled by the firmware), so geni-i2c needs GPI DMA.
r7: with gpi_dma0 enabled at EE offset 0 (mainline sm8250 match data), every command
timed out ("EV ALLOCATE completion timeout"). The stock tree uses
qcom,gpi-ee-offset = <0x1000> for the QUPv3_0 GPI (reference/live/live.dts).
"""
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
LINUX = ROOT / "linux"
DTS = LINUX / "arch" / "arm64" / "boot" / "dts" / "qcom" / "sm8250-samsung-gts7xl.dts"
GPI_C = LINUX / "drivers" / "dma" / "qcom" / "gpi.c"
LIVE = ROOT / "reference" / "live" / "live.dts"

pytestmark = pytest.mark.skipif(not DTS.exists(), reason="needs the linux/ checkout")


def block(src, label):
    m = re.search(r"^&" + re.escape(label) + r" \{\n(.*?)^\};", src, re.S | re.M)
    return m.group(1) if m else None


def stock_ee_offset():
    if not LIVE.exists():
        return 0x1000
    m = re.search(r"qcom,gpi-dma@900000 \{.*?qcom,gpi-ee-offset = <(0x[0-9a-f]+)>", LIVE.read_text(), re.S)
    return int(m.group(1), 16)


def test_gpi_dma0_enabled_with_stock_ee_offset():
    b = block(DTS.read_text(), "gpi_dma0")
    assert b is not None, "&gpi_dma0 missing"
    assert 'status = "okay";' in b
    m = re.search(r"qcom,gpi-ee-offset = <(0x[0-9a-f]+|\d+)>;", b)
    assert m and int(m.group(1), 0) == stock_ee_offset()


def test_gpi_driver_reads_ee_offset_property():
    assert '"qcom,gpi-ee-offset"' in GPI_C.read_text()


def test_i2c5_keeps_its_dmas():
    b = block(DTS.read_text(), "i2c5")
    assert b is not None
    assert "/delete-property/ dmas" not in b and "/delete-property/ dma-names" not in b


def test_i2c0_unchanged():
    b = block(DTS.read_text(), "i2c0")
    assert b.strip() == 'status = "okay";'
