#!/usr/bin/env python3
"""Make a DTB that kexec can boot on the gts7xl.

On a real boot the shim copies the memory layout the ABL computed (/memory reg) into the
mainline DTB. kexec -l --dtb skips the shim, so the new DTB must get /memory from the
running kernel's own DTB (/sys/firmware/fdt, pulled over USB). /chosen (bootargs, initrd)
is filled in by kexec itself (--command-line / --reuse-cmdline, --initrd).

usage: kexec_dtb.py --new NEW.dtb --running RUNNING.fdt -o OUT.dtb
Needs fdtget/fdtput (dtc).
"""
import argparse, shutil, subprocess, sys


def fdt(*args):
    # fdtget -l exits 1 on the ABL-built /sys/firmware/fdt even though it prints the full
    # node list (seen on gts7xl r10); trust the output when there is some.
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode and not r.stdout.strip():
        raise subprocess.CalledProcessError(r.returncode, args, r.stdout, r.stderr)
    return r.stdout


def memory_node(dtb):
    for name in fdt("fdtget", "-l", dtb, "/").split():
        if name == "memory" or name.startswith("memory@"):
            return "/" + name
    # The listing of the ABL-built tree stops early; probe the usual names directly.
    for path in ("/memory@80000000", "/memory"):
        if subprocess.run(["fdtget", "-t", "s", dtb, path, "device_type"],
                          capture_output=True, text=True).stdout.strip() == "memory":
            return path
    raise SystemExit(f"kexec_dtb: no /memory node in {dtb}")


def patch(new, running, out):
    src, dst = memory_node(running), memory_node(new)
    reg = fdt("fdtget", "-t", "x", running, src, "reg").split()
    if not reg or len(reg) % 4:
        raise SystemExit(f"kexec_dtb: unexpected {src}/reg in {running}: {reg}")
    shutil.copyfile(new, out)
    subprocess.run(["fdtput", "-t", "x", out, dst, "reg", *reg], check=True)
    return dst, reg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--new", required=True)
    ap.add_argument("--running", required=True)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)
    node, reg = patch(a.new, a.running, a.out)
    print(f"{a.out}: {node} reg = {len(reg) // 4} ranges from {a.running}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
