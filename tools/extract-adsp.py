#!/usr/bin/env python3
"""Extract the audio DSP (ADSP) firmware from the stock firmware and join it into one .mbn.

usage: tools/extract-adsp.py BL_<...>.tar.md5 OUTDIR
       tools/extract-adsp.py --non-hlos NON-HLOS.bin OUTDIR

BL tar -> NON-HLOS.bin.lz4 (lz4 -dc) -> FAT16 image -> /image/adsp.{mdt,b00..b20}
-> OUTDIR/adsp.mbn (tools/pil-squash.py logic), plus /image/adspr.jsn and adspua.jsn
(the protection-domain maps read by pd-mapper). Read only; nothing talks to the tablet.

adsp.mbn is signed by Samsung/Qualcomm for this device: keep OUTDIR out of git (build/ is
ignored) and install the three files on the tablet in
/lib/firmware/qcom/sm8250/samsung/gts7xl/ (firmware-name in the DTS). pd-mapper finds the
.jsn files by walking /lib/firmware, so they must sit next to adsp.mbn.

The FAT reader is the one of tools/extract-gpu-zap.py.
"""
import importlib.util
import subprocess
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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

    fat = load("extract_gpu_zap", "extract-gpu-zap.py")
    files = fat.fat_files(img, "image", "adsp")
    if "adsp.mdt" not in files:
        sys.exit("no image/adsp.mdt in NON-HLOS")
    split = out / "split"
    split.mkdir(exist_ok=True)
    for n, data in files.items():
        if n.startswith("adsp.") and n != "adsp.mbn":
            (split / n).write_bytes(data)
        elif n in ("adspr.jsn", "adspua.jsn"):
            (out / n).write_bytes(data)
    for jsn in ("adspr.jsn", "adspua.jsn"):
        if not (out / jsn).exists():
            sys.exit(f"no image/{jsn} in NON-HLOS")

    squash = load("pil_squash", "pil-squash.py")
    return squash.main(str(split / "adsp.mdt"), str(out / "adsp.mbn"))


if __name__ == "__main__":
    sys.exit(main())
