# gts7xl mainline — build and flash log

One entry per build or flash: date, what was built/flashed (sha256 of each image),
what was observed. Newest at the top.

## Kernel base

- `TAG=v7.3.4`, `PKGVER=7.3.4` (newest stable 7.x tag on 2026-11-17, from the
  GitHub mirror gregkh/linux; git.kernel.org returned HTTP 502). Used as
  `pkgver` of `linux-samsung-gts7xl` in the pmaports fork (branch `gts7xl`).
- Starting kernel config: copied from pmaports
  `device/testing/linux-postmarketos-qcom-sm8250/config-postmarketos-qcom-sm8250.aarch64`
  (generated for Linux 7.2.0) into `config-samsung-gts7xl.aarch64`; to be refreshed
  against v7.3.4 (`olddefconfig`) in Task 7.

## Reference (stock T976BXXS7DXH1)

Extracted by `tools/extract-reference.sh` (outputs in `reference/`).

Boot header (`reference/stock-boot-header.txt`, mkbootimg format; file paths omitted here):

    --header_version 2 --os_version 11.0.0 --os_patch_level 2024-08 --pagesize 0x00001000 --base 0x00000000 --kernel_offset 0x00008000 --ramdisk_offset 0x02000000 --second_offset 0x00000000 --tags_offset 0x01e00000 --dtb_offset 0x0000000001f00000 --board SRPTC16A007

Stock cmdline: `console=null androidboot.hardware=qcom androidboot.memcg=1 lpm_levels.sleep_disabled=1 video=vfb:640x400,bpp=32,memsize=3072000 msm_rtb.filter=0x237 service_locator.enable=1 androidboot.usbcontroller=a600000.dwc3 swiotlb=2048 printk.devkmsg=on firmware_class.path=/vendor/firmware_mnt/image loop.max_part=7`

Boot dtb section: 4 concatenated FDTs.
- base-00: kona v2.1, `qcom,msm-id = <0x164 0x20001>`, `qcom,board-id = <0x00 0x00>`
- base-01: kona v2, `qcom,msm-id = <0x164 0x20000>`, `qcom,board-id = <0x00 0x00>`
- base-02: kona v1, `qcom,msm-id = <0x164 0x10000>`, `qcom,board-id = <0x00 0x00>`
- base-03: not a SoC DT (only `qcom,rtic-id` and `MP_DATA`), no ids.

Stock dtbo.img (from AP tar `dtbo.img.lz4`): DT-table magic 0xd7b7ab1e, header
`page_size` = 4096 (0x1000), `version` = 0. 8 entries; every entry id/rev/custom is 0,
so the board id is only inside each overlay:
- overlay-00: `qcom,board-id = <0x08 0x01>`
- overlay-01: `<0x08 0x05>`
- overlay-02: `<0x08 0x00>`
- overlay-03: `<0x08 0x04>`
- overlay-04: `<0x08 0x06>`
- overlay-05: `<0x08 0x03>`
- overlay-06: `<0x08 0x02>`
- overlay-07: no board-id (only `dtbo-version = <0x01>`).

Overlays carry no `qcom,msm-id`.

`reserved-memory` children (identical in base-00, -01 and -02; not interpreted yet):
- hyp_mem: hyp_region@80000000
- xbl_aop_mem: xbl_aop_region@80700000
- cmd_db: reserved-memory@80860000
- smem_mem: smem_region@80900000
- removed_mem: removed_region@80b00000
- pil_camera_mem: pil_camera_region@86200000
- pil_wlan_fw_mem: pil_wlan_fw_region@86700000
- pil_ipa_fw_mem: pil_ipa_fw_region@86800000
- pil_ipa_gsi_mem: pil_ipa_gsi_region@86810000
- pil_gpu_mem: pil_gpu_region@8681a000
- pil_npu_mem: pil_npu_region@86900000
- pil_video_mem: pil_video_region@86e00000
- pil_cvp_mem: pil_cvp_region@87300000
- pil_cdsp_mem: pil_cdsp_region@87800000
- pil_slpi_mem: pil_slpi_region@88c00000
- pil_adsp_mem: pil_adsp_region@8a100000
- pil_spss_mem: pil_spss_region@8be00000
- cdsp_secure_heap: cdsp_secure_heap@8bf00000
- adsp_mem: adsp_region
- sdsp_mem: sdsp_region
- cdsp_mem: cdsp_region
- cont_splash_memory: cont_splash_region@9c000000
- disp_rdump_memory: disp_rdump_region@9c000000
- dfps_data_memory: dfps_data_region@9e300000
- dump_mem: mem_dump_region
- sp_mem: sp_region
- user_contig_mem: user_contig_region
- qseecom_mem: qseecom_region
- qseecom_ta_mem: qseecom_ta_region
- secure_display_memory: secure_display_region
- cnss_wlan_mem: cnss_wlan_region
- linux,cma
- mailbox_mem: mailbox_region

## 2026-11-17 — pre-flash review fixes (I1 I2 I3, M1 M4 M6 M7) — not flashed

Supersedes the candidates of the entry below (same day; those must not be flashed).
Review: `.superpowers/sdd/2026-11-17-phase0-preparation/shim-review.md`; details of the fixes in
`shim-fixes-report.md` next to it.

What changed:
- **I1, a hang should leave a log.** cmdline + `oops=panic softlockup_panic=1 nmi_watchdog=panic reboot=warm`;
  kernel config + `SOFTLOCKUP_DETECTOR`, `HARDLOCKUP_DETECTOR` (buddy), `DETECT_HUNG_TASK` (report only),
  `WQ_WATCHDOG` (report only); kernel patch 0003 (linux a67de047d): with `reboot=warm` the power-key driver
  writes the warm PS_HOLD reset type at probe, because a panic restarts without the reboot notifiers that
  normally write it. Hardware watchdog: not armed (what the firmware does on a bite is not sourced).
  Runbook step 1b: pstore survival test from One UI.
- **I2, USB.** The hook polls up to 30 s for i2c@980000 and for the UDC, then creates/binds the gadget and
  starts DHCP if the initramfs could not. I2C writes unchanged (0x25 only).
- **I3, image shape.** `recovery-shim.img` now ends like the Magisk BOOT: `SEANDROIDENFORCE` after the last
  section (offset 69984256), footer original_image_size 69984272; vbmeta blob and the rest of the footer
  are the stock recovery's. `mkrecovery.py` refuses an image longer than the stock hashed size (72143376).

Sources: linux `gts7xl` **a67de047d**; pmaports `gts7xl`: `linux-samsung-gts7xl-7.3.4-r3`
(tarball + 3 patches, `pmbootstrap kconfig check` OK), `device-samsung-gts7xl-1-r5`.

Candidates in `build/` (sha256, first 16):

| File | sha256 | Use |
|---|---|---|
| `recovery-shim.img` | `76c90d3fd1b6f5f7` | RECOVERY, attempt A (stock vbmeta kept, Samsung trailer) |
| `recovery-shim-signed.img` | `58593f15ebba2071` | RECOVERY, attempt B (test-key footer + vbmeta disabled) |
| `shim-Image` | `d7f98cee2cfa273b` | kernel slot of both (two builds give the same bytes) |
| `dtbs/sm8250-samsung-gts7xl.dtb` | `5b434caa6797d318` | mainline DTB inside the shim (unchanged) |
| `vmlinuz` | `b840ac6ff8863e4b` | Image.gz of the package; its Image is `68855f7b826ca1ec` |
| `initramfs` | `acf7ffe52f343e0f` | ramdisk of both (hook identical to the pmaports source) |
| `boot-signed.img` | `271af153a011a2ff` | intermediate only |
| `samsung-gts7xl.img` | `9344a705f7fc7452` | rootfs of the same install (not flashed in the first attempt) |

Cmdline of both recovery images:

    console=tty0 clk_ignore_unused pd_ignore_unused cpuidle.off=1 panic=5 oops=panic softlockup_panic=1 nmi_watchdog=panic reboot=warm pmos.debug-shell  pmos_boot_uuid=4f70aecd-ab64-4a8e-93a2-c3f137f5c944 pmos_root_uuid=cc8e08a2-3ebd-426d-b464-33dd6bb6957e pmos_rootfsopts=defaults

Checked on `recovery-shim.img`: kernel = `shim-Image`; `dtb` and `recovery_dtbo` `cmp`-equal to the stock
recovery's; footer differs from stock only in original_image_size; everything from the vbmeta offset
(72146944) to the footer equal to stock; one `SEANDROIDENFORCE`. The Image contains the strings of patch 0003
and of both lockup detectors.

Build commands: as in the entry below (kernel `--force`, device package, zap + install with udiskie
paused, export, `tools/build-recovery-shim.sh`); logs in `build/logs/`.

Tests: `uv run --with pytest pytest tests -q` → 62 passed, 8 skipped (unicorn absent: skipped, no failure);
with `--no-project --with unicorn` → 70 passed; `bash tests/test_flash.sh` → OK;
`tools/flash.sh --dry-run --keep-vbmeta RECOVERY=build/recovery-shim.img` → `heimdall flash --RECOVERY … --no-reboot`.

Not verified on hardware: that a warm reset keeps ramoops (runbook 1b measures it), that PSCI SYSTEM_RESET2
plus the warm PS_HOLD type is honoured by this firmware, and that the ABL looks at the trailer at all.

## 2026-11-17 — boot shim + observable DTS — not flashed (superseded)

Superseded by the entry above. Supersedes every earlier candidate (moved to `build/superseded/`; `boot-signed.img` is now only
an intermediate and must not be flashed).

Why: on the Tab S7 11" the ABL refused every image with a mainline DTB and booted anything
behind the vendor DTB. The RECOVERY image now carries the **stock DTB + stock recovery_dtbo**
for the ABL and a **boot shim** in the kernel slot, which starts our Image with our DTB.

Sources:
- linux `gts7xl`: 78dfd9767 (skeleton) + **faf7bc8d3** (memory map, ramoops, simple-framebuffer,
  USB peripheral, UFS, keys, i2c0, GPIO 20-23 reserved, PM8150B dropped). Both are patches of
  the aport; the package DTB is byte-identical to the host-built one.
- pmaports `gts7xl`: **292cee6**. `linux-samsung-gts7xl-7.3.4-r2` (tarball + 2 patches,
  USB gadget/configfs/NCM/RNDIS/ACM built in, `pmbootstrap kconfig check` OK),
  `device-samsung-gts7xl-1-r4` (cmdline, 2800x1752, MUIC hook, i2c-tools).
- shim: `tools/shim/` (start.S, shim.c, string.c, shim.lds) + libfdt from
  `linux/scripts/dtc/libfdt` at v7.3.4 (fdt.c, fdt_ro.c, fdt_rw.c, fdt_wip.c).
  Design taken from github.com/Iamtianyuyang/steamos-tabs7 at 306c52476ab5 (`boot/shim`, GPL-2.0-only).
  Built with host clang 23.1.3 and LLD 22.1.8 from the pinned wheel `ziglang==0.17.1`
  (`uv run --with ziglang==0.17.1 python -m ziglang ld.lld`; no lld package on the host).
  Two builds of the same inputs give the same bytes.

Candidates in `build/` (sha256, first 16):

| File | sha256 | Use |
|---|---|---|
| `recovery-shim.img` | `d84512c91119610d` | RECOVERY, attempt A (stock AVB footer, vbmeta untouched) |
| `recovery-shim-signed.img` | `121c6efecd61450f` | RECOVERY, attempt B (test-key footer + vbmeta disabled) |
| `shim-Image` | `ea2fc21d8b93533b` | kernel slot of both (shim + DTB + Image) |
| `dtbs/sm8250-samsung-gts7xl.dtb` | `5b434caa6797d318` | mainline DTB inside the shim |
| `vmlinuz` | `14c7d5155ed04382` | Image.gz of the package; its Image (sha256 `4f67df359c621a0b`) is inside the shim |
| `initramfs` | `b65d471892581725` | ramdisk of both |
| `boot-signed.img` | `32b78e76bc97100c` | intermediate only |
| `samsung-gts7xl.img` | `04102eb14c80f4da` | rootfs of the same install (not flashed in the first attempt) |

Cmdline of both recovery images:

    console=tty0 clk_ignore_unused pd_ignore_unused cpuidle.off=1 panic=5 pmos.debug-shell  pmos_boot_uuid=81209c16-1709-4aeb-87af-cbdd57248bae pmos_root_uuid=6a6fad83-f326-47a1-a7f8-fa96c6e7a0f6 pmos_rootfsopts=defaults

What the ABL sees in `recovery-shim.img` (checked with unpack_bootimg / cmp / avbtool):
- header v2, os 11.0.0, board `SRPTC16A007`, load offsets of the stock boot image;
- `dtb` (1580275 bytes) and `recovery_dtbo` (2788831 bytes) byte-identical to the stock recovery's;
- kernel slot: arm64 Image header with `text_offset 0x80000`, `image_size 0x3600000`, flags `0xa`
  (stock: 0x80000, 0x461c000, 0xa);
- last 64 bytes and vbmeta blob = the stock recovery's (A); `Partition Name: recovery`,
  SHA256_RSA4096, rollback index 0 (B).

Shim checked in an emulator (unicorn) with the real `shim-Image` and the device tree captured
from the running stock kernel as "bootloader DTB", loaded at 0xa0080000: enters the Image at
0xa0200000 with x0 = 0xa3190000; the DTB there is our tree with `/memory` reg, `bootargs`,
`linux,initrd-start/end` equal to the captured ones; ~19.5 M instructions; green bar painted.

Build commands (each pmbootstrap call through `ssh localhost`, udiskie paused during install):

    git -C linux format-patch -1 <commit> --start-number N -o ../pmaports/device/testing/linux-samsung-gts7xl/
    pmbootstrap checksum linux-samsung-gts7xl && pmbootstrap kconfig check linux-samsung-gts7xl
    pmbootstrap build --force linux-samsung-gts7xl
    pmbootstrap checksum device-samsung-gts7xl && pmbootstrap build -i -n device-samsung-gts7xl
    pmbootstrap -y zap && pmbootstrap install --password changeme-not-flashed
    pmbootstrap export build/
    tools/build-recovery-shim.sh

Tests: `uv run --no-project --with pytest --with unicorn pytest tests -q` (60 passed),
`bash tests/test_flash.sh` (OK). DTB: `make CHECK_DTBS=y qcom/sm8250-samsung-gts7xl.dtb` clean
(`build/dtbs-check.log`).

Notes:
- The ABL's command line is about 2900 bytes with ours near the start; mainline keeps the first
  2047 bytes (COMMAND_LINE_SIZE 2048), so only `androidboot.*` arguments at the end are cut.
- The image still has the placeholder password; rebuild with the real one before flashing USERDATA.
- `reference/live/stock-config.txt` (gitignored): `/proc/config.gz` of the stock kernel, read over adb.

## 2026-11-17 — phase 0 review fixes (cmdline, 4K sectors, reproducible kernel) — not flashed (superseded)

Superseded by the entry above. Supersedes the candidates of the entry below (those must not be flashed).

Why:
- `sign_boot.py --cmdline` replaced the cmdline and dropped `pmos_boot_uuid` / `pmos_root_uuid` /
  `pmos_rootfsopts`. The initramfs (`find_partition`) looks up UUID, then path, then label; without the uuids it
  fell back to the labels `pmOS_boot` / `pmOS_root`. `sign_boot.py` now keeps the input cmdline
  (`--append-cmdline` adds args, `--replace-cmdline` discards it, more than 511 + 1023 bytes is an error).
  Board args are in `deviceinfo_kernel_cmdline`, with `clk_ignore_unused pd_ignore_unused panic=5` added for first boot.
- The rootfs image had a 512-byte-sector GPT; the tablet's UFS has 4096-byte logical blocks (read on the tablet:
  `/sys/block/sd[a-d]/queue/logical_block_size` = 4096, userdata = sda37) → `deviceinfo_rootfs_image_sector_size="4096"`.
- The kernel aport now carries the DTS commit (linux 78dfd9767) as a patch, so `pmbootstrap build linux-samsung-gts7xl`
  from the kernel.org tarball gives the same DTB (byte-identical to the `--src` build, sha256 `04dfe60815e17a85`).
- `deviceinfo_flash_method="none"`: `pmbootstrap flasher` refuses ("Flash method none is not supported", checked in
  pmbootstrap 3.12.1 `flasher/init.py`, not run). Never use `pmbootstrap flasher` (nor `--method heimdall-bootimg`):
  the only flash path is `tools/flash.sh`.

Kernel: v7.3.4 + linux 78dfd9767 as patch, package `linux-samsung-gts7xl-7.3.4-r1` built from the tarball (no `--src`).
The earlier `--src` binary `7.3.4_p20261117075704-r0` was moved to `~/.local/var/pmbootstrap/packages-aside/`
(it has a higher version and would be installed instead). `device-samsung-gts7xl-1-r2`. pmaports fork (branch `gts7xl`) at 086541b.

Candidates in `build/` (sha256, first 16):

| File | sha256 |
|---|---|
| `boot-signed.img` | `c2e3d1255a8305e0` |
| `dtbo-empty.img` | `51c15f49bc27af8c` |
| `samsung-gts7xl.img` | `5df010b498339f3d` |

`boot-signed.img` and `samsung-gts7xl.img` are a pair: the cmdline carries the filesystem UUIDs of that image.
After every `pmbootstrap install`, export and sign again, and flash both.

Cmdline of `boot-signed.img`:

    console=ttyMSM0,115200 console=tty0 clk_ignore_unused pd_ignore_unused panic=5 PMOS_NO_OUTPUT_REDIRECT  pmos_boot_uuid=9eb3dd8d-5b79-4116-9904-911d3c5d7e46 pmos_root_uuid=811a783b-092c-4ba7-850f-1ea8760a697c pmos_rootfsopts=defaults

Checks:
- `samsung-gts7xl.img`: GPT header at byte 4096 (none at 512); p1 `pmOS_boot` ext2 UUID `9eb3dd8d-…`, p2 `pmOS_root`
  ext4 UUID `811a783b-…` (blkid), same as the cmdline.
- `boot-signed.img`: header v2, AVB `Partition Name: boot`, `SHA256_RSA4096`, rollback index 0, 71303168 bytes;
  DTB unchanged (113995 bytes at 0x01f00000, compatible `samsung,gts7xl qcom,sm8250`, msm-id `<0x164 0x20001>`,
  board-id `<0 0>, <8 0> … <8 6>`).
- `tools/flash.sh --dry-run BOOT=build/boot-signed.img DTBO=build/dtbo-empty.img`: prints the heimdall command, nothing executed.

Build commands (each pmbootstrap call through `ssh localhost`, udiskie paused during install):

    pmbootstrap build --force linux-samsung-gts7xl      # tarball + patch; use --src build/linux-src only to iterate
    pmbootstrap build -i -n device-samsung-gts7xl
    pmbootstrap -y zap && pmbootstrap install --password changeme-not-flashed
    pmbootstrap export build/
    python3 tools/sign_boot.py --stock <stock-firmware>/fw/boot.img build/boot.img build/boot-signed.img

Notes:
- `PMOS_NO_OUTPUT_REDIRECT` is no longer read by the current postmarketos-initramfs (harmless; `pmos.debug-shell` is the current debug key).
- A new linux commit must be added to the aport as a patch (`git -C linux format-patch`) and `pkgrel` bumped.
- Image built with the placeholder password; rebuild with the real one before flashing.

## 2026-11-17 — phase 0 done — not flashed (superseded)

Kernel tag: v7.3.4 (`linux/` branch `gts7xl` at 78dfd9767, pmaports fork branch `gts7xl` at bd4a415).
Package: `linux-samsung-gts7xl-7.3.4_p20261117075704-r0` (built with `pmbootstrap build --src build/linux-src`, LLVM=1).

Candidates in `build/` (sha256, first 16):

| File | sha256 |
|---|---|
| `boot-signed.img` | `53e559451fabb3f8` |
| `dtbo-empty.img` | `51c15f49bc27af8c` |
| `samsung-gts7xl.img` | `33cc031c5c79a656` |

Checks:
- `boot-signed.img`: header v2, AVB footer `Partition Name: boot`, `SHA256_RSA4096`, rollback index 0;
  DTB compatible `samsung,gts7xl qcom,sm8250`, msm-id `<0x164 0x20001>`,
  board-id `<0 0>, <8 0> … <8 6>` (8 pairs: stock list has `<0 0>` in front of the 5G ids).
- `samsung-gts7xl.img`: GPT with /boot and / ; `/sbin/init` → `../lib/systemd/systemd` present in the root partition.
- `tools/flash.sh --dry-run BOOT=… DTBO=…` prints the heimdall command (BOOT, DTBO, VBMETA, `--no-reboot`), nothing executed.

Notes for phase 1:
- The config in the fork is the one embedded in the built kernel (extract-ikconfig); `pmbootstrap kconfig check` passes.
- `pmbootstrap install` was run without `--no-image-only` (option absent in this pmbootstrap); sparse flag not needed.
- `sign_boot.py --cmdline` replaces the cmdline, so `pmos_boot_uuid` / `pmos_root_uuid` added by pmbootstrap are not in
  `boot-signed.img`; the initramfs must find the subpartitions by label. Decide in phase 1 whether to keep the uuids.
- `build/samsung-gts7xl.img` is a symlink into the pmbootstrap chroot: a `pmbootstrap zap` removes it. Rebuild with the real password before flashing.
