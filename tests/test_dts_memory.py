# tests/test_dts_memory.py
"""The mainline DTB must keep Linux out of everything the stock kernel keeps out of.

Compares the built DTB with the device tree captured from the running stock kernel
(reference/live/live.dtb, not in git). Skipped when one of them is missing.
"""
import struct, subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
LIVE = ROOT / "reference" / "live" / "live.dtb"
OURS = ROOT / "build" / "dtbs" / "sm8250-samsung-gts7xl.dtb"

pytestmark = pytest.mark.skipif(not (LIVE.exists() and OURS.exists()),
                                reason="needs reference/live/live.dtb and build/dtbs/sm8250-samsung-gts7xl.dtb")

def fdtget(dtb, *args):
    res = subprocess.run(["fdtget", *args[:-2], str(dtb), *args[-2:]], capture_output=True, text=True)
    return res.stdout.strip() if res.returncode == 0 else None

def regions(dtb):
    """{node: (base, size, no_map)} for the reserved-memory nodes with a fixed address."""
    out = {}
    for name in subprocess.run(["fdtget", "-l", str(dtb), "/reserved-memory"],
                               capture_output=True, text=True, check=True).stdout.split():
        reg = fdtget(dtb, "-t", "x", f"/reserved-memory/{name}", "reg")
        if not reg:
            continue                                   # dynamic pool (size only)
        hi, lo, shi, slo = (int(v, 16) for v in reg.split())
        props = subprocess.run(["fdtget", "-p", str(dtb), f"/reserved-memory/{name}"],
                               capture_output=True, text=True, check=True).stdout.split()
        out[name] = ((hi << 32) | lo, (shi << 32) | slo, "no-map" in props)
    return out

def test_every_fixed_region_of_the_stock_kernel_is_reserved():
    ours = [(base, base + size) for base, size, _ in regions(OURS).values()]
    missing = []
    for name, (base, size, _) in regions(LIVE).items():
        if not any(lo <= base and base + size <= hi for lo, hi in ours):
            missing.append(f"{name} {base:#x}+{size:#x}")
    assert not missing, missing

def test_no_region_of_ours_is_made_up():
    """Each of our regions exists at the same place and size in the stock tree."""
    live = {(base, size) for base, size, _ in regions(LIVE).values()}
    extra = [f"{n} {b:#x}+{s:#x}" for n, (b, s, _) in regions(OURS).items() if (b, s) not in live]
    assert not extra, extra

def test_all_our_fixed_regions_are_no_map():
    assert all(no_map for _, _, no_map in regions(OURS).values())

def test_ramoops_layout_is_the_stock_one():
    for prop in ("reg", "record-size", "console-size", "ftrace-size", "pmsg-size"):
        assert fdtget(OURS, "-t", "x", "/reserved-memory/ramoops@9fa00000", prop) == \
               fdtget(LIVE, "-t", "x", "/reserved-memory/ramoops@9FA00000", prop), prop
    assert fdtget(OURS, "/reserved-memory/ramoops@9fa00000", "compatible") == "ramoops"

def test_memory_size_is_left_to_the_bootloader():
    assert fdtget(OURS, "-t", "x", "/memory@80000000", "reg") == "0 80000000 0 0"
