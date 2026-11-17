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
- RECOVERY: 3754a375133ef1fb14f4baf2a7163802eda4ab872c037639423d4c8d9ea31c88 /home/tarpediem/Work/samsung/gts7xl-mainline/build/recovery-shim.img

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
