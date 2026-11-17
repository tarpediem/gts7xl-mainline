# Mainline Linux on Galaxy Tab S7+ 5G (gts7xl / SM-T976B) — design

Date: 2026-11-17. Status: approved in conversation, phases 0-4 detailed, 5-8 outlined.

## Goal

Run Omarchy (Arch Linux ARM + Hyprland) on the maintainer's Galaxy Tab S7+ **5G**
(SM-T976B, codename `gts7xl`, Snapdragon 865+ / SM8250), on a current mainline
kernel, usable **by touch only** (no Book Cover keyboard).

Route chosen: **postmarketOS for hardware bring-up, then Arch Linux ARM + Omarchy**.
The first win is a mainline kernel that boots and gives a shell.

## Context and constraints

- Bootloader already unlocked, Knox already tripped. Current OS: stock One UI 5
  (T976BXXS7DXH1) + Magisk. No security updates: **One UI is disposable**, Linux
  goes on internal storage.
- No fastboot on this tablet: every flash goes through **Heimdall** in Download Mode.
- Never written: bootloader partitions, EFS, modem/CP. Recovery path: stock
  firmware in `<stock-firmware>/`.
- Variant is **5G**, not Wi-Fi. Board IDs `<8 0>`..`<8 6>` and 5G-specific
  regulators; the Wi-Fi port's values must not be reused (the Droidian attempt
  of 2026-07 hung on the Samsung logo for exactly this reason).
- Droidian work in `<droidian-gts7xl>/` stays as reference
  (AVB signing tool, vbmeta-disabled image, decompiled downstream DTBs).

## Hardware (from the downstream device tree)

| Block | Part | Mainline status |
|---|---|---|
| SoC | SM8250 (kona) | supported (`sm8250.dtsi`, sm8250-mainline fork) |
| GPU | Adreno 650 | supported (msm DRM + Mesa Freedreno) |
| Storage | UFS | supported |
| Wi-Fi/BT | Qualcomm (ath11k) | supported, firmware needed |
| Charger/PD | MAX77705 | supported since 6.15 |
| Audio amp | Cirrus CS35L41 | driver exists; UCM work needed |
| Display | Samsung OLED WQXGA, DSI (S6TUUM/ANA38401 family) | **panel driver to write** |
| Touch | STM FTS (`stm,fts_touch`) | `stmfts` exists for an older generation; adapt or new driver |
| Pen | Wacom W90xx over I2C | to investigate |
| 5G modem | Snapdragon X55, external over PCIe | MHI/ModemManager support exists for M.2 modules; Samsung wiring unknown |
| Cameras, video decode | — | out of scope |

Reference templates: upstream `sm8250-xiaomi-elish` and `sm8250-xiaomi-pipa`
(SM8250 tablets).

## Phases

| # | System | Work | Done when |
|---|---|---|---|
| 0 | host | pmbootstrap, pmaports fork with `device-samsung-gts7xl`, upstream stable kernel checkout with our DTS, tools | a pmOS image builds |
| 1 | pmOS | minimal DTS: boot, memory, UFS, USB | `ssh`/`telnet` into the tablet over USB, `dmesg` readable |
| 2 | pmOS | OLED panel driver + display power | console shown on the panel |
| 3 | pmOS | touch (STM FTS) | Phosh usable by finger |
| 4 | pmOS | Wi-Fi, charging/battery, buttons, Freedreno | runs on battery, Wi-Fi, GPU acceleration |
| 5 | Arch | port kernel, firmware, config as Arch packages | Arch boots with the same working hardware |
| 6 | Arch | Omarchy 4.5 aarch64 + touch layer (on-screen keyboard, hyprgrass gestures, menu buttons, rotation) | Omarchy usable without a physical keyboard |
| 7 | Arch | pen, audio, rotation sensor, suspend | one item at a time |
| 8 | Arch | optional: X55 5G modem | data connection works (no promise) |

Phases 2 and 3 carry the project's main risk. If the panel resists, phases 4-5
can still progress headless over SSH.

Phases 5-8 get their own design once phase 4 is reached.

Option to decide at the start of phase 5 (raised 2026-11-17): add a Steam
gaming mode. Either SteamOS ARM as an alternative userspace (prior art for the
SM8250 Tab S7 11": github.com/Iamtianyuyang/steamos-tabs7), or — preferred so
far — a gamescope + Steam Big Picture session launched from the Omarchy menu
on Arch Linux ARM, with FEX + Proton for x86 games and Turnip (Mesa Vulkan,
Adreno 650). The kernel/DT work of phases 1-4 is the same either way.

## Phase 1 design: boot chain

> **Amended 2026-11-17 (before the first flash).** Points 3 and 4 and the "flashed on every
> attempt" line below are superseded. The ABL of the Tab S7 family only goes through with the
> vendor DTB, so the image carries a **boot shim** in the kernel slot and the **stock DTB and
> stock overlays** for the ABL; the shim hands the mainline DTB to the mainline kernel
> (`tools/mkshim.py`, `tools/shim/`). The image goes to **RECOVERY**; BOOT and DTBO are never
> written, VBMETA only in the second attempt. USB needs the MAX77705 MUIC switched from the
> initramfs. Current procedure: `docs/runbooks/first-flash.md`.

Requirements of the Samsung ABL (learned during the Droidian attempt):

1. **boot.img header v2** containing kernel, initramfs and DTB, with an **AVB
   hash footer** signed with the AOSP test key, partition name `boot`.
   Tool: `tools/sign-boot.py`, derived from the Droidian port's
   `build-bootimg.py`. Header fields the ABL checks (load addresses, OS
   version/SPL, board name) are copied from this tablet's **stock T976B
   boot.img**, not from the Wi-Fi port's constants.
   The tool keeps the cmdline pmbootstrap wrote (`pmos_boot_uuid`,
   `pmos_root_uuid`, `pmos_rootfsopts` plus `deviceinfo_kernel_cmdline`): the
   initramfs looks the subpartitions up by filesystem UUID. A signed boot.img
   therefore only matches the rootfs image of the same `pmbootstrap install`.
   The rootfs image uses 4096-byte sectors (`deviceinfo_rootfs_image_sector_size`),
   like the tablet's UFS.
2. **vbmeta disabled** (flags 0x02): `vbmeta-disabled.img`, always flashed in
   the same Heimdall command (single-image commits are unreliable on SM8250).
3. **DTB selection by `qcom,msm-id` and `qcom,board-id`**: our mainline DTB must
   carry the exact values of the 5G downstream DTBs. Values are read from the
   compiled downstream DTBs, never guessed.
4. **DTBO overlays**: ABL applies the `dtbo` partition on top of the selected
   DTB, which would corrupt a mainline DTB. We flash an **empty DTBO table**
   (magic 0xd7b7ab1e, zero entries), generated by `tools/`.

Flashed on every attempt: `BOOT`, `DTBO` (empty), `VBMETA` (disabled).
Flashed once: pmOS rootfs to `userdata`, TWRP 3.7.1 to `RECOVERY`.

Observability without a working panel or keyboard:

- **USB debug shell**: pmOS initramfs debug hook, USB network gadget,
  `172.16.42.1` from the host. The USB controller is forced to
  `dr_mode = "peripheral"`; no reliance on the MAX77705 Type-C logic early on.
- **simple-framebuffer**: ABL leaves the panel on after the logo. Describing the
  splash framebuffer (address/size/stride from the downstream DT) may give an
  on-screen console in phase 1 already; phase 2 then adds real panel control
  (brightness, blanking, 120 Hz).
- **Crash logs**: ramoops region in the DTS; after a failed boot, reboot into
  TWRP and read the previous kernel log from pstore.
- **Last resort**: a minimal kernel that reboots on purpose after N seconds; a
  reboot proves the kernel ran. Then add blocks back one at a time.

## Phase 1 design: minimal device tree

`arch/arm64/boot/dts/qcom/sm8250-samsung-gts7xl.dts`, based on `sm8250.dtsi`,
modelled on elish/pipa. Contents:

| Node | Source of values |
|---|---|
| `qcom,msm-id`, `qcom,board-id` (5G) | downstream compiled DTB + `dtbo-5g` overlays |
| reserved-memory | Samsung memory map — most sensitive item: a missing region crashes silently |
| PM8150/PM8150B/PM8150L regulators (RPMh) | downstream DT + Xiaomi template |
| UFS | SM8250 standard |
| USB (peripheral) | SM8250 standard |
| simple-framebuffer | downstream splash region |
| volume/power keys | `gpio-keys` + PMIC |
| ramoops | reserved region |

Only values (addresses, GPIOs, voltages) are taken from the downstream tree,
never its Samsung-specific code.

## Workspace

`gts7xl-mainline/` (local git, not pushed for now):

| Path | Content |
|---|---|
| `linux/` | upstream **stable** kernel (latest release tag), branch `gts7xl`, built with `pmbootstrap envkernel`. `gitlab.com/sm8250-mainline/linux` stops at v6.13 (MAX77705 needs ≥ 6.15), so it is a source of cherry-picks only, not the base |
| `pmaports/` | fork, `device/testing/device-samsung-gts7xl` |
| `tools/` | AVB boot.img wrapper, empty-DTBO generator, `flash.sh` (one Heimdall command) |
| `reference/` | downstream DTBs decompiled to text |
| `NOTES.md` | log of every flash: what was flashed, what happened |
| `docs/specs/` | this document |

Publishing (GitHub repo, upstream DTS submission, pmaports MR) comes after a
working boot.

## Safety rules

- Each flash is done with the maintainer present and the tablet in Download Mode.
  The first flash wipes One UI and is confirmed separately.
- Only `BOOT`, `DTBO`, `VBMETA`, `RECOVERY`, `USERDATA` are ever written.
- The only flash path is `tools/flash.sh`. `pmbootstrap flasher` is never used
  (it would write the unsigned boot.img without vbmeta); the device package sets
  `deviceinfo_flash_method="none"` so it refuses.
- Before the first flash: back up EFS from TWRP to the host.
- Every flash is logged in `NOTES.md` with the image hashes.

## Out of scope

Cameras, hardware video decode, fingerprint reader, grip sensors, Samsung DeX
equivalents. The 5G modem is optional (phase 8).
