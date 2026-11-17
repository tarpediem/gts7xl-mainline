#!/usr/bin/env python3
"""Extract one Hexagon DSP firmware (adsp, cdsp or slpi) from the stock firmware as one .mbn.

usage: tools/extract-dsp.py NAME BL_<...>.tar.md5 OUTDIR
       tools/extract-dsp.py NAME --non-hlos NON-HLOS.bin OUTDIR

BL tar -> NON-HLOS.bin.lz4 (lz4 -dc) -> FAT16 image -> /image/NAME.{mdt,b00..}
-> OUTDIR/NAME.mbn (tools/pil-squash.py logic), plus every /image/NAME*.jsn (the
protection-domain maps read by pd-mapper; slpi: slpir.jsn, slpius.jsn). Read only;
nothing talks to the tablet. Same as tools/extract-adsp.py, for any DSP.

The images are signed by Samsung/Qualcomm for this device: keep OUTDIR out of git
(build/ is ignored) and install the files on the tablet in
/lib/firmware/qcom/sm8250/samsung/gts7xl/ (firmware-name in the DTS).
"""
import importlib.util
import subprocess
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ("adsp", "cdsp", "slpi")


def load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 3 or args[0] not in NAMES:
        sys.exit(__doc__)
    name = args[0]
    if len(args) == 4 and args[1] == "--non-hlos":
        img = Path(args[2]).read_bytes()
    elif len(args) == 3:
        with tarfile.open(args[1]) as t:
            lz = t.extractfile("NON-HLOS.bin.lz4").read()
        img = subprocess.run(["lz4", "-dc"], input=lz, capture_output=True, check=True).stdout
    else:
        sys.exit(__doc__)
    out = Path(args[-1])
    out.mkdir(parents=True, exist_ok=True)
    out.chmod(0o700)

    fat = load("extract_gpu_zap", "extract-gpu-zap.py")
    files = fat.fat_files(img, "image", name)
    if f"{name}.mdt" not in files:
        sys.exit(f"no image/{name}.mdt in NON-HLOS")
    split = out / f"split-{name}"
    split.mkdir(exist_ok=True)
    for n, data in files.items():
        if n.startswith(f"{name}.") and n != f"{name}.mbn":
            (split / n).write_bytes(data)
        elif n.endswith(".jsn"):
            (out / n).write_bytes(data)
            print(f"{n}: {len(data)} bytes")

    squash = load("pil_squash", "pil-squash.py")
    return squash.main(str(split / f"{name}.mdt"), str(out / f"{name}.mbn"))


if __name__ == "__main__":
    sys.exit(main())
