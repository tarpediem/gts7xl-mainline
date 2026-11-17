#!/usr/bin/env python3
"""Turn our signed boot image into an image for the RECOVERY partition of the gts7xl.

Why a separate image: when the Samsung ABL boots RECOVERY with a header v1/v2 image it
takes the DT overlays from the image's own recovery_dtbo section, not from the DTBO
partition (the stock recovery.img carries a full copy of the DT table). So our overlays
travel inside this image and the DTBO partition stays stock for One UI.

What changes compared with the input image: a recovery_dtbo section is added, and the
AVB hash footer is rebuilt for the recovery partition (name "recovery", size of the
stock recovery.img, so the footer lands on the last 64 bytes of the partition).
Kernel, ramdisk, DTB, load addresses, OS version, board name and cmdline are kept.

--stock-footer: instead of a test-key footer, keep the stock recovery's own AVB vbmeta
blob and footer at their stock offsets. For a device that keeps its stock vbmeta: the
recovery chain partition then verifies exactly as before on a normal boot (One UI sees no
change); only booting RECOVERY itself reports a hash mismatch, which an unlocked
bootloader tolerates the same way it tolerates the Magisk-patched BOOT.
"""
import argparse, struct, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sign_boot import KEY, stock_rollback_index  # read-only reuse
import dtbo

def die(msg):
    sys.exit(f"mkrecovery.py: {msg}")

def unpack(image: Path, outdir: Path) -> dict:
    res = subprocess.run(["unpack_bootimg", "--boot_img", str(image), "--out", str(outdir),
                          "--format=mkbootimg", "-0"], check=True, capture_output=True)
    words = [w.decode() for w in res.stdout.split(b"\0")]
    if words and words[-1] == "":
        words.pop()
    if len(words) % 2:
        die("unexpected unpack_bootimg output")
    return dict(zip(words[::2], words[1::2]))

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stock-recovery", required=True, help="stock recovery.img: gives partition size and rollback index")
    ap.add_argument("--recovery-dtbo", required=True, help="DT table for the recovery_dtbo section (dtbo.py noop)")
    ap.add_argument("--rollback-index", type=int)
    ap.add_argument("--stock-footer", action="store_true",
                    help="keep the stock recovery's AVB vbmeta blob and footer (for use with the stock vbmeta)")
    ap.add_argument("input"); ap.add_argument("output")
    a = ap.parse_args(argv)
    table, out = Path(a.recovery_dtbo), Path(a.output)
    try:
        dtbo.parse(table.read_bytes())
    except Exception as e:  # ValueError (magic) or struct.error (short file)
        die(f"{table}: not a DT table ({e})")
    partition_size = Path(a.stock_recovery).stat().st_size
    rollback = a.rollback_index if a.rollback_index is not None else stock_rollback_index(a.stock_recovery)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        opts = unpack(Path(a.input), tmp / "in")
        if opts.get("--header_version") != "2":
            die(f"input header version {opts.get('--header_version')}, expected 2")
        opts["--recovery_dtbo"] = str(table)
        subprocess.run(["mkbootimg", *[w for kv in opts.items() for w in kv], "--output", str(out)], check=True)
        unpack(out, tmp / "out")
        for comp in ("kernel", "ramdisk", "dtb"):
            if (tmp / "in" / comp).read_bytes() != (tmp / "out" / comp).read_bytes():
                die(f"repack changed {comp}")
        if (tmp / "out" / "recovery_dtbo").read_bytes() != table.read_bytes():
            die("repack changed recovery_dtbo")
    if out.stat().st_size + 69632 > partition_size:  # room for vbmeta blob + footer
        out.unlink()
        die(f"image does not fit the recovery partition ({partition_size} bytes)")
    if a.stock_footer:
        stock = Path(a.stock_recovery).read_bytes()
        footer = stock[-64:]
        if footer[:4] != b"AVBf":
            out.unlink(); die("stock recovery has no AVB footer")
        voff, vsize = struct.unpack_from(">QQ", footer, 20)
        img = out.read_bytes()
        if len(img) > voff or voff + vsize > partition_size - 64:
            out.unlink(); die(f"image ({len(img)} bytes) overlaps the stock vbmeta blob at {voff}")
        blob = stock[voff:voff + vsize]
        out.write_bytes(img + b"\0" * (voff - len(img)) + blob
                        + b"\0" * (partition_size - 64 - voff - vsize) + footer)
        print(f"OK {out} ({partition_size} bytes, stock AVB footer kept, recovery_dtbo {table.stat().st_size} bytes)")
        return
    subprocess.run(["avbtool", "add_hash_footer", "--image", str(out),
                    "--partition_size", str(partition_size), "--partition_name", "recovery",
                    "--algorithm", "SHA256_RSA4096", "--key", str(KEY),
                    "--rollback_index", str(rollback)], check=True)
    print(f"OK {out} ({partition_size} bytes, recovery_dtbo {table.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
