# tests/test_gpi_kexec.py
"""GPI DMA must survive kexec: reclaim stale GPIIs at allocation, tear them down on shutdown.

r14 (#14 kexec'd from a RECOVERY boot): the GPII channel and event ring contexts outlive
the kernel. The new kernel's EV ALLOCATE timed out ("EV ALLOCATE completion timeout:2",
"error alloc_ev_chan:-5"), geni_i2c 994000 got no rx channel and the touchscreen was gone.
Fix (linux-samsung-gts7xl r14, patch 0020): gpi_reclaim_gpii() before gpi_alloc_ev_chan()
in gpi_ch_init(), and a platform .shutdown hook.
"""
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
GPI_C = ROOT / "linux" / "drivers" / "dma" / "qcom" / "gpi.c"
APORT = ROOT / "pmaports" / "device" / "testing" / "linux-samsung-gts7xl"


def func(src, name):
    m = re.search(r"^static \w+ " + name + r"\(.*?^\}", src, re.S | re.M)
    return m.group(0) if m else None


@pytest.mark.skipif(not GPI_C.exists(), reason="needs the linux/ checkout")
def test_reclaim_runs_before_ev_allocate():
    body = func(GPI_C.read_text(), "gpi_ch_init")
    assert body is not None
    reclaim = body.find("gpi_reclaim_gpii(gpii);")
    assert reclaim != -1
    assert reclaim < body.find("gpi_alloc_ev_chan(gpii)")
    assert body.find("gpi_config_interrupts(") < reclaim, "commands need the IRQ"


@pytest.mark.skipif(not GPI_C.exists(), reason="needs the linux/ checkout")
def test_reclaim_deallocates_channels_then_event_ring():
    body = func(GPI_C.read_text(), "gpi_reclaim_gpii")
    assert body is not None
    ch = body.find("GPI_CH_CMD_DE_ALLOC")
    ev = body.find("GPI_EV_CMD_DEALLOC")
    assert -1 < ch < ev


@pytest.mark.skipif(not GPI_C.exists(), reason="needs the linux/ checkout")
def test_driver_has_shutdown_hook():
    src = GPI_C.read_text()
    assert re.search(r"\.shutdown\s*=\s*gpi_shutdown,", src)
    body = func(src, "gpi_shutdown")
    assert "GPI_EV_CMD_DEALLOC" in body and "gpi_disable_interrupts" in body


@pytest.mark.skipif(not APORT.exists(), reason="pmaports fork not checked out")
def test_aport_carries_the_fix():
    patches = [p for p in APORT.glob("*.patch") if "gpi_reclaim_gpii(gpii);" in p.read_text()]
    assert len(patches) == 1
    assert patches[0].name in (APORT / "APKBUILD").read_text()
