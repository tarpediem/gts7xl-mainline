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

## 2026-11-17 — phase 0 review fixes (cmdline, 4K sectors, reproducible kernel) — not flashed

Supersedes the candidates of the entry below (those must not be flashed).

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
