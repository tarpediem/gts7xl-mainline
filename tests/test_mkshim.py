# tests/test_mkshim.py
"""Boot shim: layout checks in Python, and the real aarch64 binary run in an emulator.

The emulated runs need clang, an lld (see mkshim.find_linker), dtc/fdtget and the
unicorn package:  uv run --no-project --with pytest --with unicorn pytest tests -q
"""
import shutil, struct, subprocess, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import mkshim

ROOT = Path(__file__).parent.parent
LIBFDT = ROOT / "linux" / "scripts" / "dtc" / "libfdt"
MIB = 1 << 20

# ---------------------------------------------------------------- pure layout

def fake_image(size=3 * MIB, image_size=4 * MIB, text_offset=0, magic=b"ARM\x64"):
    """An arm64 Image: 64-byte header, then a pattern that makes a moved copy checkable."""
    body = bytearray((i * 7 + 3) & 0xff for i in range(256)) * (size // 256)
    struct.pack_into("<QQQ", body, 8, text_offset, image_size, 0xa)
    body[56:60] = magic
    body[0:4] = struct.pack("<I", 0x14000000)        # "b ." : the emulator stops here
    return bytes(body)

def test_image_info_reads_the_arm64_header():
    assert mkshim.image_info(fake_image()) == (0, 4 * MIB)

def test_image_info_refuses_what_is_not_an_arm64_image():
    with pytest.raises(ValueError):
        mkshim.image_info(fake_image(magic=b"XXXX"))
    with pytest.raises(ValueError):
        mkshim.image_info(b"\0" * 32)

def test_image_info_refuses_a_text_offset():
    """The shim places the Image on a 2 MiB boundary: only right for text_offset 0."""
    with pytest.raises(ValueError):
        mkshim.image_info(fake_image(text_offset=0x80000))

def test_reserve_covers_the_worst_case_move_and_is_2mib_aligned():
    size = 0x2f40000
    reserve = mkshim.reserve_for(size)
    assert reserve % (2 * MIB) == 0
    # loaded anywhere: Image moved up by less than 2 MiB, 64K-aligned DTB, DTB room, stack
    worst = mkshim.KERNEL_OFFSET + 2 * MIB + size + 0x10000 + mkshim.DTB_ROOM + mkshim.STACK_ROOM
    assert worst <= reserve < worst + 2 * MIB

def test_load_gunzips_a_compressed_kernel(tmp_path):
    import gzip
    img = fake_image()
    (tmp_path / "vmlinuz").write_bytes(gzip.compress(img))
    (tmp_path / "Image").write_bytes(img)
    assert mkshim.load_kernel(tmp_path / "vmlinuz") == img
    assert mkshim.load_kernel(tmp_path / "Image") == img

# ------------------------------------------------------------ the real binary

def toolchain_missing():
    if not all(shutil.which(t) for t in ("clang", "llvm-objcopy", "llvm-readelf", "dtc", "fdtget")):
        return "clang/llvm-objcopy/llvm-readelf/dtc/fdtget not installed"
    if not LIBFDT.is_dir():
        return "linux/scripts/dtc/libfdt not checked out"
    try:
        mkshim.find_linker()
    except RuntimeError as e:
        return str(e)
    return None

needs_toolchain = pytest.mark.skipif(toolchain_missing() is not None, reason=str(toolchain_missing()))

MAINLINE_DTS = """/dts-v1/;
/ { #address-cells = <2>; #size-cells = <2>; model = "mainline";
    chosen { stdout-path = "keep-me"; };
    memory@80000000 { device_type = "memory"; reg = <0x0 0x80000000 0x0 0x0>; };
};"""
BOOTARGS = "console=tty0 pmos.debug-shell androidboot.verifiedbootstate=orange"
MEMREG = "0x00 0x80000000 0x00 0x3bb00000 0x01 0x80000000 0x01 0x00 0x00 0xc0000000 0x00 0xc0000000"

def abl_dts(initrd=(0xaff16000, 0xafffe90f), bootargs=BOOTARGS, memory=True):
    chosen = f'bootargs = "{bootargs}"; kaslr-seed = <0x1234 0x5678>;'
    if initrd:
        chosen += f" linux,initrd-start = <0x0 {initrd[0]:#x}>; linux,initrd-end = <0x0 {initrd[1]:#x}>;"
    mem = f'memory {{ device_type = "memory"; ddr_device_type = <8>; reg = <{MEMREG}>; }};' if memory else ""
    return f"""/dts-v1/;
/ {{ #address-cells = <2>; #size-cells = <2>; model = "vendor";
    chosen {{ {chosen} }};
    {mem}
}};"""

def dtc(text, path):
    subprocess.run(["dtc", "-q", "-I", "dts", "-O", "dtb", "-o", str(path), "-"], input=text.encode(), check=True)
    return path

@pytest.fixture(scope="module")
def shim(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("shim")
    image = fake_image()
    (tmp / "Image").write_bytes(image)
    dtb = dtc(MAINLINE_DTS, tmp / "mainline.dtb")
    out = tmp / "shim-Image"
    info = mkshim.build(tmp / "Image", dtb, LIBFDT, out)
    return {"path": out, "blob": out.read_bytes(), "image": image, "info": info, "tmp": tmp}

@needs_toolchain
def test_shim_header_looks_like_the_stock_kernel_to_the_abl(shim):
    blob = shim["blob"]
    text_offset, image_size, flags, res2, res3 = struct.unpack_from("<5Q", blob, 8)
    assert blob[56:60] == b"ARM\x64"
    assert text_offset == 0x80000 and flags == 0xa and res3 == 0xecefecef
    assert image_size == mkshim.reserve_for(4 * MIB) == shim["info"]["reserve"]
    assert struct.unpack_from("<I", blob, 0)[0] >> 26 == 0x5          # code0 is a branch

@needs_toolchain
def test_shim_carries_the_image_at_the_kernel_offset_and_the_dtb(shim):
    blob, image = shim["blob"], shim["image"]
    assert blob[mkshim.KERNEL_OFFSET:] == image                       # not padded to image_size
    assert (shim["tmp"] / "mainline.dtb").read_bytes() in blob[:mkshim.KERNEL_OFFSET]

FB_BASE, FB_BYTES = 0x9c000000, 2800 * 1752 * 4
RAM_BASE, RAM_SIZE = 0xa0000000, 0x10000000
ABL_DTB_ADDR = 0xafd15000

def emulate(shim, abl_dtb: bytes, load=0xa0080000, dtb_addr=ABL_DTB_ADDR, max_insn=40_000_000):
    """Run the shim as the ABL would start it. Returns (uc, pc)."""
    uc_mod = pytest.importorskip("unicorn")
    from unicorn import arm64_const as c
    uc = uc_mod.Uc(uc_mod.UC_ARCH_ARM64, uc_mod.UC_MODE_ARM)
    uc.mem_map(RAM_BASE, RAM_SIZE)
    uc.mem_map(FB_BASE, 0x2400000)
    uc.mem_write(load, shim["blob"])
    uc.mem_write(dtb_addr, abl_dtb)
    uc.reg_write(c.UC_ARM64_REG_X0, dtb_addr)
    kernel = (load + mkshim.KERNEL_OFFSET + 2 * MIB - 1) & ~(2 * MIB - 1)
    try:
        uc.emu_start(load, kernel, count=max_insn)      # stops when the shim branches into the Image
    except uc_mod.UcError as e:
        pytest.fail(f"emulation fault at pc={uc.reg_read(c.UC_ARM64_REG_PC):#x}: {e}")
    return uc, uc.reg_read(c.UC_ARM64_REG_PC)

def pixel(uc, index=0):
    return struct.unpack("<I", uc.mem_read(FB_BASE + 4 * index, 4))[0]

def fdtget(dtb: bytes, tmp, node, prop, fmt=None):
    path = tmp / "probe.dtb"; path.write_bytes(dtb)
    cmd = ["fdtget"] + (["-t", fmt] if fmt else []) + [str(path), node, prop]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()

def patched_dtb(uc, addr):
    size = struct.unpack(">I", uc.mem_read(addr + 4, 4))[0]
    assert uc.mem_read(addr, 4) == b"\xd0\x0d\xfe\xed" and size < mkshim.DTB_ROOM
    return bytes(uc.mem_read(addr, size))

@needs_toolchain
def test_shim_enters_the_image_with_the_abl_boot_data(shim, tmp_path):
    c = pytest.importorskip("unicorn.arm64_const")
    abl = dtc(abl_dts(), tmp_path / "abl.dtb").read_bytes()
    uc, pc = emulate(shim, abl)
    kernel = 0xa0200000                                  # 0xa0080000 + KERNEL_OFFSET: no move needed
    assert pc == kernel
    assert bytes(uc.mem_read(kernel, len(shim["image"]))) == shim["image"]
    assert [uc.reg_read(r) for r in (c.UC_ARM64_REG_X1, c.UC_ARM64_REG_X2, c.UC_ARM64_REG_X3)] == [0, 0, 0]
    dtb_addr = uc.reg_read(c.UC_ARM64_REG_X0)
    assert dtb_addr == kernel + 4 * MIB and dtb_addr % 8 == 0          # right after image_size (BSS included)
    out = patched_dtb(uc, dtb_addr)
    assert fdtget(out, tmp_path, "/", "model") == "mainline"           # still our tree
    assert fdtget(out, tmp_path, "/chosen", "stdout-path") == "keep-me"
    assert fdtget(out, tmp_path, "/chosen", "bootargs") == BOOTARGS
    assert fdtget(out, tmp_path, "/chosen", "linux,initrd-start", "x") == "0 aff16000"
    assert fdtget(out, tmp_path, "/chosen", "linux,initrd-end", "x") == "0 afffe90f"
    assert fdtget(out, tmp_path, "/chosen", "kaslr-seed", "x") == "1234 5678"
    assert fdtget(out, tmp_path, "/memory@80000000", "reg", "x") == " ".join(f"{int(v, 16):x}" for v in MEMREG.split())
    assert pixel(uc) == 0xff00ff00 and pixel(uc, 2800 * 64) == 0       # green bar, 64 rows only

@needs_toolchain
def test_shim_moves_the_image_when_the_load_address_is_not_aligned(shim, tmp_path):
    abl = dtc(abl_dts(), tmp_path / "abl.dtb").read_bytes()
    uc, pc = emulate(shim, abl, load=0xa0090000)
    assert pc == 0xa0400000 and pc % (2 * MIB) == 0
    assert bytes(uc.mem_read(pc, len(shim["image"]))) == shim["image"]
    from unicorn import arm64_const as c
    out = patched_dtb(uc, uc.reg_read(c.UC_ARM64_REG_X0))
    assert fdtget(out, tmp_path, "/chosen", "bootargs") == BOOTARGS

def stopped_with(uc, pc, colour):
    """The shim painted the whole screen and never reached the Image."""
    assert pixel(uc) == colour and pixel(uc, 2800 * 1752 - 1) == colour
    assert not 0xa0200000 <= pc < 0xa0200000 + 3 * MIB

@needs_toolchain
def test_shim_stops_yellow_without_a_device_tree(shim):
    uc, pc = emulate(shim, b"\0" * 64, max_insn=60_000_000)
    stopped_with(uc, pc, 0xffffff00)

@needs_toolchain
def test_shim_stops_red_when_the_ramdisk_is_inside_its_window(shim, tmp_path):
    abl = dtc(abl_dts(initrd=(0xa0300000, 0xa0400000)), tmp_path / "abl.dtb").read_bytes()
    uc, pc = emulate(shim, abl, max_insn=60_000_000)
    stopped_with(uc, pc, 0xffff0000)

@needs_toolchain
def test_shim_stops_red_when_the_abl_dtb_is_inside_its_window(shim, tmp_path):
    abl = dtc(abl_dts(), tmp_path / "abl.dtb").read_bytes()
    uc, pc = emulate(shim, abl, dtb_addr=0xa0080000 + shim["info"]["reserve"] - 0x1000, max_insn=60_000_000)
    stopped_with(uc, pc, 0xffff0000)

@needs_toolchain
def test_shim_stops_cyan_without_a_memory_layout(shim, tmp_path):
    abl = dtc(abl_dts(memory=False), tmp_path / "abl.dtb").read_bytes()
    uc, pc = emulate(shim, abl, max_insn=60_000_000)
    stopped_with(uc, pc, 0xff00ffff)

@needs_toolchain
def test_shim_boots_without_ramdisk_or_cmdline(shim, tmp_path):
    """Only the memory layout is mandatory: the kernel log on screen beats a coloured halt."""
    text = abl_dts(initrd=None).replace(f'bootargs = "{BOOTARGS}";', "")
    abl = dtc(text, tmp_path / "abl.dtb").read_bytes()
    uc, pc = emulate(shim, abl)
    assert pc == 0xa0200000

@needs_toolchain
def test_build_refuses_a_dtb_larger_than_its_room(shim):
    tmp = shim["tmp"]
    (tmp / "huge.dtb").write_bytes(b"\xd0\x0d\xfe\xed" + b"\0" * mkshim.DTB_ROOM)
    with pytest.raises(ValueError):
        mkshim.build(tmp / "Image", tmp / "huge.dtb", LIBFDT, tmp / "nope")
    assert not (tmp / "nope").exists()

@needs_toolchain
def test_shim_is_quick_with_a_vendor_sized_device_tree(shim, tmp_path):
    """The ABL's DTB is ~800 KiB with /chosen at the end; caches are off, so no repeated walks."""
    filler = "".join(f'n{i} {{ compatible = "vendor,filler"; reg = <{i} 0 0 0>; data = "{"x" * 200}"; }};\n'
                     for i in range(3000))
    text = abl_dts().replace("chosen {", filler + "chosen {", 1)
    abl = dtc(text, tmp_path / "abl.dtb").read_bytes()
    assert len(abl) > 700_000
    uc, pc = emulate(shim, abl, max_insn=30_000_000)
    assert pc == 0xa0200000
    from unicorn import arm64_const as c
    out = patched_dtb(uc, uc.reg_read(c.UC_ARM64_REG_X0))
    assert fdtget(out, tmp_path, "/chosen", "bootargs") == BOOTARGS
