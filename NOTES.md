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

## 2026-11-17T09:50:08+07:00 flash
- RECOVERY: 76c90d3fd1b6f5f7e45628ae379fe20113f018676253e9a176de80f1c7d29687 build/recovery-shim.img
- Result: FIRST MAINLINE BOOT. Booted RECOVERY (Vol Up + Power) through the vendor-DTB shim: Linux 7.3.4 up,
  8 CPUs, 7.1 GiB RAM, UFS sda (37 partitions, 4096-byte blocks), MUIC switched over i2c0, USB gadget
  18d1:d001 -> RNDIS, the host got 172.16.42.2, `telnet 172.16.42.1` reaches the pmOS debug shell.
  Screen: plain white (simpledrm fb0 registered at 0x9c000000; console not visible yet).
  dmesg saved to build/firstboot/dmesg-raw.txt (gitignored: contains device serials).

## 2026-11-17 — panel white then black on the first boot: cause and fix (not flashed)

Measured on the running tablet (read-only), full report in
`.superpowers/sdd/2026-11-17-phase0-preparation/panel-report.md`:

- dispcc had no consumer: its sync_state powered the MDSS GDSC off 0.36 s after it was registered
  (`pd_ignore_unused` does not cover genpd sync_state);
- rpmhpd sync_state lowered MMCX to low_svs (camcc vote) under a 300 MHz MDP clock;
- L9A (DSI 1.2 V) is shared with the UFS PHY, which released it on runtime suspend.

The panel module kept its power (GPIO 135), reset (GPIO 82) and TCON RDY (GPIO 26) all along: no panel rail was
cut out of order, repeating the boot is judged safe.

Fix: `linux` 5954f55b7 — the simple-framebuffer node holds MMCX (nominal), the MDSS GDSC, L5A and L9A.
`pmaports` aa928ac — kernel r4 (patch 0004), device r6 (`regulator_ignore_unused` on the cmdline).

| File | sha256 (first 16) |
|---|---|
| `build/recovery-shim.img` | `aedae4cd8b5b8a11` |
| `build/recovery-shim-signed.img` | `2f315345ffefdc96` |
| `build/shim-Image` | `674280aef1829b0d` |

Expected on screen next time: the bootloader's last picture, steady. The kernel console needs an MDSS/DSI and
panel driver (command-mode panel: nobody sends frames). Check after boot: `mdss_gdsc` on, `mmcx` at 256,
`vreg_l9a_1p2` enabled with a framebuffer consumer.

## 2026-11-17T10:13:24+07:00 flash
- RECOVERY: aedae4cd8b5b8a11813d1eaef3e0aa33fed85947ccfc45e6afb4af907a5c2e9c build/recovery-shim.img

## 2026-11-17 — phase 2: MDSS/DSI0 + S6TUUM3 panel driver (not flashed)

`linux` 9deabe798 (driver `panel-samsung-s6tuum3.c` + binding), 657f28493 (DTS: mdss, dsi0, phy, panel,
`octa-vdd` regulator on GPIO 135, pin states from the stock tree). `pmaports` 405666f: kernel r5
(patches 0005/0006, `CONFIG_DRM_PANEL_SAMSUNG_S6TUUM3=y`). Full report:
`.superpowers/sdd/2026-11-17-phase0-preparation/panel-driver-report.md`.

- Power sequence copied from the vendor kernel: vddlcd on + 10 ms → DSI LP-11 → reset 1 ms low / 1 ms high
  (skipped if TCON_RDY already high) → 200 ms + up to 300 ms for TCON_RDY → on list (HS) → brightness packet →
  display on + 17 ms → first time: F8/F9. Off: display off + 100 ms (no sleep-in), DSI off, reset low,
  10 ms, vddlcd off.
- DSC 1.1, 2 slices 1400x12, 8 bpc/8 bpp; PPS sent as the vendor's 88 bytes through register 9Eh.
- Tablet read before the build: GPIO 135 high, reset high, TCON_RDY low (it was high in the previous boot).

| File | sha256 (first 16) |
|---|---|
| `build/recovery-shim.img` | `ee6f68598f5296c8` |
| `build/recovery-shim-signed.img` | `ccd2fc135db69ac8` |
| `build/shim-Image` | `4ad570ddb2b8c67f` |

Expected: kernel console (fbcon) on the panel after msm binds, brightness 128/255. If not: dmesg for
`TCON not ready`, DSI `write failed`, DPU pp/TE timeouts.

## 2026-11-17 — phase 2 safety fixes (kernel r6, not flashed)

From `panel-safety-review.md` (GO_WITH_FIXES). `linux` 6f967c479: the TCON_RDY-high shortcut (no reset) is only
taken after an enable() of our own that worked, so the first enable after boot always does reset + TCON wait
(the ABL panel's link dies when msm resets MDSS); enable() never returns an error (logs it, forces the reset path
next time) so disable() always sends display off before power is cut; `suppress_bind_attrs`. `linux` 93877676c:
`off-on-delay-us = <100000>` on `octa-vdd`. `pmaports` kernel r6.

| File | sha256 (first 16) |
|---|---|
| `build/recovery-shim.img` | `0f3d127a670c7f8b` |
| `build/recovery-shim-signed.img` | `0099abe1a3894a0a` |
| `build/shim-Image` | `577961ed99b437ca` |

Expected on the next boot: TCON_RDY probably high at hand-over; dmesg should show
`TCON ready but not initialised by us: reset`, then `TCON ready after N ms`, then the console.
Recovery from a bad picture: `echo 1 > /sys/class/graphics/fb0/blank; echo 0 > …` or reboot into One UI.

## 2026-11-17T10:56:26+07:00 flash
- RECOVERY: 0f3d127a670c7f8b169521b194f53a0787ca50cdfd3fead3cdd90c3078026911 build/recovery-shim.img

## 2026-11-17 panel driver boot (recovery-shim.img sha256 0f3d127a670c7f8b…)
- Result: DISPLAY WORKS. msm_dpu + DSI0 + DSC + panel-samsung-s6tuum3: "TCON ready but not initialised by us: reset",
  "TCON ready after 334 ms", fb0 = msmdrmfb. Kernel console and the pmOS buffyboard on-screen keyboard are shown
  at 2800x1752 (photo: docs/photos/2026-11-17-first-console.jpg). USB debug shell still works.
- To look at: "DSI PLL(0) lock failed" + WARN in dsi_phy_driver_probe at 0.38 s (harmless so far, display came up);
  UFS WriteBooster query attr idn 31 -22 (cosmetic); va_macro deferred (audio, phase 7).

## 2026-11-17 — phase 3: touchscreen (STM FTS1BA90A), kernel r7 (not flashed)

`linux` d49d342aa (binding `st,fts1ba90a`), b739d846f (new driver `stmfts1b.c`; mainline `stmfts.c` is another
generation with other opcodes), ef2cb3211 (DTS: i2c5 400 kHz, touch @0x49, IRQ GPIO 15 level-low, L13A 3.3 V avdd,
L14A 1.8 V vdd, gpi_dma0 okay). `pmaports` 32150ee: kernel r7 (patches 0009–0011, `CONFIG_TOUCHSCREEN_STMFTS1B=y`).
Full report: `.superpowers/sdd/2026-11-17-phase0-preparation/touch-report.md`.

- Sequence from the vendor driver: avdd, 1 ms, vdd, 5 ms; system reset (`FA 20 00 00 24 81`); wait ready event;
  ID/version/panel reads; touch functions `30 61 00`; scan on `A0 00 01` while the input is open, `A0 00 00` otherwise.
  No flash/config/calibration command (0x13 force calibration skipped). Rails never switched off (L14A is also the
  stock display node's vddio).
- Orientation: controller portrait 1752x2800 → `touchscreen-swapped-x-y` + `touchscreen-inverted-x`
  (= Droidian matrix `0 1 0 -1 0 1`). If touches come out mirrored on both axes, use inverted-y instead.

| File | sha256 (first 16) |
|---|---|
| `build/recovery-shim.img` | `2161d2e8fda699e0` |
| `build/recovery-shim-signed.img` | `4a20ccd2d92eb02e` |
| `build/shim-Image` | `3b5e2a3d48dbb8f8` |

Expected: dmesg `stmfts1b … fw 0x…`, `resolution 1752x2800`, input "STM FTS1BA90A Touchscreen"; finger works on
buffyboard.

## 2026-11-17T11:21:44+07:00 flash
- RECOVERY: 2161d2e8fda699e0ccedd5ddea175dd1394f82fcb288b3d89b4ab72b711ca039 build/recovery-shim.img

## 2026-11-17 — r7 did not boot; fallback r8 (not flashed)

r7 (recovery-shim `2161d2e8…`): no USB gadget, white panel → early hang/panic before USB and msm bind; r6 was fine.
Cause not known yet (pstore pending). Suspects in order: `gpi_dma0` enabled (new fw_devlink supplier of i2c0, GPI +
SMMU), the touch probe blocking boot, the new L13A/L14A votes.

r8: `linux` 6fa9d5cea (stmfts1b: `PROBE_PREFER_ASYNCHRONOUS`, ready poll ≤ ~1 s, echo poll ≤ ~0.5 s),
ca16d990d (gpi_dma0 stays disabled, `/delete-property/ dmas, dma-names` on i2c5 → FIFO/SE-DMA mode).
i2c0, gpi_dma0 and the QUP wrapper are identical to r6 in the compiled DTB. `pmaports`: kernel r8 (patches 0012/0013).

| File | sha256 (first 16) |
|---|---|
| `build/recovery-shim.img` | `926ea2e3d47f34e5` |
| `build/recovery-shim-signed.img` | `06a552934f95b5de` |
| `build/shim-Image` | `b8d0ad4756e3a714` |

If r8 still fails like r7: next bisect step is r8 without the L13A/L14A regulator nodes and touch node (i2c5 only).
If SE5 is in GSI-only mode, i2c5 now fails to probe (no touch) instead of needing GPI.

## 2026-11-17T11:32:18+07:00 flash
- RECOVERY: 780166d92efd1baa0ba20e23733d737656345764792966e2b985f9075ae7aa7a build/stock/recovery.img

## 2026-11-17 r7 (touch) boot loop — lesson
- r7 looped panic→reboot into RECOVERY. pstore (build/r7crash/, gitignored) shows
  `vreg_l13a_3p3: unsupported voltage constraints 3304000-3296000uV` → the whole PM8150 RPMh regulator
  device failed → no L5A/L9A → no DSI, no USB, UFS starved. Cause: stock value 3300000 µV is off the
  mainline pldo grid (1504000 + n×8000). Downstream rounds silently, mainline refuses.
- RULE: snap every downstream regulator voltage to the mainline grid before flashing (grid-check test in tests/).
- RULE: archive every flashed image in build/archive/ before rebuilding.
- Escape a RECOVERY boot loop: Vol Down + Power, at black screen switch at once to Vol Up + Vol Down → Download Mode,
  then reflash build/stock/recovery.img. Recovered with stock recovery (sha256 780166d9…), One UI boots.

## 2026-11-17 — r7 root cause, r9 (not flashed)

pstore of r7 (`build/r7crash/console-ramoops-0`): `vreg_l13a_3p3: unsupported voltage constraints 3304000-3296000uV`,
then `qcom-rpmh-regulator 18200000.rsc:regulators-0: ldo13 devm_regulator_register() failed, ret=-22`. 3300000 uV is not
on the PMIC5 PLDO grid (1504000 + n × 8000), so the whole PM8150 RPMh regulator device failed → no L5A/L9A (DSI, white
panel), no USB PHY supplies (no USB). r8 still had this value: **r8 would hang the same way, never flash it.**

r9 = r8 + `linux` 4cb39cb88: L13A min = max = 3296000 (nearest step below the stock 3.3 V). All other regulators checked
against `qcom-rpmh-regulator.c`: S4A 1.8–1.92 V (hfsmps510), L2A 3.072 V, L17A 2.496–3.008 V (pldo), L12A/L14A 1.8 V
(pldo_lv), L5A 0.88 V, L6A/L9A 1.2 V (nldo) — all on grid, unchanged. New host test `tests/test_dts_regulators.py` reads
the grids from the driver source and fails on any off-grid DTS value (it fails on the r7/r8 tree).
`pmaports`: kernel r9 (patch 0014).

| File | sha256 (first 16) |
|---|---|
| `build/recovery-shim.img` (copy: `build/archive/recovery-shim-r9-4bcdd974.img`) | `4bcdd97422c39465` |
| `build/recovery-shim-signed.img` | `445aa7abda44215f` |
| `build/shim-Image` | `769c2badbc62112c` |

## 2026-11-17T11:43:59+07:00 flash
- RECOVERY: 4bcdd97422c394651eb11b1b00aa36784fd19f507fa21dbc3cb35b8804977bd2 build/recovery-shim.img

## 2026-11-17 — r10: GPI DMA for the touch bus, kexec + modules over USB (not flashed)

r9 on hardware: boot, display, USB OK; touch dead: `geni_i2c 994000.i2c: … Failed to get tx DMA ch` → SE5 runs in
GSI mode (FIFO disabled by the firmware), i2c5 needs GPI. r7 had shown the GPI failing: `EV ALLOCATE completion timeout`,
`alloc_ev_chan:-5`.

GPI fix: the stock tree (live DT and the vendor kona.dtsi) gives the QUPv3_0 GPI `qcom,gpi-ee-offset = <0x1000>`
(0x6000 for the two other wrappers); mainline's sm8250 match data uses 0, so commands went to the wrong EE window and
never completed. Register macros, gpii mask 0x7ff, 15 gpii, ev-factor 2 and interrupts 244–256 already match.
`linux` e3daa7d7e (binding: `qcom,gpi-ee-offset`), dfa9325cc (gpi.c: the DT value overrides the match data),
56ca27880 (DTS: `&gpi_dma0` okay with 0x1000, i2c5 keeps its GPI `dmas`; i2c0 identical to r9 in the compiled DTB).
Guard: `tests/test_dts_gpi.py`.

USB iteration (runbook `docs/runbooks/iterate-over-usb.md`): KEXEC/KEXEC_FILE were already on (no KEXEC_SIG, lockdown
none); `kexec-tools` in the initramfs; `stmfts1b` is now a module in the initramfs, blacklisted for udev there and
loaded by the hook `50-gts7xl-modules.sh` in the background once telnetd runs (`gts7xl.nomodules` skips it).
geni-i2c and GPI stay built-in (i2c0 = MUIC/USB path, and GPI is a fw_devlink supplier of i2c0).
Tools: `tools/usbsh.py` (telnet run / base64 pull / HTTP+wget push), `tools/kexec_dtb.py` (copy /memory from
/sys/firmware/fdt into the new DTB), `tools/kexec-push.sh`, `tools/module-push.sh` (both with `--dry-run`).
`pmaports` 03b471e (kernel r10, patches 0015–0017), a731e32 (device r7).

| File | sha256 (first 16) |
|---|---|
| `build/recovery-shim.img` (copy: `build/archive/recovery-shim-r10-bda4530a.img`) | `bda4530a7464240c` |
| `build/recovery-shim-signed.img` | `4a6a77d85ed4b5ca` |
| `build/shim-Image` | `61a87d0bafd79148` |

Expected: `gpi 900000.dma-controller` without timeouts, i2c-N for 994000.i2c, `gts7xl-modules: loaded stmfts1b` in
dmesg after telnetd, `stmfts1b … fw 0x…`, touch on buffyboard. kexec/usbsh not yet tried on the tablet.

## 2026-11-17T12:07:49+07:00 flash
- RECOVERY: bda4530a7464240c535216812e91e0b52fd443ce10eee791ccd0bfcf3f246ddb build/recovery-shim.img

## 2026-11-17 r10 (recovery-shim.img sha256 bda4530a…) — TOUCH WORKS
- GPI DMA fixed with `qcom,gpi-ee-offset = <0x1000>` (stock firmware EE); i2c5 probes, stmfts1b module loads at 4.7 s:
  FTS1BA90A fw 0x0113, 1751x2799, 53x33 channels; buffyboard restarted; typing by finger on the on-screen
  keyboard works with the correct orientation. Display, USB, UFS unchanged. kexec + module push tooling in place
  (docs/runbooks/iterate-over-usb.md), not yet exercised on the device.

## 2026-11-17 — r11: power key and volume down, short press toggles the display (not flashed, not kexec'd)

r10 on hardware (read only over usbsh): input devices were gpio-keys (Vol Up), the touchscreen and buffyboard; no
pm8941_pwrkey / pm8941_resin. `c440000.spmi:pmic@0:pon@800` existed with no driver bound. Cause: the pwrkey and resin
nodes are children of `pon@800` (`qcom,pm8998-pon`), and only the qcom-pon driver creates their devices
(`devm_of_platform_populate`). `CONFIG_POWER_RESET_QCOM_PON` was `=m` and the module was not in the initramfs, so
pm8941-pwrkey (built in) never saw a device. The DT nodes were fine (`&pon_pwrkey` okay, `&pon_resin` okay with
`KEY_VOLUMEDOWN`). Patch 0003 (warm PS_HOLD at probe) did not break anything: it simply never ran until now.

Fix: `CONFIG_POWER_RESET_QCOM_PON=y` (no `mode-*` properties in pm8150.dtsi, so its reboot-mode registers no mode and
writes nothing). Guard: `tests/test_kconfig_pon.py`. No linux/ source change; the DTB is byte-identical to r10.

Power key in the debug shell: hook `60-gts7xl-powerkey.sh` (device package), forks and returns. It reads 24-byte
`input_event` records from the pm8941_pwrkey event node with `dd bs=24 count=1 | od -tu1` (fd kept open), measures the
press from the event timestamps; a press < 3 s toggles: off = `inhibited=1` on the touchscreen input device (input
core calls close(): stmfts1b stops scanning, masks its IRQ) then `fb0/blank=1` (DRM fbdev: CRTC disabled, panel
disable/unprepare); on = `fb0/blank=0` then `inhibited=0`. ≥ 3 s: logged, nothing else (PMIC long-press reset still
applies). State is kept in the hook, not read from fb0: the vt keyboard handler unblanks the console on any key press,
so a volume key can light the screen while touch stays inhibited (next short press restores both). Messages go to
/dev/kmsg as `gts7xl-powerkey: …`. `gts7xl.nopowerkey` on the command line disables it.
Test: `tests/test_powerkey_hook.py` runs the hook under the pmbootstrap native chroot's busybox (ash/dd/od) on a fake
/sys and an event file.

Next step: s2idle suspend on power key (needs wakeup sources, GDSC/regulator handling and the panel's suspend path).

Sources: pmaports `linux-samsung-gts7xl-7.3.4-r11` (config only), `device-samsung-gts7xl-1-r8`.
Tests: 111 passed (regulator grid and GPI included), `test_flash.sh` OK.

| File | sha256 (first 16) |
|---|---|
| `build/recovery-shim.img` (copy: `build/archive/recovery-shim-r11-7b0787e6.img`) | `7b0787e6858c02f4` |
| `build/recovery-shim-signed.img` | `2f890419ad7a28b9` |
| `build/shim-Image` | `353efe4baa9ff67f` |
| `build/vmlinuz` (kexec payload) | `67d643040729a791` |
| `build/initramfs` (kexec payload) | `9dc5888e72ed6406` |
| `build/dtbs/sm8250-samsung-gts7xl.dtb` (= r10) | `c7ce97975c4e3a48` |

kexec (owner present): `tools/kexec-push.sh` (dry run: pulls /sys/firmware/fdt, copies /memory into the DTB, pushes
Image/DTB/initramfs to /tmp/kx, `kexec -l … --reuse-cmdline`, `kexec -e`). Expected after the jump:
`/proc/bus/input/devices` lists pm8941_pwrkey and pm8941_resin, dmesg `PS_HOLD reset type set to warm (reboot=warm)`
and `gts7xl-powerkey: watching /dev/input/eventN`; then: short press → screen off, touches ignored;
short press → screen on, typing works. First real use of the panel's disable/unprepare → prepare/enable path.

## 2026-11-17 — r12: kexec -e oopsed under kCFI; machine_kexec() __nocfi (not flashed)

First real kexec (r10 running, `#11`): `kexec -l /tmp/kx/Image --dtb=… --initrd=… --reuse-cmdline` returned 0,
`kexec_loaded` = 1; `kexec -e` → oops in the old kernel: `Unable to handle kernel paging request at virtual address
00000001148d6ffc`, level 3 translation fault through TTBR0, `pc : machine_kexec+0x12c`, x8 = `00000001148d7000`,
then panic → reboot (pstore kept in `build/kexec1/`, not in git: serials).

Cause, read from the r10 Image (`machine_kexec` at `_text + 0x56ef0` from /proc/kallsyms, no KASLR): +0x128
`ldr x8, [x19, #0x310]` (= `kimage->arch.kern_reloc`, a physical address), +0x12c `ldur w16, [x8, #-4]`, `movk w17`…,
`cmp`, `brk #0x8228`, `blr x8`. That is the kCFI check of `kernel_reloc(kimage)` (`CONFIG_CFI=y`, clang): it loads
the type hash at target − 4, in the page before the relocation page, which the kexec idmap in TTBR0 does not map. The
copied relocation code (SYM_CODE) has no hash either, so it would `brk` even if mapped. Not a segment placement
problem (kexec-tools uses only "System RAM"; no-map holes are excluded); `kexec -s` ends in the same function.
Upstream master still has the plain `void machine_kexec(`.

Fix: `linux` 50fbe0d8a `arm64: kexec: no kCFI check on the jump to the relocation code` (`__nocfi`, like
`swsusp_arch_resume()`), pmaports 8fd0f31ce (patch 0018, kernel r12, `#13`). Checked in the r12 Image: `ldr x8, [x19, #0x310];
blr x8`, no check. Guard: `tests/test_kexec_cfi.py`.

The running kernel does the jump: **r10/r11 can never kexec**. One RECOVERY flash of r12 is needed first.

Tools: `kexec_dtb.py` tolerates `fdtget -l` exiting 1 on the ABL-built tree (partial listing) and probes
`/memory@80000000` directly; `kexec-push.sh` refuses a running kernel older than `#13` (`--force` to skip),
`kexec -l` with a 300 s usbsh timeout then checks `kexec_loaded`, and the jump is
`( trap '' HUP; exec setsid sh -c 'sleep 2; sync; exec kexec -e' ) … & true` (a plain `&` job died with the telnet
session; HUP ignored from the fork closes the window before setsid; `& true` because `&;` is a syntax error).
Tests (`tests/test_kexec_tools.py`): fake fdtget, fake usbsh for the version check, the jump under busybox ash with
SIGHUP sent to the shell's process group.

Sources: pmaports `linux-samsung-gts7xl-7.3.4-r12`, `device-samsung-gts7xl-1-r8` (unchanged).
Tests: 121 passed, `test_flash.sh` OK.

| File | sha256 (first 16) |
|---|---|
| `build/recovery-shim.img` (copy: `build/archive/recovery-shim-r12-3754a375.img`) | `3754a375133ef1fb` |
| `build/recovery-shim-signed.img` | `76bfd7747d9bd0ea` |
| `build/shim-Image` | `146128ff9554f7b2` |
| `build/vmlinuz` (kexec payload) | `59b3e3a3e14cc2a2` |
| `build/initramfs` (kexec payload) | `77c0576dd8c6e70b` |
| `build/dtbs/sm8250-samsung-gts7xl.dtb` (= r10) | `c7ce97975c4e3a48` |

Flash (owner present, Download Mode): `tools/flash.sh --keep-vbmeta RECOVERY=build/recovery-shim.img`
(dry run: `heimdall flash --RECOVERY build/recovery-shim.img --no-reboot`). Then, in the r12 debug shell:
`tools/kexec-push.sh` (r12 → r12 is enough for a first test of the jump).

## 2026-11-17T13:51:58+07:00 flash
- RECOVERY: 3754a375133ef1fb14f4baf2a7163802eda4ab872c037639423d4c8d9ea31c88 build/recovery-shim.img

## 2026-11-17 r12 — power key + first successful kexec
- RECOVERY r12 (sha256 3754a375…): pm8941_pwrkey / pm8941_resin present, PS_HOLD warm reset set,
  power key short press toggles display + touch (confirmed by hand).
- `tools/kexec-push.sh` r12 → r12: "kexec_core: Starting new kernel", PSCI CPU1-7 killed, "Bye!", new kernel
  boots with 8 CPUs, panel (TCON ready 334 ms), msm fb0, touch module, USB debug shell back. No reflash needed
  for kernel/DTB iterations from now on.
- Seen once on display-off: `dpu_encoder_helper_wait_for_irq *ERROR* encoder is disabled` (harmless so far).

## 2026-11-17 — r13: QCA6390 Wi-Fi and Bluetooth (kexec, not flashed)

Chip: QCA6390 (stock DT is "converged" for qca6390/qca6490; the vendor partition only has
`firmware/qca6390/` and the PCI id is `17cb:1101`). Stock wiring, from `reference/live/live.dts`:
supplies aon/dig S6A (950-952 mV), io S4A (1.8 V), rfa1 S5A (2.04 V), rfa2 S8C (1.35 V),
antenna switch L5C (1.8 V, no load vote); wlan-en GPIO 90, bt-en GPIO 76, sw-ctrl GPIO 124;
Wi-Fi on PCIe0 (perst 79, wake 81, PHY 0.88/1.2 V = L5A/L9A); BT on QUP SE6 = `uart6`
(GPIO 16-19, stock active pin biases copied).

- linux **e2ad98634** (patch 0019): `qcom,qca6390-pmu` node + `regulators-1` (PM8150L) with
  S8C and L5C; S6A 952 mV and S8C 1352 mV (stock 950/1350 are off the FTSMPS/HFSMPS grid,
  `tests/test_dts_regulators.py`), L5C always on; `&pcie0`, `&pcie0_phy`, `wifi@0`
  (`pci17cb,1101`, `qcom,calibration-variant = "Samsung_gts7xl"`), `&uart6` + `bluetooth`
  (`qcom,qca6390-bt`), alias serial0. `dtbs_check`: only the old simple-framebuffer warning.
- Kernel config: `CONFIG_BT_LE=y` (+ `BT_LE_L2CAP_ECRED`); without it every discovery that
  includes LE is rejected (status 0x0b). Everything else was already in the sm8250 config
  (ATH11K_PCI, MHI, QRTR_MHI, PCI_PWRCTRL_PWRSEQ, POWER_SEQUENCING_QCOM_WCN, BT_HCIUART_QCA, all =m;
  PCIE_QCOM is bool, builtin).
- device r9: depends on linux-firmware-ath11k, linux-firmware-qca, iw, bluez-btmgmt; the
  QCA6390 firmware (5 `.zst` files, ~1.9 MB), `iw`, `btmgmt` and the modules go into the
  initramfs; `pwrseq_qcom_wcn`, `pci_pwrctrl_pwrseq`, `ath11k_pci`, `hci_uart` blacklisted for
  udev there; the hook loads them after the touchscreen (`gts7xl.nowireless` skips them).
  The builtin PCIe controller defers (pwrctrl not bound) until the hook loads the pwrctrl
  driver, then trains the link.

**kexec bug found on the way:** kexec-tools 2.0.32 defaults to kexec_file_load when the kernel
has it; on arm64 that ignores `--dtb` and reuses the running tree. The first r13 kexec booted
the new kernel with the r12 DTB (no PCIe, no uart6). `kexec-push.sh` now passes `-c`
(kexec_load). Earlier kexec tests (r12 → r12) used the same DTB and could not show it.

Result (kexec from r12/r13 debug shell, xz and zstd initramfs both tried):
- `qcom-pcie 1c00000.pcie: PCIe Gen.2 x1 link up`, `[17cb:1101]`, `ath11k_pci: qca6390 hw2.0`,
  `chip_id 0x0 chip_family 0xb board_id 0xff`, fw 0x10121492 (linux-firmware), `wlan0` present.
  Passive scan (`iw dev wlan0 scan passive`, no connection): 16, 25 and 18 BSS on three boots
  (2.4 and 5 GHz). Only counts were looked at.
- hci_uart: `QCA SOC Version 0x400a0200`, `htbtfw20.tlv` + `htnv20.bin` downloaded, setup OK.
  hci0 is **unconfigured** (no BD address: the stock one lives in EFS); with a random one set by
  `btmgmt public-addr` and LE on, `btmgmt find`: 6 devices (BR/EDR-only find before BT_LE: 2).
- Board data: generic `bus=pci,qmi-chip-id=0,qmi-board-id=255` works. The stock `bdwlan.elf`
  (= `bdwlan.e05`, ELF) was also booted through `tools/wlan-fw-overlay.py` (variant
  `Samsung_gts7xl` added to board-2.bin, appended cpio, `kexec-push.sh --overlay`): the loader
  took the overlay's plain board-2.bin (firmware_class dyndbg), wlan0 up, scan OK. Which entry
  ath11k picked is not logged without ATH11K_DEBUG (the variant name is tried first).
  Distribution: Samsung/Qualcomm blobs never go into a package or git; each owner extracts them
  from the stock firmware package (`tools/extract-qca6390-vendor.sh`: super → vendor → debugfs,
  offline) into `build/` and builds the overlay locally. Nothing was mounted on the tablet except
  `apnhlos` read-only (no Wi-Fi files there).

RECOVERY size: with the wireless files the zstd initramfs (19.0 MB) no longer fits before the
stock vbmeta blob (overlap 2.6 MB). pmbootstrap's `lzma` (Go xz) gives 17.2 MB, still too big.
`tools/xz_ramdisk.py` recompresses the same cpio with `xz --check=crc32
--lzma2=preset=9e,dict=32MiB` (15.2 MB, deterministic) for the RECOVERY image only
(`build-recovery-shim.sh`); margin left before the vbmeta blob: 1.16 MB. That xz initramfs was
booted by kexec (unpacks, hooks and wireless OK). The package keeps zstd.

Sources: pmaports d5d84ce29 (`linux-samsung-gts7xl-7.3.4-r13`), aaa55ae63
(`device-samsung-gts7xl-1-r9`). Tests: 135 passed, `test_flash.sh` OK.

| File | sha256 (first 16) |
|---|---|
| `build/recovery-shim.img` (copy: `build/archive/recovery-shim-r13-b7c6df10.img`) | `b7c6df1031b0de52` |
| `build/recovery-shim-signed.img` | `6c9f7f67ef228f7f` |
| `build/shim-Image` | `d8ee2a1ccd9ffa6f` |
| `build/vmlinuz` (kexec payload) | `745d031b738190ca` |
| `build/initramfs` (kexec payload, zstd) | `45b29c004c16c0d0` |
| `build/dtbs/sm8250-samsung-gts7xl.dtb` | `496b84691d6272cc` |

Not flashed. The tablet runs r13 by kexec (xz initramfs test, no overlay, on the last boot).
Next: BD address from EFS (read-only) into the DT or a hook, regulatory/country, a
supplicant for a real connection test, suspend.

## 2026-11-17 — r14: GPI DMA survives kexec (touch after kexec), kexec + Wi-Fi caveat

**Bug:** after a real boot (RECOVERY) touch works; after `tools/kexec-push.sh` the new kernel
gets `gpi 900000.dma-controller: cmd: EV ALLOCATE completion timeout:2`, `error alloc_ev_chan:-5`,
`geni_i2c 994000.i2c: Failed to get rx DMA ch` → no i2c5, no touchscreen.

**Cause:** the GPII channel and event ring contexts are hardware state that outlives the
kernel. Nothing tears them down on kexec, so the next kernel finds GPII 0 still allocated
(read on the first fixed boot: ev state 1 = ALLOCATED, both channels 2 = STARTED) and the
hardware never completes EV ALLOCATE.

**Fix** (linux **c99d858fc**, aport patch 0020, `linux-samsung-gts7xl-7.3.4-r14`, uname `#15`):
- `gpi_reclaim_gpii()`, called in `gpi_ch_init()` once the IRQ is set up and before
  `gpi_alloc_ev_chan()`: reads CH/EV CHSTATE; for each allocated channel CH STOP (if
  started), CH RESET, CH DE_ALLOC, then EV DE_ALLOC (dev_dbg line "gpiiN left allocated").
- `gpi_shutdown()` (platform `.shutdown`, also run by kexec through `device_shutdown()`):
  for each ACTIVE GPII stops/resets/de-allocates its active channels, EV DE_ALLOC, disables the
  interrupts, leaves the software state DISABLE so a later free does not touch the hardware.
- Test: `tests/test_gpi_kexec.py`.

Results (kexec, `gpi.dyndbg=+p` on a shortened command line: the full ABL command line plus
`--append` is over 2048 bytes, "Kernel command line too long"):
1. #14 (unfixed) → #15: probe side: "gpii0 left allocated (ev:1 ch:2/2), resetting it",
   6 CH CTRL + EV DEALLOC, then EV ALLOCATE OK; `5-0049`, "STM FTS1BA90A Touchscreen", i2c
   transfers over GPI OK; display (TCON ready, fb0 msmdrmfb), wlan0 (17 BSS), hci0.
2. #15 → #15: shutdown side: no "left allocated" line (the old kernel's teardown left the
   registers at NOT ALLOCATED), touch OK, display OK.
3. #15 → #15 again: touch OK, display OK, wlan0 OK (20 BSS), BT setup OK.

**Separate kexec + Wi-Fi caveat (not GPI):** in run 2 the old kernel had the QCA6390 powered
and in use; the new kernel got `qcom-pcie: Device not found` and BT `Reading QCA version
information failed (-110)` (sw-ctrl GPIO 124 low). Run 3 started from a kernel with the
wireless modules unloaded (wlan-en low) and Wi-Fi/BT came back. Trying to automate that
(`rmmod hci_uart ath11k_pci qrtr_mhi pci_pwrctrl_pwrseq pwrseq_qcom_wcn` in the kexec jump)
**panicked** the old kernel with Wi-Fi up: SMMU context fault from the PCIe SID, ath11k
`firmware crashed: MHI_CB_EE_RDDM`, root port link down, then a synchronous external abort in
the `qcom_pcie` IRQ thread → `oops=panic` → reboot into RECOVERY (r12). Not kept. Needs a
proper wireless power-off on shutdown (ath11k / pwrctrl / pwrseq) — open.
Also on kexec boots: `DSI PLL(0) lock failed` + clk "already disabled/unprepared" WARNs in
`dsi_phy_driver_probe`; the panel still comes up.

| File | sha256 (first 16) |
|---|---|
| `build/recovery-shim.img` (copy: `build/archive/recovery-shim-r14-ec0a2a64.img`) | `ec0a2a64297f34a7` |
| `build/recovery-shim-signed.img` | `5f0641ae56ce3c7a` |
| `build/shim-Image` | `6edd14f7f6c1db2f` |
| `build/vmlinuz` (kexec payload) | `20b54500239f6f36` |
| `build/initramfs` (kexec payload, zstd) | `5fa5651550ae58bf` |
| `build/dtbs/sm8250-samsung-gts7xl.dtb` (unchanged) | `496b84691d6272cc` |

Tests: 140 passed (`test_modules_hook.py::test_wireless_after_buffyboard_restart` failed once
under load, passed alone and on rerun); `test_flash.sh` OK. Not flashed.

## 2026-11-17 r14 (kexec) — first Wi-Fi connection
- Kexec from RECOVERY #13 into r14 (#15): touch OK after kexec (GPI reclaim), wlan0 present.
- `tools/wifi-connect.sh`: wpa_supplicant 2.11 + libs from the aarch64 rootfs chroot pushed to /tmp/w (not in
  the initramfs yet); WPA2-PSK and WPA3-SAE network blocks; busybox udhcpc needs its own bound script.
- Result on a 5 GHz home AP: WPA2-PSK COMPLETED, -48 dBm, tx 648 Mbit/s HE80 MCS6 NSS2, DHCP lease,
  ping 1.1.1.1 ~23 ms avg, DNS OK. telnetd stays bound to 172.16.42.1 only (not reachable from the LAN).
- Notes: the Alpine wpa_supplicant has no `-f` (log file) support; Wi-Fi after kexec only works when the
  previous kernel had the QCA6390 off (proper wireless power-off at shutdown still to do).

## 2026-11-17 — r15: root filesystem for USERDATA (prepared, not written, not flashed)

Layout: standard pmOS subpartitions. The `--no-split --sector-size 4096` image (own GPT,
header at byte 4096, `pmOS_boot` ext2 + `pmOS_root` ext4) goes raw at the start of userdata
(sda37). Checked in postmarketos-initramfs 3.12.6 (`init_functions.sh`): `mount_subpartitions`
scans every partition, `fdisk -l` must count 2, then `losetup -P --direct-io=on --sector-size
4096`; root/boot by `pmos_root_uuid`/`pmos_boot_uuid`; first boot `parted resizepart 2 100%` +
`resize2fs` on the loop device. Failing to find/mount root ends in `fail_halt_boot` → debug
shell; Volume Down held during `check_keys` → debug shell; Volume Up held → fail on purpose
(→ debug shell too).

device-samsung-gts7xl r10 (pmaports caa85430a):
- `pmos.debug-shell` removed from `deviceinfo_kernel_cmdline`.
- `50-gts7xl-modules.sh`: without `pmos.debug-shell` it still waits for telnetd (late debug
  shell) but loads nothing on timeout: the root filesystem's udev autoloads the modules (the
  blacklist is initramfs only); switch_root kills the background job (`kill -9` of every `sh`).
- `device-samsung-gts7xl-sshd-keyonly`: sshd_config.d drop-in, key only, no root.
- `device-samsung-gts7xl-bluetooth`: bluez + btmgmt; `gts7xl-bt-addr.service` (bluetooth.service
  drop-in, runs before bluetoothd) sets hci0's address with `btmgmt public-addr`, derived from
  `/etc/machine-id` (sha256, locally administered unicast): stable across reboots, EFS never
  read; `hidp` + `uhid` in modules-load.d (both `=m`) for keyboards.
- pmbootstrap config: `ssh_keys = True`, `ssh_key_glob = ~/.ssh/gts7xl_ed25519.pub` (new key
  pair on the build host, private key never in git). Random user password outside the repo.
  Image: console UI, systemd, NetworkManager + wpa_supplicant, sshd, bluetooth.service enabled,
  hostname gts7xl, `/etc/machine-id` empty (generated on first boot).

New tools: `tools/write-userdata.sh` (target by `PARTNAME=userdata`, checks disk/size/PIT start/
holders/mounts/block size, typed `ERASE-USERDATA`, re-resolve, `wget | dd conv=fsync` detached,
byte count, read-back sha256, NOTES log), `tools/serve_file.py` (streams one file). Tests:
`tests/test_write_userdata.py` (fake usbsh), `tests/test_bt_addr.py`, two hook cases.
Dry run against the tablet (read-only): `/dev/sda37`, start byte 12693012480 = PIT USERDATA
block 3098880 × 4096, 243138539520 bytes, 4096-byte blocks, no holders, not mounted.
Runbook: `docs/runbooks/rootfs-on-userdata.md`.

| File | sha256 (first 16) |
|---|---|
| `build/rootfs-r15.img` (1463812096 bytes, raw) | `c021a80ac9801c3f` |
| `build/recovery-shim.img` (copy: `build/archive/recovery-shim-r15-59538de5.img`) | `59538de5022a9d1d` |
| `build/recovery-shim-signed.img` | `6fc1335f44a0c0d5` |
| `build/shim-Image` (= r14) | `6edd14f7f6c1db2f` |
| `build/vmlinuz` (kexec payload, = r14) | `20b54500239f6f36` |
| `build/initramfs` (kexec payload, zstd) | `a54113ffaa78dcee` |
| `build/dtbs/sm8250-samsung-gts7xl.dtb` (= r14) | `496b84691d6272cc` |

Cmdline of the pair (`pmos_root_uuid` = ext4 UUID of the image's `pmOS_root`, checked):

    console=tty0 clk_ignore_unused pd_ignore_unused regulator_ignore_unused cpuidle.off=1 panic=5 oops=panic softlockup_panic=1 nmi_watchdog=panic reboot=warm  pmos_boot_uuid=1f14fc28-9e4c-4baa-8db4-58c747ee7cb9 pmos_root_uuid=793aa611-bf65-4305-a1b4-bd0dfc863699 pmos_rootfsopts=defaults

Risks noted:
- BOOT still holds One UI. A normal boot (or off-mode charging) runs Android's `fs_mgr`, which
  formats a `formattable` userdata it considers wiped (no ext4/f2fs superblock at its start):
  that would erase pmOS. Start only into RECOVERY until BOOT is handled.
- systemd-logind's default `HandlePowerKey=poweroff`: a short power-key press in the root
  filesystem powers the tablet off (the initramfs power-key hook does not run there).

Not fixed, noted: buffyboard 3.6.0 sends `.`, `+`, `*`, `%` as KEY_KPDOT / KEY_KPPLUS /
KEY_KPASTERISK, but its uinput device does not declare those keys, so the kernel drops them
(those characters cannot be typed on the on-screen keyboard in the debug shell).

## 2026-11-17T16:43:00+07:00 userdata write
- image: `rootfs-r15.img`, 1463812096 bytes, sha256 c021a80ac9801c3f6daac6d4988108af7924c71a9a2ec09ef24d978e2a3a4152
- target: /dev/sda37 (PARTNAME=userdata), start byte 12693012480, 243138539520 bytes
- result: OK, 1463812096 bytes written, read back sha256 matches
- 2026-11-17 kexec boot into the rootfs on userdata (cmdline of build/boot.img, no debug shell): systemd
  "running" with no failed units, root /dev/loop0p2 auto-grown to 219.7G, SSH key login over USB OK.

## 2026-11-17 — r15 BOOT image: Linux on a normal power-on (built, not flashed)

Owner decision: BOOT (One UI's normal boot) gets our Linux too, so a normal power-on or
off-mode charging starts postmarketOS and Android's `fs_mgr` can never format userdata.
One UI data is already gone. DTBO and vbmeta stay stock.

`tools/mkboot.py` (called by `tools/build-recovery-shim.sh` after the RECOVERY images):
header v2 fields of the stock boot.img, kernel slot = `build/shim-Image`, ramdisk and cmdline of
`build/boot-signed.img` (the same xz initramfs and UUIDs as RECOVERY r15, no debug shell), dtb =
the stock boot.img's dtb byte for byte, no recovery_dtbo (the ABL applies the DTBO partition on a
normal boot). Image + `SEANDROIDENFORCE` + stock boot vbmeta blob + stock footer with
original_image_size and vbmeta_offset updated.

Size: 68198416 bytes with the trailer in a 71303168-byte partition, but past the stock vbmeta
offset (56000512) and the stock hashed size (55996944) by 12201472 bytes. Shrinking was measured
and rejected: the initramfs would have to be under ~2.9 MB xz; with every module and firmware
file removed it is still 8.75 MB (systemd-udev, cryptsetup/libcrypto, btrfs/xfs tools,
buffyboard). So the blob moves to the first 4096 boundary after the image (68202496),
`--relocate-vbmeta`, which is what magiskboot did to the Magisk BOOT on this tablet (blob at
56143872, footer differs from stock only in original_image_size and vbmeta_offset, its dtb
ends 142832 bytes past the hashed size and the tablet boots it). Upstream libavb
`load_and_verify_hash_partition` loads the whole partition when verification errors are allowed
(unlocked), not the hashed size. RECOVERY is unchanged (r15 rebuilt bit for bit, it still fits
under its stock hashed size).

Checked offline on `boot-shim.img`: header differs from the stock boot only in kernel_size and
ramdisk_size; dtb == stock boot dtb; kernel == shim-Image; ramdisk == RECOVERY r15's; cmdline
== RECOVERY r15's; one trailer; zero padding; blob == stock blob; avbtool info_image reads it.
Tests: 182 passed (with unicorn: the shim emulation runs), `test_flash.sh` OK. The running rootfs
(read-only check over SSH) uses the same `pmos_boot_uuid`/`pmos_root_uuid`.

| File | sha256 (first 16) |
|---|---|
| `build/archive/boot-shim-r15-eba2068f.img` (BOOT, 71303168 bytes) | `eba2068f68d3359b` |
| `build/archive/recovery-shim-r15-59538de5.img` (RECOVERY, unchanged) | `59538de5022a9d1d` |

    tools/flash.sh --keep-vbmeta --pit build/gts7xl.pit \
        RECOVERY=build/archive/recovery-shim-r15-59538de5.img BOOT=build/archive/boot-shim-r15-eba2068f.img

Dry run: `heimdall flash --RECOVERY …/recovery-shim-r15-59538de5.img --BOOT …/boot-shim-r15-eba2068f.img --no-reboot`.
Way back to One UI: `rootfs-on-userdata.md` section 8 (stock boot + stock recovery, then wipe data
from the stock recovery before any normal boot).

## 2026-11-17T17:25:30+07:00 flash
- RECOVERY: 59538de5022a9d1dfcd0c201de334266d42dcf5cc11d5e42d969f3f15dc6c505 build/archive/recovery-shim-r15-59538de5.img
- BOOT: eba2068f68d3359be75544008c0322fd81bae276fa512b245479ebea6ea94535 build/archive/boot-shim-r15-eba2068f.img

## 2026-11-17 — device r11: root, polkit, Bluetooth address, power key, quiet console

Applied to the running rootfs on userdata (no reflash, no kexec): the r11 apks were copied
over SSH and installed with `sudo apk add --allow-untrusted` (apk pins them by checksum in
`/etc/apk/world`, fine while they exist in no repository).

1. **Root.** It was there already: `sudo` is sudo-rs from `postmarketos-base`
   (`%wheel ALL=(ALL) ALL`); it only failed in a non-interactive SSH command because it
   asks for the password on a TTY. `sudo -S -p ""` with the password on stdin works. No
   doas added. What was missing is polkit for SSH sessions (not active, not local):
   new `device-samsung-gts7xl-polkit` (`/usr/share/polkit-1/rules.d/40-gts7xl-wheel.rules`):
   wheel gets every `org.freedesktop.NetworkManager.*` action and login1 power-off / reboot /
   halt (with `-multiple-sessions` and `-ignore-inhibit`) without a prompt. Suspend and
   hibernate keep the defaults.
2. **Bluetooth.** hci0 appears in sysfs at ~8.0 s, but hci_qca finishes its patch/NVM download
   only at ~9.5 s; the service ran at 8.4 s and `btmgmt public-addr` got "Invalid Index" (0x11).
   `gts7xl-bt-addr.sh` now polls mgmt: `info` shows our address → done; `config` lists
   `public-address` as missing → set it; otherwise retry until 60 s (uptime clock, the wall
   clock jumps at boot here), never failing the boot. After reboot:
   "hci0 address set to … after 2s", `bluetoothctl list` shows the controller with the stable
   address, bluetoothd picks it up (ordered after the service). Tests: `tests/test_bt_addr.py`
   (stateful fake btmgmt: setup delay, failed set retried, bounded give-up).
3. **Power key.** Short press did nothing: postmarketos-base-systemd sets
   `HandlePowerKey=ignore` (`/usr/lib/systemd/logind.conf`), logind watches event0 but ignores
   it, and the initramfs watcher is dead after `switch_root` (only an orphaned `dd`/`od` pair from
   it remains, which exits at the next press). Choice: **blank/unblank** as in the debug shell, not
   suspend (s2idle untested, `cpuidle.off=1`, unknown wake sources) and not poweroff (too easy to
   hit). New `device-samsung-gts7xl-console`: the same script as `/usr/libexec/gts7xl-powerkey`,
   `gts7xl-powerkey.service` (static, `multi-user.target.wants` link, foreground, restart on
   failure). Checked: service "watching /dev/input/event0"; `fb0/blank` and the touchscreen
   `inhibited` writes work from the rootfs (one `dpu_encoder_helper_wait_for_irq` error on blank,
   panel back after ~330 ms). **Not checked: a real button press** (needs the owner).
4. **UFS spam.** `ufshcd_wb_curr_buff_threshold_check: dCurWriteBoosterBufferSize read failed -22`
   (KERN_ERR, every 3-8 s, 42 lines in the first 200 s) flooded tty1. Not fixed at the source
   (WriteBooster attribute read on this UFS; look at it with the UFS work). The console package sets
   `kernel.printk = 3 4 1 3` (`/usr/lib/sysctl.d/60-gts7xl-console.conf`): only critical
   messages reach the screen; dmesg and the journal keep everything.

Also: `tools/flash.sh` logs image paths relative to the repo (or the file name) in NOTES.md
instead of absolute paths. Runbook: `rootfs-on-userdata.md` (install `--add` list, sections 0,
6, 9).

Verified after `systemctl reboot` run as the user over SSH (polkit, no password): sudo with the
password → root, `nmcli device wifi rescan` as the user OK, `bluetoothctl list` = 1 controller
(stable address), `btmgmt info` = configured primary controller, `systemctl --failed` empty,
`gts7xl-powerkey`, `bluetooth`, `NetworkManager` active, `kernel.printk` = 3 4 1 3.

| apk (pmaports device r11) | sha256 (first 16) |
|---|---|
| `device-samsung-gts7xl-1-r11.apk` | `a67dd21bee664342` |
| `device-samsung-gts7xl-bluetooth-1-r11.apk` | `962c2021262e6226` |
| `device-samsung-gts7xl-console-1-r11.apk` | `0096b58dccf30b34` |
| `device-samsung-gts7xl-polkit-1-r11.apk` | `8562974cb5ec2869` |
| `device-samsung-gts7xl-sshd-keyonly-1-r11.apk` | `595e108194828b7d` |

The console apk on the tablet is the second r11 build (unit made static); the other four on the
tablet are from the first r11 build (same content, different apk timestamps).

## 2026-11-17 — r16: battery and charging (MAX77705 charger + fuel gauge), built, not flashed (superseded by r17)

r16 on hardware (kexec): the MFD refused the chip ("Rev.0x2 is not tested"), no power supply,
and every rootfs module failed (BTF of another build). The temperature remark in the table
below is wrong: see r17.

Kernel `linux-samsung-gts7xl-7.3.4-r15` (uname `#16`), linux `gts7xl` e46430cdb, 0d11871b2,
4339a19be = aport patches 0021-0023. Config: `MFD_MAX77705`, `CHARGER_MAX77705`,
`BATTERY_MAX17042`, `QCOM_SPMI_ADC5` (+ `QCOM_VADC_COMMON`, `MFD_SIMPLE_MFD_I2C`) built in,
so nothing comes from the root filesystem's modules of the r14 build.

Hardware (stock live DT + vendor kernel): MAX77705 on i2c0 (QUP SE0 0x980000, FIFO mode, no
GPI change): top 0x66, charger 0x69 (registers 0xB0+), fuel gauge 0x36, USB-C/MUIC 0x25 (the
initramfs hook's address: not claimed by any driver, untouched). Interrupt: PM8150L GPIO11
(`chg_int`, level low, pull-up). PCA9468 direct charger 0x57: not described, no driver.
Battery thermistor: PM8150L ADC5 AMUX THM1 (0x4d), stock `adc-temp` with
`battery,thermal_source = 2` (ADC). The fuel gauge TEMP register is not a measurement on this
board (the vendor driver writes the ADC temperature into it): do not trust the battery's `temp`.

Mainline changes:
- max17042: `maxim,max77705-battery` matched the of_match_table but has no i2c_device_id,
  so probe returned -ENODEV; falls back to the OF match data.
- max77705 charger: optional safety monitor, enabled by an `io-channels`/`battery-temp`
  channel: CHG_EN off while configuring; CC = battery `constant-charge-current-max`, CHGIN =
  `input-current-limit-microamp`, CV = `constant-charge-voltage-max`; sysfs writes clamped to
  them; every 10 s: watchdog kick (WDT enabled, as stock), thermistor read, alert-celsius window
  with 2 C hysteresis (failed/implausible read = no charging), safety timer, limits re-checked
  and rewritten if found above ours (else no charging); health OVERHEAT/COLD/SAFETY_TIMER;
  charger `temp` = thermistor. Also fixed: status with CHG_EN off read "Charging"; CHGIN was
  written as mA/25 (stock and the read-back use mA/25 - 1); NULL bat_info before init.
- DTS: MAX77705 MFD, charger@69, fuel-gauge@36 (no interrupt: only SALRT_Th = 0xff00 written),
  `pm8150l_adc` channel 0x4d `batt_therm`, simple-battery node.

### Safety report: every charger value, stock source, ours

Stock sources: `reference/live/live.dts` (local, gitignored; line numbers of the T976BXXS7DXH1
capture) and the vendor kernel `kernel_samsung_sm8250` (droidian-gts7xl, 97e4a5b90),
`drivers/battery_v2/max77705_charger.c` (`chg.c`) / `max77705_fuelgauge.c` (`fg.c`).

| Parameter | Stock | Source | Ours |
|---|---|---|---|
| Float (CV) voltage | 4380 mV new battery; 4270 mV from 1000 cycles | live.dts:34434 `battery,chg_float_voltage`; :34474 `battery,age_data` | **4270 mV** (CV reg 0x0b), lowest stock float |
| voltage-max-design | 4380 mV | live.dts:34434 | 4380 mV (information only; not used for CV) |
| Fast charge current | 450-3150 mA by cable; 975 mA below 5 C; max 3150 | live.dts:34542-34590 cable-info (min 0x1c2 = 450 mA, group 7 :34578); :34449; :34472 | **450 mA** (CC reg 9 = 9 x 50 mA, stock encoding chg.c:709) |
| Input current limit (CHGIN) | 475-1800 mA by cable (USB SDP 475) | live.dts:34542 current_group_1 (0x1db); :34488 max 3000 | **475 mA** (reg 18, stock encoding chg.c:673) |
| Termination (top-off) current | 150 mA at init (500 mA set later by sec-battery) | chg.c:1045 | 150 mA (upstream init value, = stock init) |
| Top-off timer | 30 min (CNFG_03 = 0x9f) | reference/live/dmesg.txt register dump | 30 min (upstream) |
| HW fast-charge timer | disabled | chg.c:1012 | disabled (upstream, = stock) |
| SW charging timer | USB 10 h, TA 5 h, HV 3 h | live.dts:34431 `usb_charging_total_time` 36000 s | **10 h** of charging since plug-in, then off until unplugged |
| Restart threshold / prequal | disabled / disabled | chg.c:1012 | same (upstream) |
| Battery temperature, cold | stop < 0.0 C, recover 2.0 C | live.dts:34392-34393 | stop < 0 C, recover >= 2 C |
| Battery temperature, hot | swelling: stop >= 42.0 C, recover 40.0 C (stop >= 50 C) | live.dts:34442-34443, :34390 | **stop >= 41 C, recover <= 39 C** (WRONG, see r17: the mainline table reads ~1 C HIGH, so this is ~40.1 C real; the cold stop at 0 C was ~-1.3 C real) |
| Thermistor | PM8150L ADC5 0x4d, ratiometric, 200 us settle | live.dts:34501 io-channels, :5138 | same channel, mainline 100K_PU table |
| Watchdog | enabled, kicked by sec-battery | chg.c:1102 | enabled, kicked every 10 s |
| BAT-to-SYS OCP | 6200 mA (CNFG_05 0xf) | live.dts:34435 | 4800 mA (upstream, lower) |
| VCHGIN regulation | 4.6 V with input / 4.5 V | chg.c:1063, :1067 | 4.5 V (upstream) |
| Direct charging (PCA9468) | up to 6000 mA | live.dts:28145 | **off: not described** |
| Fuel gauge sense resistor | fg_resistor 5 -> 1.5625 uV / 2 mOhm | live.dts:34522, fg.c:640 | 2000 uOhm |
| Capacity (design) | 10090 mAh | live.dts:34493 | 10090000 uAh |

Not reproduced (more conservative or not needed at 450 mA): low-temperature current steps,
swelling recharge at 4.15 V, recharge after full (RSTRT off: charging restarts on re-plug),
cable detection (BC1.2/PD/AFC: no MUIC driver, so one set of values for every cable).
Concerns: at 475 mA input the tablet may still discharge on USB with the screen on;
a suspend longer than the watchdog period stops charging (no suspend is used today).

Tests: `tests/test_dts_battery.py` (DT values <= stock, read from live.dts when present, no
PCA9468, drivers built in); `test_dts_gpi.py` i2c0 guard updated. 193 passed with unicorn,
`test_flash.sh` OK. `dtbs_check` of the board: no new warning (log `build/logs/r15-dtbs-check.log`).
`tools/build-recovery-shim.sh --cmdline-from IMG` keeps the cmdline (UUIDs) of an earlier image.

| File | sha256 (first 16) |
|---|---|
| `build/archive/boot-shim-r16-e94bda17.img` (BOOT) | `e94bda17c1aa2266` |
| `build/archive/recovery-shim-r16-80aca546.img` (RECOVERY) | `80aca5463ec2f1ff` |
| `build/shim-Image` | `6b9b71c9a59cf649` |
| `build/vmlinuz` | `6be2dc50f60cc380` |
| `build/initramfs` | `669c7635ef2bc226` |
| `build/dtbs/sm8250-samsung-gts7xl.dtb` | `09cb70daa6b8ccb4` |

Both images carry the r15 cmdline byte for byte (`pmos_boot_uuid=1f14fc28-…`,
`pmos_root_uuid=793aa611-…`). Not flashed.

## 2026-11-17 — r17: charging that really stops, 80 % cap, own module directory (kexec-tested, not flashed)

Kernel `linux-samsung-gts7xl-7.3.4-r17`, release **7.3.4-r17**, uname `#18`. linux `gts7xl`:
05a0bb6d2 (MFD), f38b6835f (review fixes), 706c794ea (DTS 2 C), 31f00ec57 (capacity cap) =
aport patches 0024-0027.

What changed since r16:
1. **MFD accepts this chip.** The tablet's MAX77705 reads PMICID1 0x15, PMICREV 0x02; the vendor
   driver lists it as {0x15, 2} "MD15 PASS2" (logical PASS5, `drivers/mfd/max77705.c:55-66`) and
   reads the charger interrupt the same way as PASS2-4 (`max77705-irq.c:238-249`). Only that pair is
   added to PASS3; the charger and fuel gauge code do not depend on the revision.
2. **Module directory per package revision.** `DEBUG_INFO_BTF_MODULES` ties modules to the exact
   vmlinux, so under r16 every r14 module in `/lib/modules/7.3.4` failed ("failed to validate
   module … BTF: -22": nftables, zram, Bluetooth, fuse). The aport now builds with
   `LOCALVERSION=-r$pkgrel`: r17 is `7.3.4-r17` and its modules live in `/lib/modules/7.3.4-r17`,
   next to r15/r14's `7.3.4`, which stays untouched (the r15 BOOT/RECOVERY keep working).
   The package's `modules.alias` is empty (depmod at build time does not read the .ko.zst):
   **run `depmod -a <release>` after copying modules by hand**; apk installs run the trigger.
3. **Safety review fixes** (independent review of r16, `scratchpad/battery-review-r16.md`):
   - B1: off = CNFG_00 MODE 0x05 → 0x04 (vendor method) **and** CHG_EN 0; on = CHG_EN 1 + MODE 0x05.
     The charger starts off and the monitor turns it on after its first check.
   - S1/S2: the watchdog is kicked only from a read-back safe state (off, or on with every limit
     verified); a watchdog expiry forces off first, limits are checked, the kick comes last.
   - S3: CV/CC/CHGIN targets are encoded from DT, written and read back at probe (mismatch = probe
     fails with the charger off); the monitor compares against the targets.
   - S4: `alert-celsius = <2 41>`: the mainline 100k table reads this thermistor ~1 C high
     between 0 and 45 C against the stock table, so the window is ~0.8 C to ~40.1 C real
     (stock: stop below 0 C, swelling block 42 C).
   - S5: AICL handler stops at 100 mA (reg 3), bounded loop, under the lock (it could wrap to 3.2 A).
   - S7: a register or fuel-gauge read error blocks charging (BLOCK_IO) and leaves the 10 h timer
     as it is; status/charge_type return read errors.
   - S9: `safety_ready` set/checked under the lock, self-requeue only while set, chgin_work flushed:
     nothing re-enables charging after unbind.
   - Also: WDTEN re-enabled if found cleared; "limits rewritten" counted in the log.
   - S6 (documented): the USB-C firmware's AutoIBUS can raise CHGIN_LIM; the monitor rewrites it
     within 10 s (count in dmesg "rewriting them (N so far)"). Not seen during the test.
   - S8 (documented): if the MFD or charger never probes, nothing touches CC/CV/MODE/watchdog; the
     previous owner's settings stay. Before leaving it plugged in, check dmesg for
     "safety monitor:".
4. **80 % cap (owner request).** The monitor reads the fuel-gauge capacity every 10 s: stop at
   `charge_control_end_threshold` (default 80), resume below `charge_control_start_threshold`
   (default 75), same off path; no fuel gauge or a read error = no charging. Both writable
   (start < end <= 100), plus `charge_behaviour` auto / inhibit-charge.
5. Fuel gauge: upstream binds `maxim,max77705-battery` through `simple-mfd-i2c` (FG and hwmon
   cells, client 0x36); the max17042 i2c fallback (patch 0021) is unused here but harmless.

Updated safety table (only the rows that changed from r16):

| Parameter | Stock | Ours r17 |
|---|---|---|
| Battery temperature, cold | stop < 0.0 C, recover 2.0 C (live.dts:34392-34393) | stop < 2 C, recover >= 4 C on the mainline table (~0.8 / ~2.9 C real) |
| Battery temperature, hot | swelling block 42.0 C, recover 40.0 C (live.dts:34442-34443) | stop >= 41 C, recover <= 39 C (~40.1 / ~38.2 C real) |
| Charger off switch | CNFG_00 MODE 0x05 → 0x04 (vendor `max77705_charger.c:385`, 1558-1720) | MODE 0x04 + CHG_EN 0, read back |
| Watchdog | on, kicked every ~10 s | on, kicked every 10 s only from a verified state |
| Capacity window | none (charges to 100 %) | stop at 80 %, resume < 75 % (tunable) |

### Hardware test (kexec from r15, 2026-11-17 19:04-19:18, USB to the host)

Procedure (r15 untouched): copy `usr/lib/modules/7.3.4-r17` from the apk to the rootfs
(`/usr/lib/modules/7.3.4-r17`, root-owned) and `depmod -a 7.3.4-r17`; copy Image (decompressed),
`kexec_dtb.py` DTB (memory from `/sys/firmware/fdt`) and initramfs to `/tmp`; `kexec -c -l …
--reuse-cmdline`; `systemd-run --on-active=2 systemctl kexec` (clean shutdown). Back:
`systemd-run --on-active=2 systemctl reboot` → r15 from BOOT.

Results on r17:
- `max77705 0-0066: PMIC ID 0x15, revision 0x2`; `safety monitor: CC 450000 uA, CHGIN 475000 uA,
  CV reg 0xb, battery 2..41 C, timer 36000 s, capacity 75..80 %`.
- Registers (single-byte reads of the bound charger, `i2cget -f`, read only): CNFG_02 0x49
  (CC reg 9 = 450 mA), CNFG_04 0x0b (4.27 V), CNFG_09 0x92 (CHG_EN 1, CHGIN 18 = 475 mA), CNFG_00
  0x15 (WDTEN, MODE 5). Thermistor 27.4-27.6 C, fuel gauge 28.0 C (stale), 4.01 V, 71-72 %,
  cycle count 1256, full charge 8.83 Ah (design 9.385 Ah in the FG).
- **B1 off switch:** `charge_behaviour=inhibit-charge`, the 80 % cap (end set to 70 with 71 %) and
  a driver unbind all give CNFG_00 0x14, CNFG_09 0x12, CHG_DTLS 0x1 (CC) → **0x8 (charger off)**,
  status "Not charging"; back to 0x15/0x92/CHG_DTLS 0x1 on auto, on resume below start, and on
  rebind. **Battery current did not change** (-260 to -300 mA in both states): on the host port the
  475 mA input is below the system draw (cpuidle off, screen on or blanked), so the charger was in
  supplement mode and never pushed current into the battery. The current-based check needs a
  source above the system draw with the same 475 mA input cap, i.e. it cannot show a difference
  with this limit; the register state (the vendor's own off state) is the evidence.
- Capacity hysteresis: start 60 / end 80 at 71 % stays off (not below start); start 75 → resumes.
- Rebind: first check finds no fuel gauge yet → off (BLOCK_IO), next check on.
- Interrupts: spmi-gpio 10 (max77705), chgin-irq, aicl-irq all 0 (no storm).
- Rootfs modules: after `depmod` 38-40 modules, Bluetooth hci0 back, nftables OK;
  `postmarketos-zram-swap` fails (no zram module in any of our builds, r14 included).
- Not tested: a cable plug/unplug (the cable is the SSH link), a watchdog expiry, temperatures
  outside the window.
- Back on r15: Wi-Fi connected, hci0, no failed unit.

Rootfs change: `/usr/lib/modules/7.3.4-r17` added (root-owned, with depmod output), not apk-managed;
`/usr/lib/modules/7.3.4` untouched, so RECOVERY/BOOT r15 still find their modules. To remove:
`sudo rm -rf /usr/lib/modules/7.3.4-r17`. Before flashing r17 as BOOT, either keep that directory
or install `linux-samsung-gts7xl-7.3.4-r17.apk` in the rootfs (it ships the same directory; apk
then also replaces the r14 package's `/lib/modules/7.3.4`, which the r15 RECOVERY fallback needs:
**do not apk-upgrade the kernel while RECOVERY is r15**, or keep a copy of `7.3.4`).

| File | sha256 (first 16) |
|---|---|
| `build/archive/boot-shim-r17-1f69460a.img` (BOOT) | `1f69460ab8f1f4f1` |
| `build/archive/recovery-shim-r17-d34a442c.img` (RECOVERY) | `d34a442c6377d83f` |
| `build/shim-Image` | `ff15848f2301ed8e` |
| `build/dtbs/sm8250-samsung-gts7xl.dtb` | `7d754d19db599c14` |
| kexec Image (decompressed vmlinuz) | `72e22c7578686174` |
| `build/initramfs` | `df8844ac0fc8c43b` |

Same cmdline (UUIDs) as r15, checked. Not flashed.

    tools/flash.sh --keep-vbmeta --pit build/gts7xl.pit BOOT=build/archive/boot-shim-r17-1f69460a.img

Tests: 201 passed (+ `tests/test_kernel_charger.py`); `test_modules_hook.py::
test_wireless_after_buffyboard_restart` failed once in the full run under load and passed alone
(known flaky since r14); `test_flash.sh` OK.

## 2026-11-17 — r18: input limit per cable type (kexec-tested on the PC port, not flashed)

Owner decision: as stock, per cable: USB SDP (PC port) 475 mA, wall charger (DCP) 1800 mA
(stock cable-info `default_input_current` 0x708). Battery side unchanged (450 mA, 4.27 V, 2-41 C,
10 h, 80/75 %).

Detection: mainline has no MUIC/USB-C driver, but the MAX77705 USB-C firmware runs BC1.2 itself and
reports it in BC_STATUS (USB-C block 0x25, register 0x08; vendor `max77705-muic.h:212-219`, read the
same way by the vendor MUIC driver): bit 7 VBUS present, bits 1:0 CHGTYP 1 SDP / 2 CDP / 3 DCP.
On r15 at the PC port it reads 0x81 (VBUS, SDP). The charger reads it every check with an
unclaimed SMBus read (the initramfs MUIC hook keeps the address). Only VBUS + CHGTYP DCP gives
1800 mA; SDP, CDP, proprietary types, no VBUS or a read error give 475 mA. The selected value is
the monitor's reference: written on a change (plug, unplug, other cable), otherwise "not above"
is enforced, so a lower AICL value stays; AICL stays bounded (100 mA floor). `usb_type` shows
the detected cable. linux 1aebd6d56 (driver + binding), 36208b21a (DTS) = aport patches 0028-0029,
kernel 7.3.4-r18, uname `#19`.

r18 on the tablet (kexec from r15, 19:31): `safety monitor: CC 450000 uA, CHGIN 475000 uA (DCP
1800000 uA) …`, usb_type `[SDP]`, input_current_limit 475000, BC_STATUS 0x81, CNFG_09 0x92.
Modules from `/usr/lib/modules/7.3.4-r18` (r17 directory removed, depmod run), hci0 and Wi-Fi
(wlan0, home LAN address) up after kexec this time.

**B1 battery-current proof on a wall charger: PASSED** (19:38-19:45, owner swapped the cable). A logger runs on the tablet
(`systemd-run --unit=b1-dcp sh /tmp/b1-dcp.sh`, log `/var/tmp/b1-dcp.log`): it waits up to 30 min
for `[DCP]`, then logs auto / inhibit-charge / auto for 60 s each (battery current, voltage,
input limit, BC_STATUS, CNFG_00/09, CHG_DTLS), then waits for the PC port again. Pass: battery
current positive in auto, negative in inhibit-charge, CHG_DTLS 0x8 and CNFG_00 0x14 when inhibited,
input limit 1800000 on DCP and 475000 again on the PC port.

| File | sha256 (first 16) |
|---|---|
| `build/archive/boot-shim-r18-9f062cf6.img` (BOOT) | `9f062cf61e8abe1c` |
| `build/archive/recovery-shim-r18-34b90907.img` (RECOVERY) | `34b909070988008c` |
| kexec Image | `65fe1f902ad93418` |
| `build/initramfs` | `7d11e7ad5cd8831e` |

Same cmdline (UUIDs) as r15. Tests: 204 passed. Not flashed.

## 2026-11-17 — GPU: Adreno 650 (freedreno / turnip) renders, kexec tested, not flashed

Kernel change: DTS only (`DRM_MSM` is built in, adreno included). linux branch `gts7xl-gpu`
90b41160d (rebased on gts7xl 36208b21a, the r18 charger work):
`&gmu` and `&gpu` okay, `&gpu_zap_shader` firmware-name
`qcom/sm8250/samsung/gts7xl/a650_zap.mbn`. `gpu_mem` already sits at the stock pil_gpu
region (0x9031a000, 8 KiB, live.dts `pil_gpu_region`). pmaports branch `gts7xl-gpu`
5f9ea52ec (on gts7xl e4e87e8a0, r18): kernel patch 0030 and pkgrel 19,
`device-samsung-gts7xl-nonfree-firmware` (linux-firmware-qcom + firmware-samsung-gts7xl-gpu),
`firmware-samsung-gts7xl-gpu` (local build only, the .mbn is gitignored).

Firmware:
- `qcom/a650_sqe.fw`, `qcom/a650_gmu.bin`: linux-firmware-qcom (GMU firmware v2.1.8).
- Zap shader: not in vendor `/firmware` (only a615/a620 there). It is in the BL tar,
  `NON-HLOS.bin` (FAT16) `image/a650_zap.{mdt,b00,b01,b02}`, Samsung-signed: never commit
  or publish it. `tools/extract-gpu-zap.py BL_<...>.tar.md5 build/firmware-gpu` reads the
  FAT (VFAT long names) and joins it with `tools/pil-squash.py` into `a650_zap.mbn`
  (13964 bytes, sha256 c74bdb38d0420996 for T976BXXS7DXH1). Install on the tablet as
  `/lib/firmware/qcom/sm8250/samsung/gts7xl/a650_zap.mbn`, or copy it into the aport dir and
  build `firmware-samsung-gts7xl-gpu`.
- The SQE request at 0.43 s (initramfs, no firmware there) fails harmlessly; msm retries on
  first open from the root filesystem (7.5 s: "loaded qcom/a650_sqe.fw", "Loaded GMU
  firmware v2.1.8"). No need to put GPU firmware in the initramfs.

Test (kexec, three times, back to r15 each time with Wi-Fi and Bluetooth up): r14 Image
(byte-identical to the running r15 BOOT kernel, `#15`, so the rootfs modules match) + the
r14 DTS (c99d858fc, decompiled DTB identical to the r14 package except the three GPU
properties) + the GPU nodes. Root filesystem packages added on the tablet (apk files
fetched in the pmbootstrap aarch64 chroot, `apk add --no-network`): linux-firmware-qcom,
mesa-gl, mesa-vulkan-freedreno, vulkan-loader, vulkan-tools, mesa-utils, kmscube, glmark2,
libdrm-tests (+ deps). Results (build/gpu/test-19*/):
- dmesg: GPU bound to msm_dpu, no zap, fault or hang message; `supply vdd/vddcx not found`
  (dummy, as on other sm8250 boards), `Couldn't register GPU cooling device` (no
  `#cooling-cells`; harmless), gpucc/gcc `sync_state() pending due to 3d6a000.gmu`.
- `eglinfo -B -p gbm` / `-p surfaceless`: Mesa 26.3.0 freedreno `FD650`, OpenGL 4.6 core,
  OpenGL ES 3.2.
- `vulkaninfo --summary`: `Turnip Adreno (TM) 650`, Vulkan 1.3.363, conformance 1.4.6.1;
  `vkcube --wsi display` selects it.
- `glmark2-es2-drm` on screen (2800x1752, kmscon stopped): score 790 (build 1187 fps,
  terrain 68, refract 123); off screen score 466.
- kmscube on screen runs (DRM master needs `systemctl stop kmsconvt@tty1`: kmscon holds it);
  `-c 1/61/241` exit 0. `modetest -M msm -v -s 36:2800x1752` (connector 36 = DSI-1): page
  flips at 119.6-120.3 Hz, so the command-mode panel flips at its full rate.

The flip-rate run (19:46) did not get back to r15 on its own: the owner put the tablet in
Download Mode for the r18 BOOT flash while it was rebooting (not a GPU fault).

Open issues: GPU
cooling device / thermal zones; GPU OPPs and speed bin not checked against the stock
pwrlevels (top stock level 0x22fce8c0 = 587 MHz); kmscon on tty1 must yield the DRM master
to a compositor (logind seat / VT switch). Not flashed; the next BOOT needs patch 0030 merged
into the kernel package (kexec tests used the r14/#15 Image; the GPU DTS was not yet
kexec-tested on top of the r18 kernel).

B1 result (`/var/tmp/b1-dcp.log` on the tablet, 10 s samples):
- 19:38:43 wall charger detected: BC_STATUS 0x8b (VBUS, CHGTYP DCP), usb_type `[DCP]`, input limit
  1800000.
- AUTO (60 s): battery current +435 to +477 mA (avg +441 mA, i.e. the 450 mA charge current),
  4.04-4.05 V, CNFG_00 0x15, CHG_DTLS 0x1, "Charging".
- inhibit-charge (60 s): battery current falls to +36 → 0 → -15 mA (avg +5 mA), CNFG_00 0x14,
  CNFG_09 0x47 (CHG_EN 0, input limit reg 71 = 1800 mA), CHG_DTLS 0x8, "Not charging".
- AUTO again (60 s): +437 to +473 mA (avg +445 mA).
- Thermistor 27.9-28.2 C throughout.
- Unplugged: usb_type unknown, input limit 475000 at once; PC port back: BC_STATUS 0x81 `[SDP]`,
  475000.

So the off switch (MODE 0x04 + CHG_EN 0) really stops battery current, the DCP limit applies only
on a detected wall charger, and the limit falls back to 475 mA on unplug.

## 2026-11-17T19:48:56+07:00 flash
- BOOT: 9f062cf61e8abe1c32b8d65149dcffa947485bf8490773a212be68d3f9b26dce build/archive/boot-shim-r18-9f062cf6.img

## 2026-11-17 — r19: r18 + Adreno 650 GPU (kexec-tested from r18, not flashed)

Kernel `linux-samsung-gts7xl-7.3.4-r19`, release **7.3.4-r19**, uname `#20`: r18 + aport patch
0030 (linux `gts7xl` 90b41160d, GPU nodes). The decompiled DTB differs from r18 only by the three
GPU properties (gmu/gpu status, zap firmware-name): every charger setting is r18's. pmaports
`gts7xl` 3f1d134fe (+ `device-samsung-gts7xl` r12 with `-nonfree-firmware`,
`firmware-samsung-gts7xl-gpu-20240802`, built locally only).

Images: kernel r19 installed in the rootfs chroot (`pmbootstrap chroot -r -- apk add
--no-network -u linux-samsung-gts7xl`, mkinitfs ran), `pmbootstrap export build/`,
`tools/build-recovery-shim.sh --cmdline-from build/archive/boot-shim-r18-9f062cf6.img` (cmdline
identical to r18, checked).

| File | sha256 (first 16) |
|---|---|
| `build/archive/boot-shim-r19-671d2d87.img` (BOOT) | `671d2d8731149178` |
| `build/archive/recovery-shim-r19-2c2d1d3f.img` (RECOVERY) | `2c2d1d3fe6e2325b` |
| `build/shim-Image` | `99f0b6b67ec08cf4` |
| `build/dtbs/sm8250-samsung-gts7xl.dtb` | `b38387914e6a6d7a` |

Rootfs: `/usr/lib/modules/7.3.4-r19` added from the apk (root-owned, `depmod -a 7.3.4-r19`),
`7.3.4` and `7.3.4-r18` untouched. GPU userspace and the zap shader were installed earlier
(GPU entry above).

Kexec test from r18 BOOT (19:58-20:01, build/gpu/r19-test-195820/), back to r18 by reboot:
- r19: `safety monitor: CC 450000 uA, CHGIN 475000 uA (DCP 1800000 uA), CV reg 0xb, battery
  2..41 C, timer 36000 s, capacity 75..80 %` (same line as r18), usb_type `[SDP]`,
  input_current_limit 475000, hci0, wlan0 up (Wi-Fi came back after kexec), no failed unit,
  0 "BTF: -22".
- GPU: GMU firmware v2.1.8, freedreno FD650 (OpenGL ES 3.2), turnip Adreno 650 (Vulkan 1.3),
  `glmark2-es2-drm` on screen score 819 (kmscon stopped for the test, restarted).
- Back on r18: same charger line, `[SDP]`, 475000, hci0, Wi-Fi.

Tests: 205 passed, `test_flash.sh` OK. Flash when the tablet is in Download Mode:

    printf 'FLASH\n' | FLASH_SSH="ssh localhost" tools/flash.sh --pit build/gts7xl.pit --keep-vbmeta \
        BOOT=build/archive/boot-shim-r19-671d2d87.img

## 2026-11-17T20:04:04+07:00 flash
- BOOT: 671d2d873114917849007942f0b8a00ffd619b6e370afb252c9174ff1de19897 build/archive/boot-shim-r19-671d2d87.img

## 2026-11-17 — Hyprland on pmOS: hardware validation (userspace only)

`device-samsung-gts7xl-hyprland` (pmaports 537abe4f4, device r13): greetd on tty1 (autologin of
the first regular user in the video group, tuigreet after logout), kmsconvt@tty1 disabled,
getty on tty2+ (Ctrl+Alt+F2). Defaults seeded into ~/.config by `gts7xl-hyprland`.
Hyprland 0.54.3 (Alpine): DSI-1 2800x1752@120, scale 2 (1400x876), freedreno via GBM,
touchscreen bound to DSI-1 (owner: "ça marche bien"), BT keyboard seen (layout us, mod ALT: the
keyboard is QWERTY without a Super key), `misc:disable_hyprland_guiutils_check` (not packaged
in Alpine). Power key: `gts7xl-hypr-dpms` toggles DPMS; **physical press validated by the owner** (screen
off/on under Hyprland). No sound card, no accelerometer. Screenshot:
`build/gui/hyprland-desktop.png` (local only: shows the network name). grim from an SSH session
hung once while the panel was idle; with the session active it works.
Next target: Omarchy aarch64, design in `docs/omarchy-aarch64-design.md`.

## 2026-11-17 — audio: speakers (ADSP + 4x CS35L41), kexec-tested on r40, validated by ear

Hardware (stock live DT + vendor `techpack/audio/asoc/kona.c`, `sound/soc/codecs/cs35l41.c`):
- 4x **CS35L41** rev A0 (DEVID 0x35a40; stock part name "cs35l40-spk") on QUP SE11 = `i2c11`
  (0xa8c000, 1 MHz, GPIO 60/61) at 0x40-0x43; one shared reset (GPIO 69) and one shared
  interrupt line (GPIO 84); VA/VP are a dummy always-on supply in stock.
- Bus: **Primary TDM** (AFE port 0x9000), SoC clock provider, gpio138 sck / 139 din / 140 dout /
  141 ws (stock `pri_tdm_*_active`), stock q6 settings: short sync, internal, 1-bit delay.
- Boost: stock peak 4100 mA; the stock driver writes no inductor/capacitor values, the boost
  registers stay at reset (BSTCVRT_COEFF 0x2424, SLOPE_LBST 0x7500) = what mainline programs for
  1.0 uH / 0-19 uF. Read back on the tablet: identical.
- Speaker protection: Samsung runs a Cirrus DSP firmware (vendor `/firmware/cs35l40-spk-dsp1-spk-prot.{wmfw,bin}`,
  tuning "TAB_S7P_SPKPV2_PPP_20200602", only DSP coefficients, no register patches). **Not loaded
  here** (no protection), so the gains are capped instead (below).
- Positions checked by ear, one amp at a time, landscape as the display is mounted (Hyprland):
  **0x41 top left, 0x40 bottom left, 0x43 top right, 0x42 bottom right.** The stock
  `cirrus,right-channel-amp` flags (0x42, 0x40) do not match this orientation and are not used.

Kernel (linux `gts7xl-audio`, aport patches 0031-0032, test package pkgrel 40 = release 7.3.4-r40):
- 77d829629 `ASoC: qcom: sm8250: primary TDM with several codecs`: 4 slots x 16 bit, 48 kHz,
  BCLK 3.072 MHz (PRI_TDM_IBIT, stays on like the MI2S ports), DSP_A, codec n gets slot n % 2,
  SCLK as the codec PLL reference. q6afe uses the "invert" clock attribute for TDM, so the codecs
  are NB_NF (stock: normal SoC clock + IB codec). 32-bit slots like stock are impossible: mainline
  cs35l41 ties the ASP slot width to the sample width and accepts only S16/S24.
- 5a3206351 DTS: `&adsp` (firmware `qcom/sm8250/samsung/gts7xl/adsp.mbn`), `&gpi_dma1` (stock EE
  offset 0x6000), `&qupv3_id_1`, `&i2c11` + 4 amps (sound-name-prefix Top/Bottom Left/Right,
  reset on every node: first prober owns it, others "assuming shared reset"; interrupt open drain
  + SoC pull-up instead of stock push-pull x4 on one line), `&q6afedai` PRIMARY_TDM_RX_0,
  `&q6asmdai` MultiMedia1/2, `&sound` (qcom,sm8250-sndcard, link order TL, TR, BL, BR).
- Config was already complete (QDSP6, CS35L41_I2C, SM8250, in-kernel PD mapper).

Firmware: `tools/extract-adsp.py BL_<...>.tar.md5 build/firmware-audio` (FAT reader of
extract-gpu-zap.py + pil-squash): NON-HLOS `image/adsp.{mdt,b00-b20}` -> `adsp.mbn` (23892108 bytes,
sha256 97ccdbf8fae60781 for T976BXXS7DXH1) + `adspr.jsn`, `adspua.jsn`. Samsung-signed: never
commit. Installed in `/lib/firmware/qcom/sm8250/samsung/gts7xl/`. The linux-firmware RB5 adsp.mbn
in `qcom/sm8250/` is not signed for this board.

Userspace (pmaports `gts7xl-audio` 7641d5002, 975d02ec9):
- `alsa-ucm-conf-samsung-gts7xl`: `conf.d/sm8250/Samsung Galaxy Tab S7+ 5G.conf` ->
  `Samsung/gts7xl/HiFi.conf` (verb HiFi: `PRIMARY_TDM_RX_0 Audio Mixer MultiMedia1`; device
  Speaker: every amp Analog PCM Volume 6 = 6.5 dB (range 0.5-20.5), Digital PCM Volume 817 = 0 dB
  (raw 913 = +12 dB), volume in software) and
  `/usr/share/wireplumber/wireplumber.conf.d/51-gts7xl-speakers.conf`: **PipeWire must use S16LE**
  on this card: with its default S24_LE on MultiMedia1 nothing is audible (cliamp stream measured
  at -20 dBFS peak on the sink monitor, owner heard nothing); with S16LE it plays.
- `firmware-samsung-gts7xl-adsp` (local build only), `device-samsung-gts7xl` r13
  (-nonfree-firmware pulls both).
- Tablet rootfs additions (by hand, carry to Omarchy): alsa-utils, alsa-ucm-conf, pipewire-alsa,
  pipewire-pulse, pipewire-tools; the firmware and UCM files above; `/usr/local/bin/cliamp`.
  cliamp v2.4.1: the official linux-arm64 release (sha256 f4e591542bb834fd, matches
  checksums.txt) is glibc-linked and does not run on Alpine (gcompat lacks `__*_chk`); here it is
  built from the v2.4.1 tag on the tablet (musl, `go build`, build deps removed). On Omarchy (glibc)
  the release binary runs as is; it needs `pipewire-alsa` (plain ALSA fails: q6asm rejects its
  buffer size, and a dmix wrapper hangs).

Tests on the tablet (kexec from r19, build/audio/test-7.3.4-r40-*/):
- `remote processor adsp is now up`, APR services 3/4/7/8, 4x `Cirrus Logic CS35L41 (35a40),
  Revision: A0`, card `S5G [Samsung Galaxy Tab S7+ 5G]`, cs35l41 interrupt count 0 after playback,
  0 "BTF: -22". Charger safety-monitor line identical to r19, Bluetooth and Wi-Fi up.
- By ear (owner): -30 dBFS tones at 0.5 dB analog gain: faint; one amp at a time (880 Hz,
  -20 dBFS, 6.5 dB): all four heard, positions above; left/right tones via PipeWire after the
  mapping fix: "low left, high right" = stereo correct; cliamp + Rainwave Chiptune
  (`https://relay.rainwave.cc/chiptune.mp3`) via PipeWire at cliamp -10 dB: plays.
- Open: `AFE failed to vote (3)` and one AFE set-param error 0x16 at ADSP start (pipa carries a
  HACK for the vote; playback unaffected); no speaker protection firmware; no IV feedback
  (Primary TDM TX); headset over USB-C and microphones not started.

## 2026-11-17 — r20: r19 + speakers (kexec-tested from r19, not flashed yet)

Kernel `linux-samsung-gts7xl-7.3.4-r20`, release **7.3.4-r20**, uname `#21`: r19 + aport patches
0031-0032 (linux `gts7xl` fast-forwarded to 5a3206351). pmaports `gts7xl` (fast-forwarded from
`gts7xl-audio`, on top of the hyprland r13 commit): device-samsung-gts7xl r14 (-nonfree-firmware
pulls firmware-samsung-gts7xl-adsp + alsa-ucm-conf-samsung-gts7xl), alsa-ucm-conf-samsung-gts7xl
r1 (r0 in local repos predates the WirePlumber rule). Images from the rootfs chroot (apk add -u,
mkinitfs, export), `tools/build-recovery-shim.sh --cmdline-from build/archive/boot-shim-r19-671d2d87.img`.

| File | sha256 (first 16) |
|---|---|
| `build/archive/boot-shim-r20-09873501.img` (BOOT) | `0987350180097721` |
| `build/archive/recovery-shim-r20-d83462ba.img` (RECOVERY) | `d83462bae64cf898` |
| `build/shim-Image` | `52d265af06a8950c` |
| `build/dtbs/sm8250-samsung-gts7xl.dtb` | `bb7fbfec7787b4ab` |

Tablet rootfs: `/usr/lib/modules/7.3.4-r20` (from the apk, depmod), r18/r19 directories kept;
firmware-samsung-gts7xl-adsp and alsa-ucm-conf-samsung-gts7xl r1 installed with apk (the user
WirePlumber rule from the r40 tests removed, the packaged one is used).

Kexec test from r19 (21:27-21:30, build/audio/test-7.3.4-r20-212710/), back to r19 by reboot:
same safety-monitor line as r19, `[SDP]`, 475000, hci0, wlan0; GMU firmware v2.1.8 loaded;
ADSP up, 4 amps, card S5G; PipeWire sink "Built-in Audio Speakers", stream opened S16_LE
(packaged rule), 3x left/right tones played, cs35l41 interrupts 0. Not re-checked by ear on r20
(same kernel code and DTB as the r40 build the owner listened to).

    printf 'FLASH\n' | FLASH_SSH="ssh localhost" tools/flash.sh --pit build/gts7xl.pit --keep-vbmeta \
        BOOT=build/archive/boot-shim-r20-09873501.img

## 2026-11-17T21:34:14+07:00 flash
- BOOT: 0987350180097721d8e63cb80a26643cba7b86c10923545728e48ecdb0947640 build/archive/boot-shim-r20-09873501.img

## 2026-11-17 — Omarchy 4.5.0 aarch64 image for USERDATA (built, not written)

Design and build details: `docs/omarchy-aarch64-design.md` (section 8). Source: the official
`omarchy-4.5.0-aarch64.iso` (sha256 c9a9dd1107c10924…, from iso.omarchy.org), its prebuilt root
image `omarchy-root.img.zst` (sha256 64c292886b3b4e38…, matches the ISO's .sha256).
`tools/build-omarchy-rootfs.sh stage|setup|device|image` (qemu-user chroot in a private mount
namespace), device layer `arch/gts7xl-device`, kernel package `arch/linux-gts7xl`.

Image `build/omarchy/omarchy-gts7xl.img` (local only: Samsung zap shader, password hash, SSH
host keys): 15.8 GiB (11 GiB allocated), sha256
`b4f8b5aee8f8fb9e55896d4197cce1794e94a3a984eeab3d1c71fe428a923eec`. GPT 4096-byte sectors,
p1 pmOS_boot ext2 (tablet's boot filesystem content) and p2 pmOS_root ext4 (14.9 GiB, grown on
the first boot), the current UUIDs (1f14fc28-…, 793aa611-…: same as BOOT r20 and RECOVERY r15
cmdlines); e2fsck -fn clean. Contents: Omarchy 4.5.0 (hyprland 0.56.2, SDDM autologin of
`tarpediem` into the Omarchy session), `linux-gts7xl 7.3.4.r20` (modules 7.3.4-r20 + BOOT image
r20 09873501, write-boot hook in dry run), fallback modules 7.3.4 (r14, for RECOVERY r15),
linux-firmware-qcom + atheros, zap shader, vulkan-freedreno, squeekboard, kmscon on tty2+,
en_US.UTF-8, us layout, left Alt = Super on the BT keyboard, scale 2, touch bound to DSI-1,
power key = DPMS, gts7xl-bt-addr, gts7xl-powerkey, Esc hwdb, polkit, sshd key-only with the
current SSH host keys and authorized key, hostname gts7xl, first-boot firewall unit.
User password: generated, in `build/omarchy/credentials/password` (600, never published).
Not in it yet: the audio work (ADSP firmware, UCM, PipeWire setup of r20).

pmOS backup before wiping (`build/backup-pmos-20261117/`, 700, local only, contains the Wi-Fi
key): `pmos-root.tar.zst` (full root, one filesystem, without /var/cache/apk; 25894 entries,
read back), `pmos-boot.tar.zst`, `extracts.tar.zst` (home, /etc, bluetooth, modules, zap),
`packages.txt`, `cmdline-uuids.txt`, `SHA256SUMS`. Taken 21:12-21:15 on r19 (before the r20
flash).

### 2026-11-17 — Omarchy image completed (audio, Wi-Fi, poubelle, Firefox, speaker protection)

`build/omarchy/omarchy-gts7xl.img` rebuilt: sha256
`9a8abc42accc65dd8248dbf99de0e834084ee9ac2a9dd6b8a89d9da655c9adef`, e2fsck -fn clean, root
15.5 GiB (grows on first boot). Added: ADSP firmware and UCM/WirePlumber files from
`firmware-samsung-gts7xl-adsp` / `alsa-ucm-conf-samsung-gts7xl` r1, alsa-utils (pipewire-alsa,
pipewire-pulse, btop already in Omarchy), cliamp v2.4.1 linux-arm64 (`/usr/local/bin`, sha256
f4e591542bb834fd = checksums.txt), Firefox 160 (next to Omarchy's Chromium), the saved
NetworkManager connection (600 root, from the pmOS backup), hostname poubelle (/etc/hostname,
/etc/hosts), /etc/motd (rebutos), IgnorePkg for foreign kernels + an aborting pacman hook
(`00-gts7xl-no-foreign-kernel.hook`) + an Omarchy pre-refresh-pacman user hook that puts
IgnorePkg back after `omarchy refresh pacman`.
Speaker protection: volume keys rebound to `gts7xl-volume` (wpctl, max 0.6); PipeWire
filter-chain sink "Speakers (protected)" (`/usr/share/pipewire/pipewire.conf.d/60-gts7xl-speaker-protection.conf`):
2x bq_highpass 180 Hz (24 dB/oct) + linear x0.5 (-6 dB), playback to
`alsa_output.platform-sound.HiFi__Speaker__sink`, session priority 2000 (default sink). Checked
on pmOS (Alpine needs pipewire-filter-graph{,-builtin}; Arch ships the module): sink created,
linked to the speakers, default; `node.dont-reconnect` had to go (the playback side starts before
the ALSA sink exists). No limiter yet (no LSP/LADSPA in the snapshot): open.

## 2026-11-17T22:06:19+07:00 userdata write
- image: `omarchy-gts7xl.img`, 17185112064 bytes, sha256 9a8abc42accc65dd8248dbf99de0e834084ee9ac2a9dd6b8a89d9da655c9adef
- target: /dev/sda37 (PARTNAME=userdata), start byte 12693012480, 243138539520 bytes
- result: OK, 17185112064 bytes written, read back sha256 matches

### 2026-11-17 — Omarchy on the tablet: first boot

USERDATA written by the owner (sha256 9a8abc42…, read back OK). Normal boot (BOOT r20): Omarchy
up in ~25 s, root grown to 223 GiB, no failed unit except ufw (see below), 0 "BTF: -22", charger
safety monitor line present, usb_type [SDP] (input_current_limit read 450000 once: AICL step,
under the 475 mA reference), GPU freedreno FD650 (Hyprland renderer), ADSP up + 4 CS35L41,
default sink "Speakers (protected)" linked to the speakers, Firefox 160, cliamp v2.4.1, hostname
poubelle, touch device bound, kmscon on tty2 (JetBrainsMono 20), squeekboard shows on request.
Fixed live and in the build (arch/gts7xl-device, build script): no sudoers rule for wheel (the
ISO's archinstall writes it; got root once through the session's polkit agent: pkexec typed by
wtype), `misc.vfr` unknown in Omarchy's Lua config, udisks asked for a password to mount the
root loop's partitions (UDISKS_IGNORE rule), the Wi-Fi connection was bound to `wlan0`
(interface is wlp1s0), clock in 1971 (NTP enabled, Asia/Bangkok), Bluetooth: pmOS machine-id
kept for gts7xl-bt-addr (same controller address D6:71:…) + /var/lib/bluetooth: keyboard
paired/trusted again. Open: ufw.service fails at boot (kernel lacks xt_limit / ip6 rules
modules: "Extension limit revision 0 not supported"), firewall partly applied.

### 2026-11-17 — GNOME next to Omarchy/Hyprland (live tablet), user password

Installed on the running tablet (not in the image): gnome-shell 51.1, gnome-session,
gnome-control-center, nautilus, gnome-text-editor, gnome-console, xdg-desktop-portal-gnome,
gnome-keyring (+ ~55 dependencies; gstreamer/gst-plugins-{base,bad}-libs 1.28.8 -> 1.28.9 as the
only upgrades, the rest of the 4.5.0 snapshot untouched). pacman needs `--disable-sandbox` (kernel
without Landlock) and the ALARM mirror as fallback (Omarchy's stable mirror 404s some files).
SDDM autologin session = gnome.desktop (Hyprland/Omarchy still selectable; backup
/root/autologin.conf.bak-pre-gnome). GNOME state checked over D-Bus: DSI-1 2800x1752@120 scale
2.0, on-screen keyboard enabled, us layout, LANG en_US.UTF-8, over-amplification off,
power-button-action nothing, default sink "Speakers (protected)", BT keyboard connected.
Power key under GNOME: gts7xl-powerkey (touch inhibit) now also calls gts7xl-session-dpms
(mutter PowerSaveMode 3/0 as the session user; tested off/on over SSH). fcitx5 (Omarchy user unit)
does not start under GNOME (ExecCondition drop-in), squeekboard only under Hyprland. dconf
defaults in /etc/dconf/db/local.d/00-gts7xl. GNOME blocks screenshots from SSH (Shell.Screenshot
denied), so no grim-like capture there: owner photo instead.
User password: the owner's home Wi-Fi key (set on the tablet from the saved connection, never
printed); the generated build password was shredded on the host. The build script now does the
same by default (PASSWORD_FROM_WIFI=1).
Kernel config to add in the next rev: Landlock (CONFIG_SECURITY_LANDLOCK + in lsm=) for pacman's
sandbox; netfilter matches for ufw (xt_limit and the other xt_* ufw uses, IPv6 tables:
IP6_NF_IPTABLES/filter, "Extension limit revision 0 not supported").
GNOME touch setup (2026-11-17, live tablet): extensions from extensions.gnome.org for shell 51
(arch/gts7xl-device/gnome-extensions.txt: Dash to Dock 110, AppIndicator 66, Just Perfection 37;
GJS OSK skipped: no 51 in its metadata, built-in OSK kept; Blur my Shell skipped). Settings
(files/gts7xl-gnome-setup): dock at the bottom, always visible, 64 px icons, minimize-or-previews,
apps button; favorites Firefox, Console, Files, Settings, cliamp; dark, accent pink (matches the
owner's rebutos wallpaper set by the coordinator), battery %, panel 48 px, tap-to-click, natural
scroll, cursor 24, text scaling 1.0. All three extensions ACTIVE after a session restart.

## 2026-11-17 night — r21 (Landlock, ufw netfilter, GPU cooling), tablet polish (not flashed)

Kernel `linux-samsung-gts7xl-7.3.4-r21` (uname `#22`), pmaports gts7xl 0f762b509: config only —
CONFIG_SECURITY_LANDLOCK=y (CONFIG_LSM already lists landlock), netfilter for ufw
(NETFILTER_XT_MATCH_LIMIT/RECENT/HL/STATE/PKTTYPE, IP6_NF_MATCH_IPV6HEADER/RT/HL),
CONFIG_DEVFREQ_THERMAL=y (GPU cooling device). ZRAM was already built in.
Kexec test from Omarchy r20 (build/r21-test-225818): `lsm` = lockdown,capability,landlock,yama,bpf;
no failed unit (ufw.service active, `ufw status` active); pacman -Sy works with its sandbox;
5 cooling devices (4 before), no "Couldn't register GPU cooling device"; charger safety line,
[SDP], 475000; Wi-Fi, Bluetooth (same address), ADSP + GMU, GNOME, protected sink; back on r20.

| File | sha256 |
|---|---|
| `build/archive/boot-shim-r21-fbb8aa14.img` (BOOT) | `fbb8aa1401e3c2c0f86d74f22c5ca37d0b0648011dfc4cd396726516f2401343` |
| `build/archive/recovery-shim-r21-f8c89b85.img` (RECOVERY, not to flash) | `f8c89b85…` |

Same cmdline UUIDs as r20. Omarchy has `linux-gts7xl 7.3.4.r21-1` installed (modules 7.3.4-r21,
BOOT image fbb8aa14, hook dry run checked on the tablet: BOOT = /dev/sda23); 7.3.4-r20 (running
BOOT) and 7.3.4 (RECOVERY r15 fallback) module dirs kept outside pacman. kexec-tools installed.
A first r21 build was superseded (build/superseded/) before DEVFREQ_THERMAL; pmbootstrap's rootfs
chroot needed `apk add <file>` to take the rebuilt same-version package.

Polish on the live tablet (and in arch/gts7xl-device): GNOME app folders (Omarchy, Terminal tools,
Office, System), screen blank 5 min, no idle suspend, Firefox touch prefs
(/usr/lib/firefox/browser/defaults/preferences/gts7xl.js), kmscon font 28, zram 7.2 G zstd
active (unmasked), gnome-tweaks + extension-manager installed, GNOME first-login autostart in the
image build, owner's wallpaper + fastfetch config carried by the build (local files).
Host: NetworkManager profile `gts7xl-usb` (172.16.42.2/24 on enp202s0f3u1): the Omarchy rootfs runs
no DHCP server on usb0, so the host lost its address after a re-enumeration.
USB OTG / host: design only, docs/usb-dual-role-design.md.

## 2026-11-17 night — sensors, hall, S Pen, cameras: bring-up prepared (not tested on hardware)

No kexec and no root on the tablet from this agent (the sudo password is not typed by agents):
everything below is built and staged, the hardware test is `tools/sensors-kexec-test.sh`.

Sensors (stock live DT + vendor.img `/etc/sensors` + persist backup):
- Everything sits behind the **SLPI** (`qcom,ssc@5c00000`, PIL "slpi"), on the SSC buses:
  **LSM6DSO** accel/gyro (SSC SPI 1), **AK0991x** magnetometer, two **VEML3328** light/RGB
  sensors, no proximity. Stock sensor list: light_cct, ambient_light, mag, accel, gyro, temp,
  pickup, sar_backoff_motion. Mainline path = SLPI remoteproc + hexagonrpcd (sdsp, serves the
  registry and the `/sdsp` libraries) + libssc + iio-sensor-proxy (already on Omarchy: ALARM
  iio-sensor-proxy 3.9 linked with libssc 0.4.4, `ssccli` present). Same scheme as pmOS
  xiaomi-pipa/elish (sm8250) and samsung-starqltechn.
- Sensor supply: stock `sensor_vdd` = L8C fixed 1.8 V, turned on by the stock PIL before the SLPI
  boots, only consumer: always-on in our DT. SSC pin state gpio67 (stock `proxy_int_default`).
- Registry: the stock SLPI built `/mnt/vendor/persist/sensors/registry/registry` (187 files, factory
  calibration) from the **MTP** json set (kona_lsm6dso_0_0: orient x=-y, y=+x, z=+z); it records the
  config mtimes (1230735600): kept on the served configs so it is reused, not regenerated.
- Firmware: `tools/extract-dsp.py slpi BL_….tar.md5 build/firmware-slpi` -> slpi.mbn (7442656 bytes,
  sha256 9c34820f81434ab9, 22 phdrs), slpir.jsn, slpius.jsn (in-kernel pd-mapper has
  msm/slpi/{root,sensor}_pd for sm8250). Tree: `tools/build-hexagonfs.sh` (260 files) ->
  `build/hexagonfs-gts7xl`, installed by `tools/install-sensors.sh` into
  /usr/share/qcom/sm8250/Samsung/gts7xl (hexagonrpcd guesses that path from model + compatible),
  registry under /var/lib/hexagonrpcd/sensors-registry (writable by user fastrpc).
- hexagonrpcd: not in ALARM; `arch/hexagonrpcd` PKGBUILD (upstream da7a374, sdsp-only unit as user
  fastrpc); a hand build is on the tablet in ~/src/hexagonrpc/out/hexagonrpcd.
- iio-sensor-proxy 3.9 tags fastrpc-sdsp only as ssc-light/ssc-compass: the device rule
  `79-gts7xl-sensors.rules` adds ssc-accel + an identity ACCEL_MOUNT_MATRIX (check rotation).

Hall sensors (vendor hall_ic.c, hall_ic_wacom.c): gpio157 book cover -> SW_LID, gpio110 digitizer
cover -> SW_MACHINE_COVER, both low = magnet, 15 ms debounce, no wakeup. logind
`HandleLidSwitch*=ignore` (no suspend support yet; GNOME still blanks on lid close).

S Pen (Wacom W9021, stock `wacom,w90xx` @0x56 on QUP SE17, fw 0x403d in the chip): Samsung's own
I2C protocol, not mainline wacom_i2c's: query = plain 31-byte read (block at offset 16, header
0x0f), 0x31 = start sampling, 17-byte packets (type 1: in-range/eraser/side/tip bits, x/y BE16,
12-bit pressure, height, tilt). New driver `wacom_w90xx` (linux a23fbc2da, syntax-checked with
clang against the kernel headers, not linked: no aarch64 linker on the host), DT 28ecdbb12: i2c17 +
GPI DMA2 (stock EE 0x6000), irq gpio136 level low, fwe gpio6 low, supply = stock fixed 3.3 V switch
on gpio93 (boot-on in stock). Axes: stock = y inverted then x/y swapped into Android's portrait
frame, which our touchscreen props undo, so the raw chip frame is the panel's landscape frame
(22656 x 14160): no transform in DT. Not done: pen-in-garage (`SW_PEN_INSERTED`, stock reports it
inverted from the garage notifications), BLE.
S Pen BLE (Air actions): separate radio in the pen, Samsung-proprietary GATT service, charged
through the digitizer coil when docked; the digitizer has BLE-charge commands 0xE8-0xEF (stock log
"ble_mode(0xed)" = keep off). Pairing is driven by the Samsung app. Feasible only as a reverse
engineering project; not touched.

Cameras (stock cam-sensor nodes + camx module bins in vendor.img):
| role | sensor | CCI / addr (7-bit) | CSIPHY | MCLK | reset | supplies (enable GPIOs) | mainline |
|---|---|---|---|---|---|---|---|
| rear wide 13 MP | Samsung S5K3M5 | CCI0 m0 / 0x2d | 0, 4 lanes | gpio94, 19.2 MHz | gpio73 | VANA gpio39 (also AF), VIO gpio37 | driver s5k3m5 (24 MHz tables only) |
| rear UW 5 MP | Samsung S5K5E9 | CCI1 m0 / 0x10 | 2 | gpio95 | gpio78 | VANA gpio42, VIO gpio37 | no driver |
| front 8 MP | Samsung S5K4HA | CCI0 m1 / 0x2d | 3 | gpio96 | gpio30 | VANA gpio38, VIO gpio37 | no driver |
Rear AF actuator 0x0c and EEPROMs 0x58/0x51/0x50 on CCI1. All rails are external switches
enabled by GPIOs (no PMIC voltage set by the SoC). Stock power-up (camx module): VIO, 1 ms, VANA,
1 ms, reset, 1 ms, MCLK, 8 ms. Test tree `sm8250-samsung-gts7xl-rearcam.dtb` (linux 0a3ecd58b,
never booted): CAMSS CSIPHY0 + CCI0 + S5K3M5 at 24 MHz MCLK, link 602.5 MHz.
Fingerprint: Goodix GW9558 optical under-display on SPI7, owned by TrustZone (Samsung TA): not
feasible on mainline. Grip/SAR: A96T3X6 x2 on GPIO-bitbanged I2C (not needed).

Sources: linux `gts7xl-sensors` 9bdfaddc0 (SLPI + hall), 0a3ecd58b (rear camera DTB), a23fbc2da
(wacom_w90xx), 28ecdbb12 (S Pen DT); pmaports `gts7xl-sensors` a9cfc19e1 (on r21: patches
0033-0036, S5K3M5=m, TOUCHSCREEN_WACOM_W90XX=m, pkgrel left to the integration).

## 2026-11-17/18 night — audio: crackle measurements, TDM loopback, speaker protection prepared (no flash)

Owner feedback on Omarchy (BOOT r20): slight crackle; bass saturating at high volume before the
"Speakers (protected)" filter (Android: Cirrus protection + Dolby). Everything below was done
without audible sound (muted amps or -60 dBFS), under the tablet lock.

Crackle, measured:
- PipeWire on r20: device node `alsa_output.platform-sound.HiFi__Speaker__sink` S16LE 48 kHz,
  quantum 1024, ALSA period 480 / buffer 3840 (MMAP, batch). pw-top device ERR 0 over every run,
  also with 8 busy CPU loops; one client (pw-play) showed ERR 8 once under that synthetic load, 0
  in three repeats (latency 1024/2048/4096). Daemons run SCHED_RR 20 (rtkit), kernel PREEMPT, HZ 250.
- Amp settings read back (regmap): HW noise gate off (NG_CFG 0x33, select 0), DSP noise gates
  off, DRE off, soft ramp off, gain ZC off, analog gain 6 (0xc0), digital 0 dB, class-H boost
  (VCTRL2 0x1), boost coefficients = stock.
- **TDM bus bit-exact** (test kernel r41, branch `gts7xl-audio-sense`: Primary TDM TX capture link):
  silent loopback (all amps Digital PCM Volume 0 = mute, analog minimum, "ASP TX1 Source" =
  ASPRX1, ASP TX2-4 = Zero, full-scale random noise on MultiMedia1, capture MultiMedia3):
  NB_NF (r20 setting): Top Right slot 100.000 % identical over 198000 frames; Top Left slot
  identical except its MSB, always 0 (first bit of the frame on the amp's transmit side; a wrong
  received MSB would be gross distortion, not heard). IB_NF (stock-like codec edge, via the debug
  parameter `snd_soc_sm8250.pri_tdm_codec_ib=1`): every bit wrong. So the r20 edge is right and
  the playback data reaches the amps intact. Tools: `tools/tdm-loopback-test.sh`,
  `tools/tdm-loopback-compare.py`. Note: a first run without ASP TX2-4 = Zero had several amps
  driving the same TX slots for ~9 s (default slot layout); the capture link must stay out of the
  main line until UCM/driver set those sources.
- Not found yet: device xruns, bus errors, gating. Remaining suspects (need sound, owner present):
  speaker over-excursion at high level (no protection), class-H/boost transitions, content.
  Next step: IMON/VMON capture during quiet music (ASP TX1/2 = IMON/VMON on the sense link) to
  see current clipping or boost dips.

Speaker protection (Samsung CSPL), prepared and checked silently:
- Firmware: vendor `/firmware/cs35l40-spk-dsp1-spk-prot.wmfw` (CSPL, Jan 2020, algorithms 0xcd
  "CSPL" and 0x400a4 "VIMON") + `cs35l40-spk-dsp1-spk-prot.bin` (TAB_S7P_SPKPV2_PPP_20200602,
  coefficients only). Mainline wm_adsp loads them as `cirrus/cs35l41-dsp1-spk-prot.wmfw/.bin`
  (generic name, no subsystem id needed): "DSP1: Firmware: 400a4 vendor: 0x2 v0.0.1",
  "Protection: C:\SPbin\TAB_S7P_SPKPV2_PPP_20200602.bin". Installed on the tablet only (Samsung
  files, never in git). Controls per amp: "<Amp> DSP1 Protection cd CAL_R/CAL_AMBIENT/CAL_STATUS/
  CAL_CHECKSUM/CAL_SET_STATUS/CSPL_STATE/...", "... 400a4 VIMON_CAL/VSC/ISC/HALO_STATE".
- Factory calibration: sec_efs `/cirrus/{rdc,vsc,isc}_cal<suffix>` + `temp_cal` (read only from
  the EFS backup and, on the tablet, from /dev/disk/by-partlabel/sec_efs with debugfs; values stay
  on the device). Suffix map (stock cirrus,mfd-suffix): "" 0x41 Top Left, "_r" 0x40 Bottom Left,
  "_b" 0x43 Top Right, "_br" 0x42 Bottom Right. RDC values ~6.5 ohm each, VIMON present.
  `tools/gts7xl-amp-cal.sh` writes them like the stock cirrus_cal_apply (CAL_R, CAL_AMBIENT,
  CAL_STATUS 1, CAL_CHECKSUM R+1, VIMON_CAL 2 + VSC/ISC); the controls are volatile, so it must
  run while the DSP runs.
- Silent run on r20 (amps muted, digital silence, 14 s): firmware on all four, PCM Source DSP,
  calibration written: HALO_STATE 2, CSPL_ENABLE 1, CAL_SET_STATUS 1, VIMON_CAL 2 read back on
  the amps that answered; cs35l41 interrupts 0. At stop, mainline's mailbox PAUSE failed on two
  amps ("Failed to set mailbox cmd 1 (status 0)", PRE_PMD -42): this 2020 firmware does not answer
  the mailbox protocol the driver expects; the amps went back to ASP/no firmware normally. Some
  reads came back empty (control read during state changes).
- Not enabled. Open before using it: mailbox mismatch (pause/resume), when the calibration must
  be written (vendor: right after firmware start; userspace can only do it once running), whether
  CSPL actually limits (CSPL_STATE 0 in that run), then a listening test with the owner at low
  level with protection on, read CSPL_TEMPERATURE/REDUCE_POWER while playing.

Mics / USB-C headset (investigated only):
- Mics: stock DMICs on the LPASS VA macro, LPI gpio6/7 (DMIC0/1, `dmic01_active` in sm8250.dtsi)
  and gpio8/9 (DMIC2/3), 600 kHz (va-dmic-sample-rate 0x927c0), stock routing "VA DMIC0..3".
  Mainline precedent: qrb5165-rb5 (`&vamacro` + "VA Capture" link VA_CODEC_DMA_TX_0). Needs: enable
  vamacro (vdd-micb supply from the stock tree), dmic23 pin state, capture link + UCM.
- USB-C headset: stock has `audio,no-earjack` and the MAX77705 MUIC "detect-alalog-audio"; the
  WCD938x is disabled in the stock tree. Digital USB-C dongles need USB host mode (see
  docs/usb-dual-role-design.md) and then work with snd-usb-audio; analog accessory mode is not
  wired to a codec here.

### 2026-11-17 night — sensors, S Pen, rear camera: kexec results (root through the tablet's passwordless sudo)

- **SLPI / accelerometer: works** (kexec r21 Image + sensors DTB, 23:10-23:20; again on r50).
  slpi remoteproc running, /dev/fastrpc-sdsp (group fastrpc), hexagonrpcd up, `ssccli --sensor
  accelerometer` steady (x 4.1, y -0.3, z 8.9 m/s², tablet resting tilted), magnetometer reads,
  iio-sensor-proxy HasAccelerometer=true. Two fixes were needed: (1) serving the stock json
  configs makes the SLPI parse them and then ask the host for a "sns_registry" write interface
  hexagonrpcd lacks -> session dies (restart loop); now only the registry is served (configs kept
  as sensors/config.stock, unserved); (2) the SLPI reads `registry/../sns_reg_version` and Samsung's
  `/sys/class/sensors/ssc_core/ssc_hw_rev`: hexagonrpcd patch (arch/hexagonrpcd/0001-…, local
  branch gts7xl-samsung of linux-msm/hexagonrpc). `ambient_light`: not provided by this SLPI (light
  sensors are "ambient_light_v"/"light_cct_v" in the stock list); no light in GNOME. Rotation
  direction not checked (needs hands). Hall: "Hall sensors" input with SW_LID + SW_MACHINE_COVER,
  irqs 157/110 bound, both open.
- **S Pen: probes** (r50): `wacom-w90xx 17-0056: fw 0x403d, mpu 0x45, bl 0x03, max 26712x16714,
  pressure 4095, tilt 63, height 255`; input "Wacom W90xx pen" ABS X 0-26712, Y 0-16714 (stock has no
  use_dt_coord: the DT max_coords 22656x14160 are unused, ranges now from the query). No pen
  event seen (nobody to hold the pen).
- **Rear camera: probes and identifies** (r50, rearcam DTB): s5k3m5 20-002d at the stock 19.2 MHz
  MCLK (patch 0037: probe/identify at 19.2 MHz, streaming refused), chip id read, CAMSS media0 +
  subdevs + video nodes; libcamera 0.7.2 (installed from the ALARM repo) `cam -l`: "Internal back
  camera (/base/soc@0/cci@ac4f000/i2c-bus@0/camera@2d)". No stream.
- **Incident, fixed:** `linux-modules-cleanup.service` (kernel-modules-hook) moves every
  /usr/lib/modules/<rel> not owned by pacman and not the running kernel to .old and deletes it:
  booting r21/r50 by kexec removed 7.3.4-r20 (BOOT) and 7.3.4 (RECOVERY), so r20 came up without
  Wi-Fi/BT/audio (23:32). Restored from the r20 apk and the r14 module tree, cleanup masked on the
  tablet (and in arch/gts7xl-device/install.sh, 15db24a). Verified: r20 back with wlp1s0, hci0,
  speakers; module dirs 7.3.4, -r20, -r21, -r50 survive reboots. (The GPU agent's earlier r21 test
  likely triggered the same; any image without the mask will repeat it.)
- r50 apk (sha256 533cc2e3a3d99143, pmaports gts7xl-sensors 0033-0039, pkgrel 50) copied to
  build/sensors-k50/ and moved out of the pmbootstrap repo to packages-aside (+ `pmbootstrap index`,
  in a private mount namespace) so nothing installs it by accident. Tablet keeps
  /usr/lib/modules/7.3.4-r50 (outside pacman), hexagonrpcd in /usr/local/bin, units/rules in /etc,
  libcamera + libcamera-tools installed, /root/sensors-config.aside (stock json, unserved).

## 2026-11-18T06:57:01+07:00 flash
- BOOT: fbb8aa1401e3c2c0f86d74f22c5ca37d0b0648011dfc4cd396726516f2401343 build/archive/boot-shim-r21-fbb8aa14.img

### 2026-11-18 morning — owner test of r50 and fixes (r51, kexec-tested, not flashed)

Owner (r50 from BOOT r21): S Pen did nothing in GNOME, rotation wrong. Causes and fixes:
- **ADSP FastRPC flood** (~70000 `qcom_scm: Assign memory protection call failed -22` + fastrpc probe
  -22 per boot): every **kexec'd** kernel (also the r21/r41 tests of the other agents) — the ADSP
  remote heap still belongs to the LPASS VMs from the previous kernel, the probe's SCM assign fails
  and the channel re-probes in a loop; real boots are clean. It also left systemd-udevd unresponsive
  (`udevadm control --reload`: "Timer expired"), which most likely hid the pen from libinput/GNOME and
  broke the hexagonrpcd start. Fix: DTS drops `memory-region`/`qcom,vmids` from the ADSP fastrpc node
  (linux 0002 of extra3, aport 0041). r51 kexec: 0 SCM errors.
- **hexagonrpcd not running**: `ConditionPathExists=/dev/fastrpc-sdsp` is checked before the SLPI is
  up. Fix: udev starts it when the node appears (`80-fastrpc.rules` SYSTEMD_WANTS). r51: active.
- **Rotation**: owner held it in the panel's landscape: SSC x = +8.8, y = -0.2, z = +3.9 m/s².
  iio-sensor-proxy calls "normal" y = -g, so `ACCEL_MOUNT_MATRIX=0, 1, 0; -1, 0, 0; 0, 0, 1`.
  r51 with the same pose: "orientation: normal".
- **S Pen**: on the r50 boot after the owner's test the pen IRQ had fired 410 times (events were
  produced). r51 driver also power-cycles the chip at probe (stock reset: off 100 ms, on 200 ms),
  sends survey-exit (0x2d) before start (0x31), sets X/Y resolution 100 units/mm, logs
  non-coordinate packets (after probe: one notification `0d 00 10 2d 10 03 …`, the survey-exit
  reply). Pen strokes not yet seen by an agent (needs hands).
r51 apk: build/sensors-k50/linux-samsung-gts7xl-7.3.4-r51.apk (sha256 ef1758a163e8e3db, pmaports
gts7xl-sensors pkgrel 51, 0033-0041), out of the pmbootstrap repo. Rules updated live on the tablet
(/etc/udev/rules.d/79-gts7xl-sensors.rules, 80-fastrpc.rules).

## 2026-11-18 — r22: r21 + sensors, hall, S Pen, ADSP FastRPC kexec fix (kexec-tested from r21, not flashed yet)

Owner after the r51 test: S Pen and rotation work (confirmed by the owner; the agent's capture
windows missed it: re-check pen IRQ counts and the four orientations with logs on the next boot).
linux `gts7xl` fast-forwarded from `gts7xl-sensors` (top = 2f8d5bf0d, the ADSP FastRPC DT fix);
pmaports `gts7xl` fast-forwarded from `gts7xl-sensors` + cde68e940 (pkgrel 22): patches 0033-0041,
TOUCHSCREEN_WACOM_W90XX=m, VIDEO_S5K3M5=m. Release **7.3.4-r22**. Images: `apk add -u` in the rootfs
chroot (initramfs with 7.3.4-r22 modules), `pmbootstrap export build/`,
`tools/build-recovery-shim.sh --cmdline-from build/archive/boot-shim-r21-fbb8aa14.img` (same cmdline,
md5 checked). All pmbootstrap calls in `sudo unshare --mount --propagation private`.

| File | sha256 |
|---|---|
| `build/archive/boot-shim-r22-987296de.img` (BOOT) | `987296dede7a9bc022db124a4509b41df8a42de781d4dd8e68dd067e74c481a0` |
| `build/archive/recovery-shim-r22-c9b40d46.img` (RECOVERY, not to flash) | `c9b40d465905dccb…` |
| `build/sensors-k50/linux-samsung-gts7xl-7.3.4-r22.apk` | (same as the pmbootstrap repo) |

**ADSP FastRPC DT change (audio agent):** `&adsp { glink-edge { fastrpc { /delete-property/
memory-region; /delete-property/ qcom,vmids; }; }; }` — the kexec'd-kernel SCM assign loop.

Kexec test from r21 (build/sensors-k50-test-075738, BOOT DTB): 7.3.4-r22; S Pen probes (fw 0x403d,
26712x16714); slpi + adsp running, hexagonrpcd + iio-sensor-proxy active, accelerometer reads,
orientation "normal" in the usual pose; Hall sensors input; 0 SCM assign errors, 0 BTF; charger
safety-monitor line, [SDP], 475000; wlp1s0 connected; hci0 same address; ADSP + GMU (2); speakers
sink + protection filter present; back on r21.

Omarchy on the tablet: `linux-gts7xl 7.3.4.r22-1` (pkg build/omarchy/pkg-r22, BOOT image
987296de, hook dry run OK: BOOT=/dev/sda23, WRITE_BOOT=no), module dirs 7.3.4, -r20, -r21, -r22
(r21 preserved across the upgrade, linux-modules-cleanup masked; r50/r51 test dirs removed);
`hexagonrpcd 0.5.0.r20.gda7a374-1` (built on the tablet from arch/hexagonrpcd, Samsung paths patch,
sdsp unit as user fastrpc, udev start); the hand-installed test copies removed. Image build:
tools/build-omarchy-rootfs.sh installs the hexagonrpcd package + tools/install-sensors.sh.
Flash waiter (scratchpad flash-r22-wait.sh) armed for Download Mode, 90 min.

    printf 'FLASH\n' | FLASH_SSH="ssh localhost" tools/flash.sh --pit build/gts7xl.pit --keep-vbmeta \
        BOOT=build/archive/boot-shim-r22-987296de.img

## 2026-11-18T08:03:32+07:00 flash
- BOOT: 987296dede7a9bc022db124a4509b41df8a42de781d4dd8e68dd067e74c481a0 build/archive/boot-shim-r22-987296de.img

## 2026-11-18T08:03:32+07:00 flash
- BOOT: 987296dede7a9bc022db124a4509b41df8a42de781d4dd8e68dd067e74c481a0 build/archive/boot-shim-r22-987296de.img
- heimdall upload OK (flash exit 0). The tablet did NOT come back on USB (no USB device at all)
  or Wi-Fi within 12 min (checked until 08:15): owner to look at the screen.

## 2026-11-18 — r23: 1.5 A charge current on a wall charger (kexec-tested from r22, not flashed)

Owner ("Oui, 1,5 A"): on the 100 W USB-PD wall charger (no PD contract, 5 V, BC1.2 DCP, input
1800 mA) the 450 mA charge current was far too slow. Change: the fast-charge current now follows
the cable like the input limit. Only a positively detected DCP (VBUS + CHGTYP DCP in BC_STATUS)
gives `maxim,dcp-constant-charge-current-microamp` = 1500 mA; SDP, CDP, unknown types, no VBUS
and read errors keep the battery's 450 mA. The selected value is the safety monitor's reference
(written on a cable change, otherwise "at or under" is enforced and rewritten). Driver ceiling
1500 mA (`MAX77705_CC_DCP_CEIL_UA`; a larger DT value is dropped with a warning).

Stock, for the record: a Samsung TA is cable 3 (`SEC_BATTERY_CABLE_TA`), in none of the
cable-info current groups, so it gets `default_input_current` 0x708 = 1800 mA and
`default_charging_current` 0x834 = 2100 mA (reference/stock-overlay-01-id0-rev0.dts, cable-info;
vendor battery_v2/sec_battery_dt.c). Battery `max_charging_current` 0xc4e = 3150 mA.
1500 mA <= 2100 mA. Every other limit unchanged: CV 4.27 V (reg 0x0b), battery 2..41 C,
10 h timer (at 1.5 A an 80 % charge of 10090 mAh takes < 6 h), 80/75 % cap, watchdog, B1 off
path (MODE 0x04 + CHG_EN 0).

linux 58cee566c (driver + binding), 7bb5de6f5 (DTS) = aport patches 0042-0043, pkgrel 23,
release **7.3.4-r23**. Tests: tests/test_kernel_charger.py (DCP charge current only on positive
detection, ceiling, reference before the limit check), DTS value <= 1500000 <= stock 2100 mA.

| File | sha256 |
|---|---|
| `build/archive/boot-shim-r23-657ade6d.img` (BOOT) | `657ade6d5cd92de0bd3c314d6f615ec44a07f1dd118d109ac1cce62ad83e6acd` |
| `build/archive/recovery-shim-r23-c973b026.img` (RECOVERY, not to flash) | `c973b026b5e3a42939241453557d4dc1173c267a34d0ee5b95b376f2728a6660` |
| `build/charge-r23/linux-samsung-gts7xl-7.3.4-r23.apk` | `eed9a346a64e4b02a8aa6c04a189a1cbce53b4206f80e3be1d14df3976e0df1c` |

BOOT image: `apk add -u` in the rootfs chroot, `pmbootstrap export`,
`tools/build-recovery-shim.sh --cmdline-from build/archive/boot-shim-r22-987296de.img` (cmdline
md5 identical to r22). All pmbootstrap calls in `sudo unshare --mount --propagation private`.
Omarchy: `linux-gts7xl 7.3.4.r23-1` installed (build/omarchy/pkg-r23, hook dry run, WRITE_BOOT=no:
BOOT not written). The upgrade removed the r22 package's 7.3.4-r22 module dir: it was copied
aside before and put back (depmod), so 7.3.4, -r20, -r21, -r22 (outside pacman) and -r23 exist.

Kexec test from r22 over Wi-Fi, tablet on the wall charger, screen backlight 0
(tools/charge-dcp-test.sh, build/charge-dcp-test-082056):
- `safety monitor: CC 450000 uA (DCP 1500000 uA), CHGIN 475000 uA (DCP 1800000 uA), CV reg 0xb,
  battery 2..41 C, timer 36000 s, capacity 75..80 %`, then `input limit 1800000 uA (USB type 2)`
  and `charge current 1500000 uA (USB type 2)`.
- CNFG_02 (0xB9) = 0x5e: CC field 0x1e = 1500 mA, read back the whole time; CNFG_09 0xc7
  (CHG_EN, 1800 mA), DTLS_01 0x31 (CC), health Good.
- 10 min, 40 samples: battery current mean +1.12 A (instant 0.86..1.25 A), FG average +1.24 A;
  capacity 15 -> 17 %; battery 28.3 -> 30.1 C. Before (r22, 450 mA): +0.45..0.47 A.
- inhibit-charge: CNFG_00 0x14, DTLS_01 0x38 (off), battery -20..+23 mA, "Not charging";
  auto again: +1.16 A within 10 s.
- Reboot to BOOT: 7.3.4-r22, CC 450000, charging +0.47 A, Wi-Fi connected, hci0, no failed units.

Why ~1.2 A and not 1.4 A: CC is set to 1500 mA but the input side is capped at 1800 mA x ~5 V
(~9 W) and also feeds the running system; AICL is not active (CHG_INT_OK 0xdf, AICL_OK set).
The charger's USB-C block reports the wall charger's Type-C advertisement CC_STATUS0 (0x0A) =
0x71: CCIStat 3 = **Rp 3.0 A**, sink, CC1. Honouring it (step 2, below) is what raises input.

Wi-Fi MAC: the QCA6390 address changes at each boot, so the DHCP address moved (.195, .196, .197
during this test; the test script now finds the tablet by mDNS, `poubelle.local`). Pinned in the
tablet's NetworkManager connection (cloned MAC = the MAC of the router's static lease), back on the
static lease afterwards. Image build: `GTS7XL_WIFI_MAC` (local setting, build/omarchy/local-settings.env,
not in git) makes arch/gts7xl-device/install.sh write
`/etc/NetworkManager/conf.d/50-gts7xl-wifi-mac.conf` for wlp1s0.

## 2026-11-18 — r24: input limit from the Type-C current advertisement (kexec-tested from r22, not flashed)

Owner: "étape 1 puis la 2". On top of r23. The charger also reads CC_STATUS0 of the USB-C block
(0x25 reg 0x0A; read only, unclaimed, like BC_STATUS; vendor ccic/max77705_cc.c): bits 2:0
CCStat must be 1 (sink), bits 5:4 CCIStat give the source's advertisement (2 = 1.5 A, 3 = 3.0 A).
Only with VBUS present (BC_STATUS bit 7). Input limit = max(BC1.2 rule, Type-C rule):
Rp 3.0 A -> `maxim,typec-3000ma-input-current-limit-microamp` 3000 mA, Rp 1.5 A ->
`maxim,typec-1500ma-input-current-limit-microamp` 1400 mA (so a detected DCP's 1800 is never
lowered); default Rp, not a sink, no VBUS or a read error: the BC1.2 value. Driver ceilings
1.4 A / 3.0 A (a larger DT value is dropped). Stock: `battery,rp_current_rp2` 0x578 = 1400 mA,
`rp_current_rp3` 0xbb8 = 3000 mA (sec_battery.c sec_bat_set_rp_current: input rp2/rp3, charge
rp2 = 1400 / battery max 3150). Charge current unchanged: 1500 mA only on BC1.2 DCP, 450 mA
otherwise, also with Rp 1.5/3 A (stock would allow 1400/3150 there; kept conservative). Bounded
AICL and the "at or under the reference" check unchanged; the register reference follows the
cable and the advertisement (written on a change).
New read-only ADC channel: PM8150L AMUX THM3 (0x4f) "chg_therm", the stock battery's
`adc-chg-temp`, for monitoring (`in_temp_chg_therm_input`); not used by the safety logic yet.

linux 7173fdcd7 (driver + binding), 8cc2c9ff3 (DTS) = aport patches 0044-0045, pkgrel 24,
release **7.3.4-r24**. Tests: Type-C read only, sink only, max() with the BC1.2 value, ceilings,
charge current independent of Type-C; DTS values <= stock rp2/rp3 and <= the 3200 mA register max.

| File | sha256 |
|---|---|
| `build/archive/boot-shim-r24-e6d92efb.img` (BOOT) | `e6d92efbaff094194ade69be0e8359a9415c650bdbcb1e73e99896da82d1651f` |
| `build/archive/recovery-shim-r24-aecaadb3.img` (RECOVERY, not to flash) | `aecaadb38e91844310ffd8a24b7c308caf1318795629b8e42a6dcac1f7961818` |
| `build/charge-r24/linux-samsung-gts7xl-7.3.4-r24.apk` | `285fe728ecf62303b88768f10460d0b32282ffe660b681306e2627b11045fc99` |

Cmdline md5 identical to r22. Omarchy: `linux-gts7xl 7.3.4.r24-1` (hook dry run, BOOT not
written); the upgrade removed 7.3.4-r23 (owned by the r23 package): put back from a copy, so
7.3.4, -r20, -r21, -r22, -r23 (outside pacman) and -r24 exist.

Kexec test from r22 over Wi-Fi (.166, MAC pinned), wall charger, backlight 0
(build/charge-dcp-test-084153):
- `safety monitor: CC 450000 uA (DCP 1500000 uA), CHGIN 475000 uA (DCP 1800000 uA, Type-C 1.5/3 A
  1400000/3000000 uA), ...`, `input limit 3000000 uA (USB type 2, Type-C 3000 mA)`,
  `charge current 1500000 uA (USB type 2)`.
- CNFG_09 (0xC0) = 0xf7: CHGIN_LIM 0x77 = 3000 mA, CHG_EN; CNFG_02 0x5e (1500 mA); CC_STATUS0
  0x71 (sink, Rp 3.0 A); CHG_INT_OK 0xdf (AICL not active); DTLS_01 0x31 (CC); health Good.
- 10 min, 40 samples: battery +1.48 A mean (1.44..1.51 A), FG average +1.48 A; capacity 18 -> 21 %;
  battery 30.9 -> 31.7 C; charger thermistor 37.6..38.0 C (steady).
- inhibit-charge: CNFG_00 0x14, CNFG_09 0x77 (CHG_EN 0), DTLS_01 0x38, battery -8..+16 mA,
  "Not charging"; auto: +1.48 A within 10 s.
- Reboot to BOOT: 7.3.4-r22, 450 mA / 1800 mA, charging +0.48 A, Wi-Fi .166, hci0, no failed units.

## 2026-11-18T21:46:17+07:00 flash
- BOOT: e6d92efbaff094194ade69be0e8359a9415c650bdbcb1e73e99896da82d1651f build/archive/boot-shim-r24-e6d92efb.img

## 2026-11-18 — Omarchy package state repaired (tablet "poubelle", BOOT r24)

Symptom: `pacman -S base-devel rust nodejs npm` failed (targets not found, then openssl 4.1.0
breaking libssl.so=3 users). Cause: the sync databases on the tablet were the live Arch Linux ARM
ones of 2026-11-17 (core/extra with openssl 4.1.0, aquamarine 0.16, rust 1.100), left from the image
build (the first setup runs had the live ALARM mirror); the configured Omarchy stable mirror
(arm-stable-mirror.omarchy.org, snapshot of 2026-10-20, openssl 3.6.5) is older, so pacman never
replaced them (If-Modified-Since), and later installs (GNOME, Firefox, gstreamer, kmscon…) mixed in
newer packages. Fixed by forcing the stable databases and a full upgrade/downgrade to the snapshot:
`sudo env OMARCHY_ALLOW_DIRECT_PACMAN=1 pacman -Syyuu --ignore firefox` (Omarchy's hook refuses
direct -Syu without that variable). 29 packages: nodejs 26.12 + 3 deps added, 15 downgraded to the
snapshot (gstreamer family 1.28.8, webkitgtk-6.0 2.54.1, kmscon 10.0.4, libgdm, libical, bluez-obex,
imlib2, libshout, libgmobile, extension-manager 0.6.5, xdg-desktop-portal-gnome), Firefox 160 kept
(profile already used by 160). No kernel, boot loader or our packages touched (linux-gts7xl r24,
hexagonrpcd); module dirs 7.3.4, r20-r24 kept; no .pacnew; IgnorePkg, refusal hook, udev rules,
PipeWire/WirePlumber protection, write-boot dry run intact. `pacman -Dk` clean, `-Su` empty,
rust/nodejs/npm/base-devel resolve. Pacman's Landlock sandbox works on r24 (no --disable-sandbox).
Backup before: `build/backup-omarchy-20261118/` (root.tar.zst 5.3 GB, 232540 entries read back,
pacman -Q / -Qe lists; local only). After a reboot (BOOT r24): sudo, Wi-Fi, GNOME (gbm renderer on
the msm card, GMU loaded), default sink "Speakers (protected)", ADSP, charger safety monitor,
hexagonrpcd-sdsp and iio-sensor-proxy active, kmscon 10.0.4 on tty2 with font 28, 0 BTF errors,
no failed unit.
Rule from now on: install with `pacman -S` only after the databases match the channel (no mirror
fallbacks in /etc/pacman.d/mirrorlist); system updates through `omarchy update` (untested here:
it runs Omarchy's migrations) or the command above.
Build script fixed so a new image cannot ship them again: `tools/omarchy-pacman-sync.sh`
(`refresh_sync_dbs`, called at the end of `setup` and of `device`) refuses to run while the live
ALARM mirror is still in the mirrorlist, deletes every sync database, runs `pacman -Syy` against the
stable mirrors, removes stray databases (the build-only [offline] repo) and fails if an installed
package is newer than the snapshot (Firefox included) unless it is listed in `ALLOW_NEWER_PKGS`
(empty by default). The live ALARM mirror stays a download fallback for files the stable mirror
404s, same version only. Tests: tests/test_omarchy_pacman_sync.py. Not yet run in a full image build.

## 2026-11-18 — r25: USB dual role + VBUS output (OTG) — role tested by kexec, boost NOT enabled yet

Owner: USB OTG (host mode for a hub / devices). Design: docs/usb-dual-role-design.md. On top of r24.

**1. dwc3 dual role.** DTS `&usb_1_dwc3`: `dr_mode = "otg"`, `usb-role-switch`,
`role-switch-default-mode = "peripheral"` -> `/sys/class/usb_role/a600000.usb-role-switch/role`
(host / device / none). Device by default: gadget networking unchanged.

**2. Automatic role (read only).** The charger driver (it already reads the USB-C block 0x25,
unclaimed) polls CC_STATUS0 every 1 s; bits 2:0 CCStat (vendor max77705_cc.c: 0 none, 1 SINK =
the tablet is the sink of a PC/charger, 2 SOURCE = a sink is attached: OTG adapter/hub/keyboard,
3 audio, 4 debug, 5 error, 6 disabled). Debounced (2 equal reads): SOURCE -> host, anything else
-> device; read errors change nothing. The role is only written on a change of the debounced
state, so a manual `echo host > .../role` stays until the next attach change;
`usb_role_auto` (0/1, charger device sysfs) stops the automatic role. DT link:
`usb-role-switch = <&usb_1_dwc3>` on the charger node (looked up by the poll, so the charger
never waits for dwc3).

**3. VBUS output (OTG boost), written, OFF by default.** Charger device sysfs `otg_vbus`
(`off` default / `auto`; shows `(on)` / `(fault)`). With `auto` and a debounced SOURCE attach:
- gates, all before any register write: driver running, no latched fault, BC_STATUS no VBUS,
  CHG_INT_OK CHGIN_OK clear, CHGIN_DTLS == 0 (below UVLO: nothing on CHGIN), battery
  thermistor read OK and inside the charging window (2..41 C), fuel gauge read OK and capacity
  >= `maxim,otg-min-capacity-percent` (15 %);
- sequence (vendor max77705_set_otg): CHGPROT unlock, CHG_EN 0, CNFG_02 OTG_ILIM = 900 mA
  (stock MAX77705_OTG_ILIM_900), CNFG_00 MODE = 0x0a (OTG + boost; vendor
  MAX77705_MODE_A_BOOST_OTG_ON), read back MODE 0x0a + CHG_EN 0 + ILIM 900 + no BYP
  over-current, else off + fault;
- every poll (1 s) while on, before the debounce: CCStat still SOURCE, MODE/CHG_EN/ILIM as
  set, DTLS_02 BYP_DTLS bit 0 (vendor: "bypass overcurrent limit") clear, thermistor and
  capacity OK; BYP interrupt triggers an immediate poll; watchdog kicked only after this check;
- off = force_off (MODE 0x04, CHG_EN 0), MODE read back without the boost bit, retried 3x
  (dev_crit if it stays); the safety monitor re-evaluates charging right after;
- while on, the safety monitor and the AICL handler leave the charger alone (requeue only);
- off on: detach/any other CCStat, unreadable CC status, `otg_vbus = off`, fault, battery out
  of range, driver unbind (devm action, runs first), shutdown (`.shutdown`). Faults latch until
  the next detach (debounced non-SOURCE state).

### Failure modes (VBUS output), and what covers them

| # | Failure | Effect | Cover |
|---|---|---|---|
| F1 | Boost on while a charger/PC also drives VBUS (back-feed, two sources) | current into the boost, IC/port damage | gates BC VBUSDET, CHGIN_OK, CHGIN_DTLS == 0 before; a charger attach changes CCStat (SOURCE -> SINK/none) -> off within 1 s, no debounce |
| F2 | Charge and boost at once | undefined mode, battery current both ways | CHG_EN 0 before MODE 0x0a; read back CHG_EN 0 every poll; safety monitor does not run its on/off while boost_on |
| F3 | Over-current / short on VBUS | heat, battery drain | hardware OTG_ILIM 900 mA; BYP over-current bit -> off + latch; BYP IRQ -> immediate poll |
| F4 | Register write lost / I2C error | wrong mode | every write read back; any read error -> off; off retried 3x, dev_crit if the boost bit stays |
| F5 | Battery too hot/cold or empty while boosting | battery stress, brown-out | thermistor + capacity read every poll; out of range -> off + latch |
| F6 | Kernel hangs while boosting | boost stays on | not covered by the watchdog for sure: the charger watchdog is documented for charging; whether it stops the boost is unknown (to test or leave as residual risk); watchdog only kicked from a verified state |
| F7 | Detach not seen (USB-C firmware stuck, CC_STATUS0 stale) | VBUS on an empty port | VBUS on an open port is harmless (5 V, 900 mA limit); any unreadable read -> off; residual: firmware freeze with a stale SOURCE |
| F8 | Dock / hub with power passthrough (source to the tablet and sink downstream) | tablet stays device, no host | CCStat SINK -> device; needs PD DR_swap (not done, future PD driver) |
| F9 | Debounce lets a short glitch through | role flaps | 2 equal reads (1 s apart); boost goes off on the first non-SOURCE read (safe direction) |
| F10 | Manual role host while a PC is attached | gadget link lost | manual action; the next attach change sets device again |
| F11 | Driver unbind / shutdown / reboot with boost on | VBUS left on | devm action (first on unbind) and `.shutdown` switch it off; kexec goes through shutdown |
| F12 | Fault latch never released | no VBUS until replug | released on the next debounced non-SOURCE state (unplug) |
| F13 | Inrush at power-on trips BYP over-current | VBUS off, latch | stock-like; replug clears it; logged "over-current" |
| F14 | AICL handler lowers CHGIN_LIM during boost | slow charge after | AICL skipped while boost_on |
| F15 | Wrong CCStat meaning on this firmware | host/boost with a charger | checked on hardware: wall charger reads CCStat 1 (SINK); SOURCE seen only with the owner's OTG adapter (to verify before enabling boost) |

linux 96ffbb332 (driver + binding), 65e1d2707 (DTS) = aport patches 0046-0047, pkgrel 25,
release **7.3.4-r25**. Tests: tests/test_kernel_charger.py (one MODE 0x0a write, every gate
before it, CHG_EN 0 first, 900 mA only, read back; default off; no-input check; monitor and
off paths incl. unbind/shutdown; safety monitor and AICL idle while boosting; debounced role,
boost off before the device role; DTS device default).

| File | sha256 |
|---|---|
| `build/archive/boot-shim-r25-4989be10.img` (BOOT) | `4989be1020e4fe9304a39d41917db9315efaa1de55a30d668cf9538fab2e66ba` |
| `build/archive/recovery-shim-r25-823e090b.img` (RECOVERY, not to flash) | `823e090b31ceb4c6bbef6b6380d3e9fa5487740a7aeca82b9940686ab4727375` |
| `build/otg-r25/linux-samsung-gts7xl-7.3.4-r25.apk` | `290c655b2a3f9e612a59caff98dd8f44023eef78883bf7ccb0558d07a367a499` |

Cmdline md5 identical to r22. Omarchy `linux-gts7xl 7.3.4.r25-1` (hook dry run, BOOT not
written); module dirs 7.3.4, -r20 .. -r25 all present (r24 put back after the upgrade).

Kexec test from r24 (tools/otg-role-test.sh, build/otg-role-test-225057), nothing plugged into
the USB-C port (CC_STATUS0 0x00, on battery), boost never enabled:
- `USB-C: data role from CC status, VBUS output off until enabled (900 mA, capacity >= 15 %)`,
  `USB role device (CC status 0)`; role `device`, `usb_role_auto` 1, `otg_vbus` `off`.
- `echo host`: xhci-hcd registers usb1 (HS) + usb2 (SS root hub), UDC gone; 6 s later still
  host (the automatic role does not undo a manual one); CNFG_00 0x15, CNFG_02 0x49 unchanged
  (no boost, OTG_ILIM bits 0).
- `echo device`: xhci removed, UDC a600000.usb back, configfs gadget g1 bound again (`not
  attached`: no PC cable during the test, so the gadget data link itself was not exercised).
- Back on r24 (BOOT), Wi-Fi up, no failed units.
- Wall charger attach (CCStat 1, SINK) was read in the r23/r24 tests (CC_STATUS0 0x71): device.

Not done yet (owner needed): host with a real device through an OTG adapter, a CCStat SOURCE
reading on this firmware (F15), the boost itself, the PC gadget link after a role round trip.

r25 hands-on (owner present, kexec from r24, build/otg-role-test-225829): OTG adapter (USB-C
plug -> USB-A) with a USB keyboard, no charger. CC_STATUS0 = 0x40 three reads in a row: CCPinStat
1 (something on CC1) but **CCStat 0 (no connection)**, BC_STATUS 0x01 (no VBUS), so the role
stayed device and the VBUS output was never switched on (by design: it needs CCStat SOURCE).
The MAX77705 USB-C firmware does not present Rp / attach as source by itself: stock configures it
at boot through the opcode mailbox (vendor max77705_usbc.c), our kernel only reads it. So the
boost is unreachable until that configuration is done (writes to the USB-C firmware: separate
design, needs the owner's approval). Host mode with a self-powered hub (manual role) untested:
no powered hub. Script stopped before its boost step; back on r24 (uname r24, no failed units,
Wi-Fi up, charger safety monitor up). r25 not flashed.

## 2026-11-18 — Waydroid on Omarchy (tablet "poubelle", BOOT r24)

Installed from the stable repos: waydroid 1.6.3, lxc 7.0.0, python-gbinder 1.3.1, dnsmasq (plus
strace for debugging). Images: official LineageOS 20 arm64 GAPPS system (2026-09-27) + MAINLINE
vendor (2026-10-22) through `waydroid init -f -s GAPPS`; waydroid checks each zip's sha256
against the OTA json (`Validating system image`). Static binder devices (no binderfs) work:
waydroid.cfg binder/vndbinder/hwbinder = the static /dev nodes, protocol aidl3.
Boot loop root cause: qemu-user-static-binfmt (installed with the Omarchy package set) registers
`qemu-arm` in binfmt_misc, so Waydroid's 32-bit vendor HALs (android.hardware.audio.service,
camera provider 2.7 external) ran under qemu-arm, which cannot pass binder ioctls
(BINDER_VERSION -> ENOTTY, "hw-ProcessState: Binder driver could not be opened"). audioserver
never found media.audio_policy and the system_server watchdog restarted it every ~2.5 min.
Fix: /etc/binfmt.d/qemu-{arm,armeb}-static.conf masked (comment only) and the two entries
unregistered (`echo -1 > /proc/sys/fs/binfmt_misc/qemu-arm`); the CPU runs AArch32 natively
(CONFIG_COMPAT=y). Boot completes in ~20 s. Device layer: arch/gts7xl-device installs the masks.
Network: ufw (INPUT/FORWARD drop) blocked the container's DHCP. Rules added (also in
gts7xl-firstboot for new images): `ufw allow in on waydroid0`, `ufw route allow in on waydroid0`,
`ufw route allow out on waydroid0`. Waydroid's own nft table does the NAT (masquerade
192.168.240.0/24). Container 192.168.240.112, Internet and DNS OK.
GPU: SurfaceFlinger GLES "freedreno, FD650, OpenGL ES 3.2 Mesa 26.0.8" (gralloc minigbm gbm,
egl mesa, vulkan freedreno). Audio HAL up, PulseAudio socket of the user session mapped
(playback not tested, owner's audio left alone). Multi-window: persist.waydroid.multi_windows
true. F-Droid 1.x official APK (PGP signature by the F-Droid release key 37D2C987...2E89, APK
signing cert SHA-256 43:23:8D:51...CC:AB) installed. Play Store present; device registration
for the uncertified-device page is done by the owner (Android ID not recorded here).
Kernel gaps for r26 (Android netd firewall rules fail; basic networking unaffected):
NETFILTER_XT_MATCH_{OWNER,BPF,CONNMARK,SOCKET,IPRANGE,QUOTA}, NETFILTER_XT_TARGET_{MARK,
CONNMARK,CT,IDLETIMER,NFLOG}, NETFILTER_XT_CONNMARK; the legacy iptable_*/ip6table_* modules
exist (=m) but are not loaded (the container cannot modprobe) -> load them via modules-load.d.
