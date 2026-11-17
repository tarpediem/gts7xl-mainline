#!/usr/bin/env python3
"""Build the boot shim of the gts7xl around a mainline Image and DTB.

The Samsung ABL only goes through with the vendor DTB (on the Tab S7 family a mainline
DTB ends in "Custom Binary Blocked By OEM Lock"), but it runs whatever is in the kernel
slot. The output of this tool is that "kernel": a small position-independent program
(tools/shim/) followed by the mainline DTB and the mainline Image. The ABL loads it like
the stock kernel and passes the vendor DTB it prepared; the shim copies /memory, the
command line and the ramdisk location into the mainline DTB and enters the Image.
tools/mkrecovery.py --kernel <output> --stock-dt then packs it for the RECOVERY partition.

Layout of the output (also its layout in RAM, the ABL loads it in one piece):

    0x000000  arm64 Image header (text_offset 0x80000, image_size = reserve), shim code
    ...       mainline DTB
    0x180000  mainline Image (2 MiB aligned once loaded at <2 MiB boundary> + 0x80000)

image_size reserves everything the shim writes to: the Image moved to the next 2 MiB
boundary if needed, its BSS, 1 MiB for the patched DTB and the stack. The file is not
padded to image_size (neither is the stock kernel: 53.6 MB on disk, image_size 73.5 MB).

Needs clang, llvm-objcopy, llvm-readelf and an lld. Linker, first match:
  $SHIM_LD, ld.lld from PATH, `uv run --with ziglang==<pinned>` (zig ships an ld.lld).
libfdt comes from the kernel tree (linux/scripts/dtc/libfdt).
"""
import argparse, gzip, hashlib, os, shlex, shutil, struct, subprocess, sys, tempfile
from pathlib import Path

SRC = Path(__file__).parent / "shim"
LIBFDT_FILES = ("fdt.c", "fdt_ro.c", "fdt_rw.c", "fdt_wip.c",
                "fdt.h", "libfdt.h", "libfdt_env.h", "libfdt_internal.h")
SOURCES = ("start.S", "payload.S", "shim.c", "string.c", "fdt.c", "fdt_ro.c", "fdt_rw.c", "fdt_wip.c")
ZIGLANG = "ziglang==0.17.1"          # fallback linker: LLD 22.1.8

MIB = 1 << 20
TEXT_OFFSET = 0x80000                # as in the stock kernel header
KERNEL_OFFSET = 0x180000             # TEXT_OFFSET + KERNEL_OFFSET = 2 MiB
DTB_ROOM = 1 * MIB                   # room for the patched mainline DTB
STACK_ROOM = 0x10000
ARM64_MAGIC = b"ARM\x64"
# Bootloader splash = the simple-framebuffer node of sm8250-samsung-gts7xl.dts
FB_BASE, FB_WIDTH, FB_HEIGHT = 0x9c000000, 2800, 1752


def image_info(image: bytes):
    """(text_offset, image_size) of an arm64 Image the shim can carry."""
    if len(image) < 64 or image[56:60] != ARM64_MAGIC:
        raise ValueError("not an arm64 Image (no ARM\\x64 magic at offset 56)")
    text_offset, image_size = struct.unpack_from("<QQ", image, 8)
    if text_offset != 0:
        raise ValueError(f"Image text_offset is {text_offset:#x}; the shim only places text_offset 0 kernels")
    if image_size < len(image):
        raise ValueError(f"Image header image_size {image_size:#x} is smaller than the file")
    return text_offset, image_size


def reserve_for(image_size: int) -> int:
    """image_size to announce to the ABL: everything the shim may write to, 2 MiB aligned."""
    worst = KERNEL_OFFSET + 2 * MIB + image_size + 0x10000 + DTB_ROOM + STACK_ROOM
    return (worst + 2 * MIB - 1) & ~(2 * MIB - 1)


def load_kernel(path) -> bytes:
    data = Path(path).read_bytes()
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def find_linker():
    """Command prefix that runs an lld in GNU mode."""
    if os.environ.get("SHIM_LD"):
        return shlex.split(os.environ["SHIM_LD"])
    if shutil.which("ld.lld"):
        return ["ld.lld"]
    if shutil.which("uv"):
        return ["uv", "run", "--no-project", "--with", ZIGLANG, "python", "-m", "ziglang", "ld.lld"]
    raise RuntimeError("no linker: install lld, or uv (for the pinned ziglang ld.lld), or set SHIM_LD")


def run(cmd):
    res = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if res.returncode:
        raise RuntimeError(f"{' '.join(str(c) for c in cmd)}\n{res.stdout}{res.stderr}")
    return res.stdout


def build(kernel, dtb, libfdt, out, fb=(FB_BASE, FB_WIDTH, FB_HEIGHT)) -> dict:
    """Build the shim around `kernel` (Image or Image.gz) and `dtb`; returns the facts worth logging."""
    image = load_kernel(kernel)
    _, image_size = image_info(image)
    dtb_data = Path(dtb).read_bytes()
    if dtb_data[:4] != b"\xd0\x0d\xfe\xed":
        raise ValueError(f"{dtb}: not a device tree blob")
    if len(dtb_data) + 0x4000 > DTB_ROOM:        # room for the properties the shim adds
        raise ValueError(f"{dtb}: {len(dtb_data)} bytes do not fit the {DTB_ROOM} bytes reserved for the DTB")
    libfdt = Path(libfdt)
    for name in LIBFDT_FILES:
        if not (libfdt / name).is_file():
            raise ValueError(f"{libfdt}: {name} missing (expected linux/scripts/dtc/libfdt)")
    reserve = reserve_for(image_size)
    linker = find_linker()

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src, obj = tmp / "src", tmp / "obj"
        shutil.copytree(SRC, src)
        obj.mkdir()
        for name in LIBFDT_FILES:
            shutil.copy(libfdt / name, src / name)
        (tmp / "Image").write_bytes(image)
        (tmp / "mainline.dtb").write_bytes(dtb_data)
        (src / "payload.S").write_text(
            f'\t.section .payload.dtb, "a"\n\t.incbin "{tmp}/mainline.dtb"\n'
            f'\t.section .payload.kernel, "a"\n\t.incbin "{tmp}/Image"\n')
        cflags = ["--target=aarch64-none-elf", "-ffreestanding", "-fno-builtin", "-nostdlib", "-O2",
                  "-mgeneral-regs-only", "-mstrict-align", "-fno-pic", "-fno-pie", "-mcmodel=small",
                  "-fno-stack-protector", "-fno-asynchronous-unwind-tables", "-fno-unwind-tables",
                  f"-DSHIM_RESERVE={reserve}", f"-DSHIM_DTB_ROOM={DTB_ROOM}", f"-DSHIM_STACK_ROOM={STACK_ROOM}",
                  f"-DSHIM_FB_BASE={fb[0]}UL", f"-DSHIM_FB_WIDTH={fb[1]}UL", f"-DSHIM_FB_HEIGHT={fb[2]}UL",
                  f"-I{src / 'include'}", f"-I{src}", "-Wall", "-Werror"]
        objects = []
        for name in SOURCES:
            o = obj / (Path(name).stem + ".o")
            run(["clang", *cflags, "-c", src / name, "-o", o])
            objects.append(o)
        # MMU off, load address unknown: only PC-relative references may survive.
        relocs = run(["llvm-readelf", "-r", *objects])
        bad = [l for l in relocs.splitlines() if any(k in l for k in ("R_AARCH64_ABS64", "R_AARCH64_ABS32", "R_AARCH64_PREL64"))]
        if bad:
            raise RuntimeError("absolute relocation in the shim, it would break at another load address:\n" + "\n".join(bad))
        run([*linker, "-T", src / "shim.lds", f"--defsym=SHIM_KERNEL_OFFSET={KERNEL_OFFSET:#x}",
             "-nostdlib", "--no-pie", "--build-id=none", *objects, "-o", tmp / "shim.elf"])
        run(["llvm-objcopy", "-O", "binary", tmp / "shim.elf", tmp / "shim.bin"])
        blob = (tmp / "shim.bin").read_bytes()
        linker_version = run([*linker, "--version"]).strip()
        clang_version = run(["clang", "--version"]).splitlines()[0]

    # What the ABL and the shim rely on, checked on the final bytes.
    text_offset, announced, flags = struct.unpack_from("<QQQ", blob, 8)
    if blob[56:60] != ARM64_MAGIC or text_offset != TEXT_OFFSET or announced != reserve or flags != 0xa:
        raise RuntimeError("shim header is not what the ABL expects")
    if blob[KERNEL_OFFSET:] != image:
        raise RuntimeError(f"Image is not at offset {KERNEL_OFFSET:#x} of the shim")
    if blob.find(dtb_data) < 64 or blob.find(dtb_data) + len(dtb_data) > KERNEL_OFFSET:
        raise RuntimeError("mainline DTB is not in front of the Image")
    Path(out).write_bytes(blob)
    return {"out": str(out), "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
            "reserve": reserve, "image_bytes": len(image), "image_size": image_size,
            "image_sha256": hashlib.sha256(image).hexdigest(),
            "dtb_bytes": len(dtb_data), "dtb_sha256": hashlib.sha256(dtb_data).hexdigest(),
            "clang": clang_version, "linker": linker_version}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kernel", required=True, help="mainline arm64 Image, or Image.gz / vmlinuz (gunzipped here)")
    ap.add_argument("--dtb", required=True, help="mainline DTB the kernel must run with")
    ap.add_argument("--libfdt", default=str(Path(__file__).parent.parent / "linux" / "scripts" / "dtc" / "libfdt"),
                    help="libfdt sources (default: linux/scripts/dtc/libfdt)")
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args(argv)
    try:
        info = build(a.kernel, a.dtb, a.libfdt, a.output)
    except (ValueError, RuntimeError, OSError) as e:
        sys.exit(f"mkshim.py: {e}")
    print(f"OK {info['out']}: {info['size']} bytes, sha256 {info['sha256']}")
    print(f"  announces image_size {info['reserve']:#x} ({info['reserve'] // MIB} MiB), text_offset {TEXT_OFFSET:#x}")
    print(f"  Image {info['image_bytes']} bytes (image_size {info['image_size']:#x}) sha256 {info['image_sha256'][:16]}")
    print(f"  DTB {info['dtb_bytes']} bytes sha256 {info['dtb_sha256'][:16]}")
    print(f"  {info['clang']}; {info['linker']}")


if __name__ == "__main__":
    main()
