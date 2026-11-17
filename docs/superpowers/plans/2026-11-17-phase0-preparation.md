# Phase 0 — Build environment for the gts7xl mainline port — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** From the host, produce a signed, ABL-acceptable postmarketOS `boot.img` + rootfs for the Galaxy Tab S7+ 5G (gts7xl), built on the latest upstream stable 7.x kernel with a skeleton device tree — without flashing anything.

**Architecture:** pmbootstrap builds the rootfs, initramfs and a header-v2 boot.img from a fork of pmaports holding `device-samsung-gts7xl` and `linux-samsung-gts7xl`. The kernel is a local checkout of upstream stable built through `pmbootstrap envkernel`. Small Python tools post-process the boot.img for the Samsung ABL (stock header fields + AVB test-key footer), generate an empty DTBO, and wrap Heimdall.

**Tech Stack:** pmbootstrap 3.12 (Arch `extra`), Heimdall 2.2.2, dtc 1.8, avbtool/mkbootimg/unpack_bootimg (installed), Python 3 + pytest (run through `uv run --with pytest`), Linux stable 7.x.

**Spec:** `docs/specs/2026-11-17-gts7xl-mainline-design.md`

## Global Constraints

- Device: Galaxy Tab S7+ **5G**, SM-T976B, codename `gts7xl`. Never reuse values from the Wi-Fi variant (`gts7xlwifi`).
- Board IDs of the 5G variant: `<8 0>` … `<8 6>`; exact `qcom,msm-id`/`qcom,board-id` are read from the stock DTBs, never guessed.
- Kernel base: latest upstream **stable 7.x** release tag. `sm8250-mainline` (stops at v6.13) is a cherry-pick source only.
- Partitions that may ever be written: `BOOT`, `DTBO`, `VBMETA`, `RECOVERY`, `USERDATA`. Nothing else.
- **No flashing in phase 0.** No Heimdall command is executed against the device.
- Stock firmware: `<stock-firmware>/fw/` (AP_T976BXXS7DXH1…, `boot.img`). Read-only.
- Droidian reference: `<droidian-gts7xl>/` (read-only; `galaxy-tab-s7-plus-droidian/{testkey_rsa4096.pem,vbmeta-disabled.img,tools/build-bootimg.py}`).
- Code comments and docs in English. Commits in English, concise, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- `sudo` is refused inside Claude's shell; run privileged commands as `ssh localhost sudo …`.
- If a task stalls (two failed attempts on the same step), re-dispatch it on the **Fable** model.

## File map

| Path | Responsibility |
|---|---|
| `.gitignore` | keeps `linux/`, `pmaports/`, `build/`, `reference/raw/` out of this repo (they are separate repos or large artifacts) |
| `NOTES.md` | flash/build log (every image hash, every attempt) |
| `tools/dtbo.py` | parse and write Android DT-table images (`split`, `empty`) |
| `tools/sign_boot.py` | copy ABL-checked header fields from the stock boot.img, set cmdline, add AVB footer |
| `tools/flash.sh` | single Heimdall command, partition allow-list, `--dry-run` |
| `tools/extract-reference.sh` | pull stock boot.img/dtbo.img apart into readable reference files |
| `tools/keys/testkey_rsa4096.pem`, `tools/images/vbmeta-disabled.img` | copied from the Droidian port |
| `tests/test_dtbo.py`, `tests/test_sign_boot.py`, `tests/test_flash.sh` | tool tests |
| `reference/` | decompiled stock DTS, header dump, `ids.txt` |
| `pmaports/` (own git) | fork; `device/testing/device-samsung-gts7xl/`, `device/testing/linux-samsung-gts7xl/` |
| `linux/` (own git) | upstream stable, branch `gts7xl`, `arch/arm64/boot/dts/qcom/sm8250-samsung-gts7xl.dts` |

---

### Task 1: Host tools and workspace skeleton

**Files:**
- Create: `.gitignore`, `NOTES.md`, `tools/keys/testkey_rsa4096.pem`, `tools/images/vbmeta-disabled.img`
- Modify: `~/.claude/rules/changelog.md` (system log, top of today's section)

**Interfaces:**
- Produces: commands `pmbootstrap`, `heimdall`, `dtc`, `fdtget` on PATH; key and vbmeta paths used by Tasks 4-5.

- [ ] **Step 1: Check what is missing**

Run: `for c in pmbootstrap heimdall dtc fdtget avbtool mkbootimg unpack_bootimg uv lz4 aarch64-linux-gnu-gcc; do printf '%-24s' $c; command -v $c || echo MISSING; done`
Expected: `pmbootstrap`, `heimdall`, `dtc`, `fdtget` MISSING (state on 2026-11-17); others present except possibly `lz4`.

- [ ] **Step 2: Install from Arch `extra`**

Run: `ssh localhost sudo pacman -S --needed --noconfirm pmbootstrap heimdall dtc lz4`
Then rerun Step 1. Expected: no MISSING among pmbootstrap/heimdall/dtc/fdtget/lz4.

- [ ] **Step 3: Workspace files**

```bash
cd gts7xl-mainline
mkdir -p tools/keys tools/images tests reference
cp <droidian-gts7xl>/galaxy-tab-s7-plus-droidian/testkey_rsa4096.pem tools/keys/
cp <droidian-gts7xl>/galaxy-tab-s7-plus-droidian/vbmeta-disabled.img tools/images/
cat > .gitignore <<'EOF'
linux/
pmaports/
build/
reference/raw/
__pycache__/
.pytest_cache/
EOF
cat > NOTES.md <<'EOF'
# gts7xl mainline — build and flash log

One entry per build or flash: date, what was built/flashed (sha256 of each image),
what was observed. Newest at the top.
EOF
avbtool info_image --image tools/images/vbmeta-disabled.img | grep -i flags
```
Expected: `Flags: 2`.

- [ ] **Step 4: Log the system change**

Add under today's date at the top of `~/.claude/rules/changelog.md`:
`- **[HOST — OUTILS DU PORT MAINLINE TAB S7+]** pacman : pmbootstrap, heimdall, dtc, lz4 (extra). Retour arrière : pacman -R pmbootstrap heimdall dtc lz4.`

- [ ] **Step 5: Commit**

```bash
git add .gitignore NOTES.md tools/keys tools/images
git commit -m "Add workspace skeleton, AVB test key and disabled vbmeta"
```

---

### Task 2: DT-table tool (`tools/dtbo.py`)

**Files:**
- Create: `tools/dtbo.py`, `tests/test_dtbo.py`

**Interfaces:**
- Produces: `parse(data: bytes) -> list[Entry]`, `build(entries: list[Entry]) -> bytes`, CLI `python3 tools/dtbo.py split <dtbo.img> <outdir>` and `python3 tools/dtbo.py empty <out.img>`. `Entry = dataclass(id:int, rev:int, custom:tuple[int,int,int,int], blob:bytes)`.

Format (Android DT table, big-endian): header 32 bytes = magic `0xd7b7ab1e`, total_size, header_size(32), dt_entry_size(32), dt_entry_count, dt_entries_offset(32), page_size, version(0). Entry 32 bytes = dt_size, dt_offset, id, rev, custom[4].

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dtbo.py
import struct, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import dtbo

FDT = struct.pack(">II", 0xD00DFEED, 40) + b"\0" * 32  # fake 40-byte FDT

def test_empty_table_is_header_only():
    data = dtbo.build([])
    magic, total, hsize, esize, count, off, page, ver = struct.unpack(">8I", data[:32])
    assert (magic, total, hsize, esize, count, off) == (0xD7B7AB1E, 32, 32, 32, 0, 32)
    assert len(data) == 32

def test_roundtrip_two_entries():
    e = [dtbo.Entry(8, 0, (0, 0, 0, 0), FDT), dtbo.Entry(8, 6, (1, 2, 3, 4), FDT + b"x" * 8)]
    out = dtbo.parse(dtbo.build(e))
    assert [(x.id, x.rev, x.custom, x.blob) for x in out] == [(x.id, x.rev, x.custom, x.blob) for x in e]

def test_parse_rejects_bad_magic():
    import pytest
    with pytest.raises(ValueError):
        dtbo.parse(b"\0" * 64)

def test_cli_empty(tmp_path):
    out = tmp_path / "e.img"
    subprocess.run([sys.executable, "tools/dtbo.py", "empty", str(out)], check=True)
    assert out.read_bytes() == dtbo.build([])
```

- [ ] **Step 2: Run, expect failure**

Run: `uv run --with pytest pytest tests/test_dtbo.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'dtbo'`.

- [ ] **Step 3: Implement**

```python
#!/usr/bin/env python3
"""Read and write Android DT-table images (dtbo.img)."""
import struct, sys
from dataclasses import dataclass
from pathlib import Path

MAGIC = 0xD7B7AB1E
HDR = struct.Struct(">8I")
ENT = struct.Struct(">8I")

@dataclass
class Entry:
    id: int
    rev: int
    custom: tuple
    blob: bytes

def parse(data: bytes) -> list:
    magic, total, hsize, esize, count, off, _page, _ver = HDR.unpack_from(data, 0)
    if magic != MAGIC:
        raise ValueError(f"bad DT table magic {magic:#x}")
    out = []
    for i in range(count):
        size, doff, eid, rev, *custom = ENT.unpack_from(data, off + i * esize)
        out.append(Entry(eid, rev, tuple(custom), data[doff:doff + size]))
    return out

def build(entries: list, page_size: int = 4096) -> bytes:
    off = HDR.size + ENT.size * len(entries)
    table, blobs = b"", b""
    for e in entries:
        table += ENT.pack(len(e.blob), off + len(blobs), e.id, e.rev, *e.custom)
        blobs += e.blob
    total = HDR.size + len(table) + len(blobs)
    return HDR.pack(MAGIC, total, HDR.size, ENT.size, len(entries), HDR.size, page_size, 0) + table + blobs

def main(argv):
    if argv[:1] == ["empty"] and len(argv) == 2:
        Path(argv[1]).write_bytes(build([]))
    elif argv[:1] == ["split"] and len(argv) == 3:
        outdir = Path(argv[2]); outdir.mkdir(parents=True, exist_ok=True)
        for i, e in enumerate(parse(Path(argv[1]).read_bytes())):
            name = f"{i:02d}-id{e.id}-rev{e.rev}.dtbo"
            (outdir / name).write_bytes(e.blob)
            print(name, "custom=" + ",".join(map(str, e.custom)))
    else:
        sys.exit("usage: dtbo.py empty OUT | dtbo.py split DTBO OUTDIR")

if __name__ == "__main__":
    main(sys.argv[1:])
```

- [ ] **Step 4: Run, expect pass**

Run: `uv run --with pytest pytest tests/test_dtbo.py -q` → `4 passed`.
Sanity on a real image: `python3 tools/dtbo.py split <droidian-gts7xl>/flash-ready/dtbo-5g.img /tmp/claude-1000/dtbo-check` prints 7 lines `id8-rev0` … `id8-rev6`.

- [ ] **Step 5: Commit**

```bash
git add tools/dtbo.py tests/test_dtbo.py
git commit -m "Add DT-table tool: split and empty dtbo images"
```

---

### Task 3: Stock reference extraction

**Files:**
- Create: `tools/extract-reference.sh`
- Generated (committed): `reference/stock-boot-header.txt`, `reference/ids.txt`, `reference/stock-base-*.dts`, `reference/stock-overlay-*.dts`
- Generated (ignored): `reference/raw/`

**Interfaces:**
- Consumes: `tools/dtbo.py split` (Task 2).
- Produces: `reference/stock-boot-header.txt` in `mkbootimg` argument format (read by Task 4 and Task 6); `reference/ids.txt` lines `FILE: qcom,msm-id = <...>; qcom,board-id = <...>;` (read by Task 7).

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Extract readable references from the stock T976B firmware. Read-only on inputs.
set -euo pipefail
FW=${FW:-$HOME/Work/samsung/stock-t976b/fw}
OUT=${OUT:-$(dirname "$0")/../reference}
RAW=$OUT/raw
mkdir -p "$RAW"

# 1. stock boot.img header (mkbootimg arg format) + its DTB
unpack_bootimg --boot_img "$FW/boot.img" --out "$RAW/boot" --format=mkbootimg > "$OUT/stock-boot-header.txt"
unpack_bootimg --boot_img "$FW/boot.img" --out "$RAW/boot" > "$RAW/boot-info.txt"

# 2. stock dtbo.img from the AP tarball
tar -xf "$FW"/AP_*.tar.md5 -C "$RAW" dtbo.img.lz4
lz4 -dfq "$RAW/dtbo.img.lz4" "$RAW/dtbo.img"
python3 "$(dirname "$0")/dtbo.py" split "$RAW/dtbo.img" "$RAW/overlays" > "$OUT/stock-overlays.txt"

# 3. decompile: base DTBs (the boot.img dtb may hold several concatenated FDTs)
python3 - "$RAW/boot/dtb" "$RAW/base" <<'PY'
import sys, struct, pathlib
data = pathlib.Path(sys.argv[1]).read_bytes(); out = pathlib.Path(sys.argv[2]); out.mkdir(exist_ok=True)
i = n = 0
while i + 8 <= len(data):
    magic, size = struct.unpack_from(">II", data, i)
    if magic != 0xD00DFEED: break
    (out / f"{n:02d}.dtb").write_bytes(data[i:i+size]); i += size; n += 1
print(n, "base dtbs")
PY
for f in "$RAW"/base/*.dtb;     do dtc -q -I dtb -O dts -o "$OUT/stock-base-$(basename "$f" .dtb).dts" "$f"; done
for f in "$RAW"/overlays/*.dtbo; do dtc -q -I dtb -O dts -o "$OUT/stock-overlay-$(basename "$f" .dtbo).dts" "$f"; done

# 4. ids actually used for DTB/DTBO selection
: > "$OUT/ids.txt"
for f in "$OUT"/stock-*.dts; do
  ids=$(grep -hoE 'qcom,(msm|board|pmic)-id = <[^>]*>' "$f" | tr '\n' ' ' || true)
  [ -n "$ids" ] && echo "$(basename "$f"): $ids" >> "$OUT/ids.txt"
done
cat "$OUT/ids.txt"
```

- [ ] **Step 2: Run it**

Run: `chmod +x tools/extract-reference.sh && tools/extract-reference.sh`
Expected: `stock-boot-header.txt` contains `--header_version 2`, `--os_version`, `--os_patch_level`, `--board`, `--base`/offset flags; `ids.txt` has at least one base line with `qcom,msm-id` and several overlay lines with `qcom,board-id = <0x08 0x0N>` for N in 0..6.
If the stock boot.img has no `dtb` section (header v2 should have one) or `dtbo.img.lz4` is not in the AP tar: stop and report — do not guess values.

- [ ] **Step 3: Record findings in NOTES.md**

Append a "Reference (stock T976BXXS7DXH1)" section with: header fields line, the msm-id(s), the board-id list, and the `reserved-memory` node names of `stock-base-*.dts` (`grep -A1 -E '^\s+[a-z_]+@[0-9a-f]+ \{' stock-base-00.dts | sed -n '/reserved-memory/,/^\t};/p'` style — list them, do not interpret yet).

- [ ] **Step 4: Commit**

```bash
git add tools/extract-reference.sh reference/*.txt reference/*.dts NOTES.md
git commit -m "Extract stock T976B boot header, DTB and DTBO references"
```

---

### Task 4: ABL boot.img signer (`tools/sign_boot.py`)

**Files:**
- Create: `tools/sign_boot.py`, `tests/test_sign_boot.py`

**Interfaces:**
- Consumes: `reference/stock-boot-header.txt` format from Task 3 (only to locate the stock image; the tool reads the stock boot.img header directly), `tools/keys/testkey_rsa4096.pem`.
- Produces: CLI `python3 tools/sign_boot.py --stock STOCK_BOOT --cmdline "…" IN OUT`; function `copy_abl_fields(src: bytes, dst: bytearray) -> None`.

Header v2 offsets (little-endian): kernel_addr 12, ramdisk_addr 20, second_addr 28, tags_addr 32, page_size 36, header_version 40, os_version 44, name[16] 48, cmdline[512] 64. Copy from stock: ramdisk_addr, second_addr, tags_addr, os_version, name. Keep the input's kernel_addr/page_size. Partition size of `boot`: 71303168 (same partition table on both variants; verify against `heimdall print-pit` in phase 1 before first flash).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sign_boot.py
import struct, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import sign_boot

def mkimg(path, os_version, board, ramdisk_offset):
    k = path.parent / "k"; r = path.parent / "r"; d = path.parent / "d"
    k.write_bytes(b"K" * 4096); r.write_bytes(b"R" * 4096); d.write_bytes(b"D" * 64)
    subprocess.run(["mkbootimg", "--kernel", k, "--ramdisk", r, "--dtb", d, "--header_version", "2",
                    "--os_version", os_version[0], "--os_patch_level", os_version[1],
                    "--board", board, "--ramdisk_offset", ramdisk_offset, "--pagesize", "4096",
                    "-o", path], check=True)

def test_copy_fields(tmp_path):
    mkimg(tmp_path / "stock.img", ("13.0.0", "2024-08"), "STOCKBOARD", "0x02000000")
    mkimg(tmp_path / "pmos.img", ("16.0.0", "2026-11"), "PMOS", "0x01000000")
    src = (tmp_path / "stock.img").read_bytes(); dst = bytearray((tmp_path / "pmos.img").read_bytes())
    sign_boot.copy_abl_fields(src, dst)
    for off in (20, 28, 32, 44):
        assert dst[off:off + 4] == src[off:off + 4]
    assert dst[48:64] == src[48:64]

def test_cli_signs_and_sets_cmdline(tmp_path):
    mkimg(tmp_path / "stock.img", ("13.0.0", "2024-08"), "STOCKBOARD", "0x02000000")
    mkimg(tmp_path / "pmos.img", ("16.0.0", "2026-11"), "PMOS", "0x01000000")
    out = tmp_path / "boot-signed.img"
    subprocess.run([sys.executable, "tools/sign_boot.py", "--stock", tmp_path / "stock.img",
                    "--cmdline", "console=ttyMSM0 pmos_debug", tmp_path / "pmos.img", out], check=True)
    data = out.read_bytes()
    assert data[64:64 + 26] == b"console=ttyMSM0 pmos_debug"
    assert len(data) == 71303168
    info = subprocess.run(["avbtool", "info_image", "--image", out], capture_output=True, text=True, check=True).stdout
    assert "Partition Name:        boot" in info and "SHA256_RSA4096" in info

def test_rejects_non_bootimg(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        sign_boot.copy_abl_fields(b"\0" * 4096, bytearray(b"\0" * 4096))
```

- [ ] **Step 2: Run, expect failure**

Run: `uv run --with pytest pytest tests/test_sign_boot.py -q` → FAIL, `No module named 'sign_boot'`.

- [ ] **Step 3: Implement**

```python
#!/usr/bin/env python3
"""Make a pmOS boot.img acceptable to the Samsung ABL of the Tab S7+ 5G (gts7xl).

Copies the header fields the ABL checks from the stock T976B boot.img, sets the
kernel cmdline, then adds an AVB hash footer signed with the AOSP test key
(the vbmeta partition carries flags 0x02). Derived from the Droidian port's
build-bootimg.py, minus its Wi-Fi-specific constants.
"""
import argparse, shutil, subprocess, sys
from pathlib import Path

BOOT_PARTITION_SIZE = 71303168
ROLLBACK_INDEX = 1900000000          # >= fused minimum (Droidian finding)
COPIED = [(20, 4), (28, 4), (32, 4), (44, 4), (48, 16)]  # ramdisk, second, tags, os_version, name
KEY = Path(__file__).parent / "keys" / "testkey_rsa4096.pem"

def copy_abl_fields(src: bytes, dst: bytearray) -> None:
    for img in (src, dst):
        if img[:8] != b"ANDROID!":
            raise ValueError("not an Android boot image")
    for off, size in COPIED:
        dst[off:off + size] = src[off:off + size]

def set_cmdline(dst: bytearray, cmdline: str) -> None:
    raw = cmdline.encode()
    if len(raw) >= 512:
        raise ValueError("cmdline too long for header v2")
    dst[64:64 + 512] = raw.ljust(512, b"\0")

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", required=True); ap.add_argument("--cmdline", required=True)
    ap.add_argument("input"); ap.add_argument("output")
    a = ap.parse_args(argv)
    img = bytearray(Path(a.input).read_bytes())
    copy_abl_fields(Path(a.stock).read_bytes(), img)
    set_cmdline(img, a.cmdline)
    Path(a.output).write_bytes(img)
    subprocess.run(["avbtool", "erase_footer", "--image", a.output], stderr=subprocess.DEVNULL)
    subprocess.run(["avbtool", "add_hash_footer", "--image", a.output,
                    "--partition_size", str(BOOT_PARTITION_SIZE), "--partition_name", "boot",
                    "--algorithm", "SHA256_RSA4096", "--key", str(KEY),
                    "--rollback_index", str(ROLLBACK_INDEX)], check=True)
    print(f"OK {a.output}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run, expect pass**

Run: `uv run --with pytest pytest tests/test_sign_boot.py -q` → `3 passed`.
If `mkbootimg` refuses `Path` arguments, convert them with `str()` in `mkimg`.

- [ ] **Step 5: Commit**

```bash
git add tools/sign_boot.py tests/test_sign_boot.py
git commit -m "Add ABL boot.img signer using stock T976B header fields"
```

---

### Task 5: Flash wrapper (`tools/flash.sh`)

**Files:**
- Create: `tools/flash.sh`, `tests/test_flash.sh`

**Interfaces:**
- Produces: `tools/flash.sh [--dry-run] PART=IMAGE …`; always appends `--VBMETA tools/images/vbmeta-disabled.img` and `--no-reboot`; refuses any partition outside `BOOT DTBO VBMETA RECOVERY USERDATA`; logs sha256 of each image to `NOTES.md` when not in dry-run.

- [ ] **Step 1: Write the failing test**

```bash
#!/usr/bin/env bash
# tests/test_flash.sh — dry-run behaviour of tools/flash.sh
set -u; cd "$(dirname "$0")/.."; fail=0
t=$(mktemp -d); echo x > "$t/boot.img"; echo y > "$t/dtbo.img"
out=$(tools/flash.sh --dry-run BOOT="$t/boot.img" DTBO="$t/dtbo.img")
[[ $out == *"heimdall flash"* && $out == *"--BOOT $t/boot.img"* && $out == *"--DTBO $t/dtbo.img"* \
   && $out == *"--VBMETA tools/images/vbmeta-disabled.img"* && $out == *"--no-reboot"* ]] || { echo "FAIL compose: $out"; fail=1; }
tools/flash.sh --dry-run EFS="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: EFS accepted"; fail=1; }
tools/flash.sh --dry-run BOOT="$t/missing.img" >/dev/null 2>&1 && { echo "FAIL: missing file accepted"; fail=1; }
[ $fail = 0 ] && echo "test_flash: OK"; exit $fail
```

- [ ] **Step 2: Run, expect failure**

Run: `bash tests/test_flash.sh` → `FAIL compose` (script does not exist).

- [ ] **Step 3: Implement**

```bash
#!/usr/bin/env bash
# Flash images to the Tab S7+ 5G with one Heimdall command (Download Mode).
# vbmeta-disabled is always included: single-image commits are unreliable on SM8250.
set -euo pipefail
cd "$(dirname "$0")/.."
ALLOWED=" BOOT DTBO VBMETA RECOVERY USERDATA "
dry=0; args=(); imgs=()
[ "${1:-}" = "--dry-run" ] && { dry=1; shift; }
[ $# -gt 0 ] || { echo "usage: flash.sh [--dry-run] PART=IMAGE ..." >&2; exit 2; }
for kv in "$@"; do
  part=${kv%%=*}; img=${kv#*=}
  [[ $ALLOWED == *" $part "* ]] || { echo "refused partition: $part" >&2; exit 1; }
  [ "$part" = VBMETA ] && { echo "VBMETA is added automatically" >&2; exit 1; }
  [ -f "$img" ] || { echo "missing image: $img" >&2; exit 1; }
  args+=("--$part" "$img"); imgs+=("$part $img")
done
cmd=(heimdall flash "${args[@]}" --VBMETA tools/images/vbmeta-disabled.img --no-reboot)
if [ $dry = 1 ]; then echo "${cmd[*]}"; exit 0; fi
{ echo; echo "## $(date -Is) flash"; for i in "${imgs[@]}"; do set -- $i; echo "- $1: $(sha256sum "$2" | cut -c1-16) $2"; done; } >> NOTES.md
ssh -t localhost sudo bash -c "$(printf '%q ' cd "$PWD") && $(printf '%q ' "${cmd[@]}")"
```

Note: the real (non-dry) path is only used from phase 1 on, with the maintainer present.

- [ ] **Step 4: Run, expect pass**

Run: `chmod +x tools/flash.sh tests/test_flash.sh && bash tests/test_flash.sh` → `test_flash: OK`.

- [ ] **Step 5: Commit**

```bash
git add tools/flash.sh tests/test_flash.sh
git commit -m "Add Heimdall flash wrapper with partition allow-list and dry-run"
```

---

### Task 6: pmaports fork, device and kernel packages, pmbootstrap init

**Files:**
- Create (in `pmaports/`): `device/testing/device-samsung-gts7xl/APKBUILD`, `device/testing/device-samsung-gts7xl/deviceinfo`, `device/testing/linux-samsung-gts7xl/APKBUILD`, `device/testing/linux-samsung-gts7xl/config-samsung-gts7xl.aarch64`

**Interfaces:**
- Consumes: `reference/stock-boot-header.txt` (Task 3) for flash offsets and pagesize.
- Produces: pmbootstrap configured with `device=samsung-gts7xl`, `aports=pmaports`, `ui=console`; kernel package name `linux-samsung-gts7xl` (used by Task 7 with envkernel); dtb path `qcom/sm8250-samsung-gts7xl`.

- [ ] **Step 1: Clone pmaports**

```bash
cd gts7xl-mainline
git clone --depth 50 https://gitlab.postmarketos.org/postmarketOS/pmaports.git
cd pmaports && git switch -c gts7xl
```

- [ ] **Step 2: Kernel package**

Pick the newest stable 7.x tag: `git ls-remote --tags https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git 'refs/tags/v7.*' | grep -v '\^{}' | awk -F/ '{print $3}' | sort -V | tail -1` (if git.kernel.org times out, use the GitHub mirror `https://github.com/gregkh/linux.git`). Call it `$TAG` (e.g. `v7.2.15`) and `$PKGVER` without the `v`.

`device/testing/linux-samsung-gts7xl/APKBUILD`:

```sh
# Maintainer: tarpediem <tarpediem@gmail.com>
pkgname=linux-samsung-gts7xl
pkgver=$PKGVER
pkgrel=0
pkgdesc="Mainline kernel for Samsung Galaxy Tab S7+ 5G (gts7xl)"
arch="aarch64"
_carch="arm64"
_flavor="samsung-gts7xl"
url="https://kernel.org"
license="GPL-2.0-only"
options="!strip !check !tracedeps pmb:cross-native"
makedepends="bash bc bison devicepkg-dev findutils flex openssl-dev perl gmp-dev mpc1-dev mpfr-dev"
source="https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-$pkgver.tar.xz
	config-$_flavor.$arch"
builddir="$srcdir/linux-$pkgver"

prepare() {
	default_prepare
	cp "$srcdir/config-$_flavor.$arch" .config
}

build() {
	unset LDFLAGS
	make ARCH="$_carch" CC="${CC:-gcc}" KBUILD_BUILD_VERSION="$((pkgrel + 1 ))-postmarketOS"
}

package() {
	downstreamkernel_package "$builddir" "$pkgdir" "$_carch" "$_flavor" "$pkgver"
	make dtbs_install O="$builddir" INSTALL_DTBS_PATH="$pkgdir/boot/dtbs"
}
sha512sums="SKIP
SKIP"
```

(Replace `$PKGVER` literally. `SKIP` checksums are acceptable only for this local-only package; envkernel builds from the local tree anyway.)

Config: start from the pmOS SM8250 kernel config if present, otherwise upstream `defconfig`:

```bash
f=$(find device -path '*linux-postmarketos-qcom-sm8250*' -name 'config-*aarch64' | head -1)
echo "pmOS sm8250 config: ${f:-none}"
```
If found, `cp "$f" device/testing/linux-samsung-gts7xl/config-samsung-gts7xl.aarch64`; otherwise generate it in Task 7 Step 2 from `make defconfig` and copy it here then. Either way `pmbootstrap kconfig check linux-samsung-gts7xl` must pass in Task 7.

- [ ] **Step 3: Device package**

Take `--pagesize`, `--base`, `--kernel_offset`, `--ramdisk_offset`, `--second_offset`, `--tags_offset` from `reference/stock-boot-header.txt` and write them below (values are hex strings exactly as printed there).

`device/testing/device-samsung-gts7xl/deviceinfo`:

```sh
deviceinfo_format_version="0"
deviceinfo_name="Samsung Galaxy Tab S7+ 5G"
deviceinfo_manufacturer="Samsung"
deviceinfo_codename="samsung-gts7xl"
deviceinfo_year="2020"
deviceinfo_dtb="qcom/sm8250-samsung-gts7xl"
deviceinfo_arch="aarch64"
deviceinfo_chassis="tablet"
deviceinfo_keyboard="false"
deviceinfo_external_storage="true"
deviceinfo_screen_width="1752"
deviceinfo_screen_height="2800"
deviceinfo_getty="ttyMSM0;115200"
deviceinfo_kernel_cmdline="console=ttyMSM0,115200 console=tty0 PMOS_NO_OUTPUT_REDIRECT"
deviceinfo_generate_bootimg="true"
deviceinfo_header_version="2"
deviceinfo_bootimg_qcdt="false"
deviceinfo_flash_method="heimdall-bootimg"
deviceinfo_flash_heimdall_partition_kernel="BOOT"
deviceinfo_flash_heimdall_partition_rootfs="USERDATA"
deviceinfo_flash_pagesize="<--pagesize>"
deviceinfo_flash_offset_base="<--base>"
deviceinfo_flash_offset_kernel="<--kernel_offset>"
deviceinfo_flash_offset_ramdisk="<--ramdisk_offset>"
deviceinfo_flash_offset_second="<--second_offset>"
deviceinfo_flash_offset_tags="<--tags_offset>"
```

The `<--flag>` markers are filled from the reference file in this step; the committed file must contain only hex values (`grep -c '<--' deviceinfo` = 0).

`device/testing/device-samsung-gts7xl/APKBUILD`:

```sh
# Reference: <https://postmarketos.org/devicepkg>
pkgname=device-samsung-gts7xl
pkgdesc="Samsung Galaxy Tab S7+ 5G"
pkgver=1
pkgrel=0
url="https://postmarketos.org"
license="MIT"
arch="aarch64"
options="!check !archcheck"
depends="postmarketos-base linux-samsung-gts7xl mkbootimg"
makedepends="devicepkg-dev"
source="deviceinfo"

build() { devicepkg_build $startdir $pkgname; }
package() { devicepkg_package $startdir $pkgname; }
sha512sums="SKIP"
```

Then `pmbootstrap checksum device-samsung-gts7xl` (fills the real sha512 of deviceinfo).

- [ ] **Step 4: pmbootstrap init**

Run in a terminal (interactive):
`pmbootstrap --aports pmaports init`
Answers: work path default; channel `edge`; vendor `samsung`; device `gts7xl`; kernel (only choice); user `user`; UI `console`; extra packages `none`; locale `fr_FR.UTF-8`; hostname `gts7xl`; build options default.
Verify: `pmbootstrap config device` → `samsung-gts7xl`; `pmbootstrap config aports` → the fork path.

- [ ] **Step 5: Commit in the fork**

```bash
cd pmaports
git add device/testing/device-samsung-gts7xl device/testing/linux-samsung-gts7xl
git commit -m "samsung-gts7xl: new device (Galaxy Tab S7+ 5G)"
```

---

### Task 7: Kernel tree with skeleton DTS, full image build, signed boot.img

**Files:**
- Create (in `linux/`): `arch/arm64/boot/dts/qcom/sm8250-samsung-gts7xl.dts`
- Modify (in `linux/`): `arch/arm64/boot/dts/qcom/Makefile`, `Documentation/devicetree/bindings/arm/qcom.yaml`
- Create (this repo): `build/` artifacts (ignored), `NOTES.md` entry

**Interfaces:**
- Consumes: `reference/ids.txt` (Task 3), kernel package name and dtb path (Task 6), `tools/sign_boot.py` (Task 4), `tools/dtbo.py empty` (Task 2), `tools/flash.sh --dry-run` (Task 5).
- Produces: `build/boot-signed.img`, `build/dtbo-empty.img`, `build/samsung-gts7xl.img` (rootfs) — the phase-1 flash candidates.

- [ ] **Step 1: Clone the stable kernel at `$TAG` (from Task 6)**

```bash
cd gts7xl-mainline
git clone --depth 1 --branch $TAG https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git linux
cd linux && git switch -c gts7xl
```

- [ ] **Step 2: Skeleton DTS**

Use the msm-id from the `stock-base` line and the full 5G board-id list from `reference/ids.txt`. `arch/arm64/boot/dts/qcom/sm8250-samsung-gts7xl.dts`:

```dts
// SPDX-License-Identifier: GPL-2.0-only
/*
 * Samsung Galaxy Tab S7+ 5G (SM-T976B, gts7xl) — phase 0 skeleton.
 * Phase 1 adds reserved-memory, regulators, UFS, USB, simple-framebuffer, keys, ramoops.
 */
/dts-v1/;

#include "sm8250.dtsi"
#include "pm8150.dtsi"
#include "pm8150b.dtsi"
#include "pm8150l.dtsi"

/ {
	model = "Samsung Galaxy Tab S7+ 5G";
	compatible = "samsung,gts7xl", "qcom,sm8250";
	chassis-type = "tablet";

	/* Values copied from reference/ids.txt (stock T976BXXS7DXH1). */
	qcom,msm-id = <MSM_ID_FROM_REFERENCE>;
	qcom,board-id = <8 0>, <8 1>, <8 2>, <8 3>, <8 4>, <8 5>, <8 6>;

	chosen {
		#address-cells = <2>;
		#size-cells = <2>;
		ranges;
	};
};
```

Replace `MSM_ID_FROM_REFERENCE` with the exact cells from `ids.txt` (e.g. `<0x164 0x20001>` — copy, do not use this example). If the board-id cells in `ids.txt` are not `8 0..6`, use the reference values instead and note the difference in `NOTES.md`.

Makefile: add next to the other sm8250 entries, keeping alphabetical order:
`dtb-$(CONFIG_ARCH_QCOM)	+= sm8250-samsung-gts7xl.dtb`

`Documentation/devicetree/bindings/arm/qcom.yaml`: in the `qcom,sm8250` enum list, add `- samsung,gts7xl` in alphabetical position.

- [ ] **Step 3: Build and check the DTB through envkernel**

```bash
cd linux
source "$(pmbootstrap config work)/../pmbootstrap/helpers/envkernel.sh" 2>/dev/null \
  || source /usr/share/pmbootstrap/helpers/envkernel.sh
cp ../pmaports/device/testing/linux-samsung-gts7xl/config-samsung-gts7xl.aarch64 .config 2>/dev/null || make defconfig
make olddefconfig
make qcom/sm8250-samsung-gts7xl.dtb
fdtget arch/arm64/boot/dts/qcom/sm8250-samsung-gts7xl.dtb / qcom,board-id
```
Expected: the dtb builds; `fdtget` prints the 14 board-id cells. If `.config` came from `defconfig`, copy it to `../pmaports/device/testing/linux-samsung-gts7xl/config-samsung-gts7xl.aarch64` and amend the pmaports commit.
Schema check (`make CHECK_DTBS=y …` needs `dtschema`): `uv tool run --from dtschema make CHECK_DTBS=y qcom/sm8250-samsung-gts7xl.dtb` — warnings about nodes not yet described are acceptable; errors on our new nodes are not.

- [ ] **Step 4: Kernel config check, build, package**

```bash
pmbootstrap kconfig check linux-samsung-gts7xl   # fix reported options with `make menuconfig`, copy .config back, re-run until clean
make -j$(nproc)
pmbootstrap build --envkernel linux-samsung-gts7xl
```
Expected: `kconfig check` reports no errors; the package builds.

- [ ] **Step 5: Install and export**

```bash
pmbootstrap -y zap
pmbootstrap install --no-image-only --password changeme-not-flashed
pmbootstrap export build
```
(Password is a throwaway placeholder for an image that is not flashed in phase 0; phase 1 rebuilds with the real one.) Expected: `build/boot.img` and `build/samsung-gts7xl.img`.

- [ ] **Step 6: Post-process and verify the candidates**

```bash
cd gts7xl-mainline
python3 tools/sign_boot.py --stock <stock-firmware>/fw/boot.img \
  --cmdline "$(grep -oP 'deviceinfo_kernel_cmdline="\K[^"]+' pmaports/device/testing/device-samsung-gts7xl/deviceinfo)" \
  build/boot.img build/boot-signed.img
python3 tools/dtbo.py empty build/dtbo-empty.img
avbtool info_image --image build/boot-signed.img | grep -E 'Partition Name|Algorithm'
unpack_bootimg --boot_img build/boot-signed.img --out /tmp/claude-1000/bootcheck >/dev/null
fdtget /tmp/claude-1000/bootcheck/dtb / compatible
tools/flash.sh --dry-run BOOT=build/boot-signed.img DTBO=build/dtbo-empty.img
```
Expected: `Partition Name: boot`, `Algorithm: SHA256_RSA4096`; compatible `samsung,gts7xl qcom,sm8250`; a heimdall command printed, nothing executed.
If `unpack_bootimg` shows no `dtb` in the image, set `deviceinfo_append_dtb="false"` / check pmOS header-v2 dtb handling, rebuild, and record the fix in `NOTES.md`.

- [ ] **Step 7: Log and commit**

Append to `NOTES.md`: date, `$TAG`, sha256 (first 16) of `boot-signed.img`, `dtbo-empty.img`, `samsung-gts7xl.img`, "phase 0 done — not flashed".

```bash
cd linux && git add -A arch/arm64/boot/dts/qcom Documentation/devicetree/bindings/arm/qcom.yaml \
  && git commit -m "arm64: dts: qcom: sm8250: add Samsung Galaxy Tab S7+ 5G skeleton"
cd .. && git add NOTES.md && git commit -m "Phase 0 complete: signed boot.img and rootfs candidates built"
```

---

## Phase 0 done when

- `uv run --with pytest pytest tests -q` and `bash tests/test_flash.sh` pass.
- `build/boot-signed.img` carries the AVB footer and the gts7xl DTB with the stock 5G board-ids.
- `build/samsung-gts7xl.img` exists; nothing has been flashed.
