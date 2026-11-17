# tests/test_gpu_zap.py
"""Adreno 650: zap shader tooling and the DTS nodes that use it.

The zap shader is Samsung-signed and comes split (a650_zap.mdt + .bNN) in the stock
NON-HLOS FAT image. tools/extract-gpu-zap.py reads it, tools/pil-squash.py joins it.
Set GTS7XL_LINUX to test another linux worktree (e.g. ../linux-gpu).
"""
import importlib.util
import os
import re
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
LINUX = Path(os.environ.get("GTS7XL_LINUX", ROOT / "linux"))
DTS = LINUX / "arch" / "arm64" / "boot" / "dts" / "qcom" / "sm8250-samsung-gts7xl.dts"


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def elf32(phdrs):
    """ELF header + program headers; phdrs = [(type, offset, filesz)]."""
    eh = bytearray(52)
    eh[:4] = b"\x7fELF"
    eh[4], eh[5] = 1, 1
    struct.pack_into("<IHH", eh, 0x1C, 52, 0, 0)
    struct.pack_into("<HH", eh, 0x2A, 32, len(phdrs))
    for t, off, sz in phdrs:
        eh += struct.pack("<IIIIIIII", t, off, 0, 0, sz, sz, 0, 0)
    return bytes(eh)


def test_pil_squash_places_segments(tmp_path):
    hdr = elf32([(0, 0, 0), (0, 0x100, 0x10), (1, 0x200, 0x20)])
    (tmp_path / "x.mdt").write_bytes(hdr + b"\0" * (0x100 - len(hdr)) + b"H" * 0x10)
    (tmp_path / "x.b02").write_bytes(b"C" * 0x20)
    out = tmp_path / "x.mbn"
    load("pil_squash", "pil-squash.py").main(str(tmp_path / "x.mdt"), str(out))
    data = out.read_bytes()
    assert len(data) == 0x220
    assert data[0x100:0x110] == b"H" * 0x10  # from the .mdt (no x.b01)
    assert data[0x200:0x220] == b"C" * 0x20  # from x.b02


def test_pil_squash_rejects_short_segment(tmp_path):
    hdr = elf32([(1, 0x100, 0x20)])
    (tmp_path / "x.mdt").write_bytes(hdr)
    (tmp_path / "x.b00").write_bytes(b"C" * 0x10)
    with pytest.raises(SystemExit):
        load("pil_squash", "pil-squash.py").main(str(tmp_path / "x.mdt"), str(tmp_path / "o"))


def fat16_image():
    """Tiny FAT16: root has an LFN-named dir 'image' holding 'a650_zap.mdt' (LFN)."""
    bps, spc, rsvd, nfats, rootents, spf, total = 512, 1, 1, 2, 16, 32, 5000
    img = bytearray(total * bps)
    struct.pack_into("<HBHBHH", img, 11, bps, spc, rsvd, nfats, rootents, total)
    struct.pack_into("<H", img, 22, spf)
    fat = rsvd * bps
    root = fat + nfats * spf * bps
    data = root + rootents * 32

    def lfn(name, seq=1):
        chars = (name.encode("utf-16-le") + b"\0\0").ljust(26, b"\xff")
        e = bytearray(32)
        e[0] = 0x40 | seq
        e[1:11], e[14:26], e[28:32] = chars[0:10], chars[10:22], chars[22:26]
        e[11] = 0x0F
        return bytes(e)

    def short(name, attr, clus, size):
        e = bytearray(32)
        e[0:11] = name
        e[11] = attr
        struct.pack_into("<HI", e, 26, clus, size)
        return bytes(e)

    payload = b"ZAP!" * 300  # 1200 bytes: clusters 3..5 (cluster 2 is the dir)
    img[root:root + 64] = lfn("image") + short(b"IMAGE~1    ", 0x10, 2, 0)
    d = data  # cluster 2
    img[d:d + 64] = lfn("a650_zap.mdt") + short(b"A650_Z~1MDT", 0x20, 3, len(payload))
    for c, nxt in ((2, 0xFFFF), (3, 4), (4, 5), (5, 0xFFFF)):
        struct.pack_into("<H", img, fat + 2 * c, nxt)
    off = data + (3 - 2) * bps
    img[off:off + len(payload)] = payload
    return bytes(img), payload


def test_fat_reader_finds_lfn_zap():
    img, payload = fat16_image()
    files = load("extract_gpu_zap", "extract-gpu-zap.py").fat_files(img, "image", "a650_zap.")
    assert files == {"a650_zap.mdt": payload}


def block(src, label):
    m = re.search(r"^&" + re.escape(label) + r" \{\n(.*?)^\};", src, re.S | re.M)
    return m.group(1) if m else None


@pytest.mark.skipif(not DTS.exists(), reason="needs a linux checkout")
def test_gpu_nodes_consistent():
    src = DTS.read_text()
    # gpu_mem must stay at the stock pil_gpu region (zap shader load address).
    assert re.search(r"gpu_mem: gpu@9031a000 \{\s*reg = <0x0 0x9031a000 0x0 0x2000>;", src)
    gpu, gmu, zap = block(src, "gpu"), block(src, "gmu"), block(src, "gpu_zap_shader")
    if gpu is None:
        pytest.skip("GPU not enabled in this tree")
    assert 'status = "okay";' in gpu
    assert gmu is not None and 'status = "okay";' in gmu, "GPU without GMU cannot power up"
    assert zap is not None
    assert 'firmware-name = "qcom/sm8250/samsung/gts7xl/a650_zap.mbn";' in zap
