#!/usr/bin/env python3
"""Extract the Adreno 650 zap shader from the stock firmware and join it into one .mbn.

usage: tools/extract-gpu-zap.py BL_<...>.tar.md5 OUTDIR
       tools/extract-gpu-zap.py --non-hlos NON-HLOS.bin OUTDIR

BL tar -> NON-HLOS.bin.lz4 (lz4 -dc) -> FAT16 image -> /image/a650_zap.{mdt,b00..b02}
-> OUTDIR/a650_zap.mbn (tools/pil-squash.py logic). Read only; nothing talks to the tablet.
The zap shader is signed by Samsung/Qualcomm for this device: keep OUTDIR out of git
(build/ is ignored) and install it on the tablet as
/lib/firmware/qcom/sm8250/samsung/gts7xl/a650_zap.mbn (path set in the DTS).

The FAT reader below only handles what this image needs: FAT12/16, 8.3 and VFAT long
names, one subdirectory level.
"""
import importlib.util
import struct
import subprocess
import sys
import tarfile
from pathlib import Path


def fat_files(img: bytes, dirname: str, prefix: str) -> dict[str, bytes]:
    bps, spc, rsvd, nfats, rootents = struct.unpack_from("<HBHBH", img, 11)
    spf, = struct.unpack_from("<H", img, 22)
    total = struct.unpack_from("<H", img, 19)[0] or struct.unpack_from("<I", img, 32)[0]
    fat_off = rsvd * bps
    root_off = fat_off + nfats * spf * bps
    data_off = root_off + ((rootents * 32 + bps - 1) // bps) * bps
    clus = spc * bps
    nclus = (total * bps - data_off) // clus
    fat16 = nclus >= 4085

    def next_cluster(c):
        if fat16:
            return struct.unpack_from("<H", img, fat_off + 2 * c)[0]
        v = struct.unpack_from("<H", img, fat_off + c * 3 // 2)[0]
        return v >> 4 if c & 1 else v & 0xFFF

    def chain(c, size=None):
        out = bytearray()
        end = 0xFFF8 if fat16 else 0xFF8
        while 2 <= c < end:
            o = data_off + (c - 2) * clus
            out += img[o:o + clus]
            c = next_cluster(c)
        return bytes(out if size is None else out[:size])

    def entries(raw):
        lfn = {}
        for i in range(0, len(raw), 32):
            e = raw[i:i + 32]
            if e[0] == 0:
                break
            if e[0] == 0xE5:
                lfn = {}
                continue
            if e[11] == 0x0F:  # VFAT long name part: 13 UTF-16 chars
                lfn[e[0] & 0x1F] = (e[1:11] + e[14:26] + e[28:32]).decode("utf-16-le", "replace")
                continue
            if lfn:
                name = "".join(lfn[k] for k in sorted(lfn)).split("\0")[0]
            else:
                base = e[0:8].decode("ascii", "replace").strip()
                ext = e[8:11].decode("ascii", "replace").strip()
                name = base + ("." + ext if ext else "")
            lfn = {}
            hi, = struct.unpack_from("<H", e, 20)
            lo, size = struct.unpack_from("<HI", e, 26)
            yield name.lower(), e[11], (hi << 16) | lo, size

    root = img[root_off:data_off]
    sub = next((c for n, a, c, _ in entries(root) if n == dirname and a & 0x10), None)
    if sub is None:
        sys.exit(f"no /{dirname} directory in the FAT image")
    return {n: chain(c, size) for n, a, c, size in entries(chain(sub))
            if not a & 0x10 and n.startswith(prefix)}


def main() -> int:
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == "--non-hlos":
        img = Path(args[1]).read_bytes()
    elif len(args) == 2:
        with tarfile.open(args[0]) as t:
            lz = t.extractfile("NON-HLOS.bin.lz4").read()
        img = subprocess.run(["lz4", "-dc"], input=lz, capture_output=True, check=True).stdout
    else:
        sys.exit(__doc__)
    out = Path(args[-1])
    out.mkdir(parents=True, exist_ok=True)
    out.chmod(0o700)
    files = fat_files(img, "image", "a650_zap.")
    if "a650_zap.mdt" not in files:
        sys.exit("no image/a650_zap.mdt in NON-HLOS")
    split = out / "split"
    split.mkdir(exist_ok=True)
    for n, data in files.items():
        (split / n).write_bytes(data)
    spec = importlib.util.spec_from_file_location(
        "pil_squash", Path(__file__).with_name("pil-squash.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main(str(split / "a650_zap.mdt"), str(out / "a650_zap.mbn"))


if __name__ == "__main__":
    sys.exit(main())
