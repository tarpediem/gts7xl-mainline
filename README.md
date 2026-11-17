# gts7xl-mainline

Mainline Linux (postmarketOS) on the Samsung Galaxy Tab S7+ 5G (SM-T976B, Qualcomm
SM8250, codename `gts7xl`).

This repository holds the tooling, notes and runbooks. The kernel and the postmarketOS
packages live in two companion repositories:

- Kernel: [tarpediem/gts7xl-linux](https://github.com/tarpediem/gts7xl-linux), branch
  `gts7xl` (patches on top of the stable tag `v7.3.4`).
- pmaports: [tarpediem/gts7xl-pmaports](https://github.com/tarpediem/gts7xl-pmaports),
  branch `gts7xl` (`device-samsung-gts7xl` and `linux-samsung-gts7xl`, which carries the
  kernel patches).

Status: early bring-up. Expect rough edges.

## What works

- Boots mainline Linux 7.3.4 from the **RECOVERY** partition. A small boot shim
  (`tools/shim/`) is loaded by the stock bootloader together with the stock (vendor) DTB
  and overlays, then jumps into the mainline kernel with the mainline DTB.
- Display: new DRM panel driver for the Samsung S6TUUM3 (AMSA24VU01) DSC panel.
- Touchscreen: new driver for the ST FTS1BA90A, over I2C with GPI DMA.
- UFS storage.
- USB networking (RNDIS/NCM) and the postmarketOS initramfs debug shell over USB
  (`telnet 172.16.42.1`). Tooling for kexec and module push over USB is in place
  (`docs/runbooks/iterate-over-usb.md`); kexec works from kernel r12 on.
- Power key: a short press toggles the display and the touchscreen.
- Wi-Fi (QCA6390 on PCIe, ath11k) and Bluetooth (QCA6390 on UART, hci_uart): the driver
  probes, `wlan0` and `hci0` come up, scans work (tested in the debug shell with `iw` and
  `btmgmt`; nothing connected yet). The generic linux-firmware board data is used; the
  stock calibration can be added locally (`tools/wlan-fw-overlay.py`, see the runbook).
  Bluetooth has no BD address yet (set one with `btmgmt public-addr` before powering on).

## What does not work yet

- Connecting to a network (no supplicant in the debug shell), the stock BD address
- Battery and charging
- GPU acceleration
- Audio
- Modem
- Booting a rootfs (the system stops in the initramfs debug shell)

## Safety

- Only the **RECOVERY** partition is flashed. One UI keeps booting from BOOT; to go back,
  flash the stock `recovery.img`.
- DTBO, BOOT and VBMETA stay untouched in the default path (attempt A of the runbook).
  Userdata is never written.
- An unlocked bootloader is required, which trips Knox and wipes the device when you
  unlock it.
- No warranty of any kind. You can brick or damage your device. Read the runbooks fully
  before running anything.

## Build and flash

1. Read `docs/runbooks/first-flash.md` (prerequisites, what gets flashed and why, how to
   recover).
2. Build the kernel and the image with pmbootstrap using the `gts7xl` branch of
   gts7xl-pmaports, then build the RECOVERY image with
   `tools/build-recovery-shim.sh` (needs the stock boot and recovery images from the
   stock firmware in `build/stock/`).
3. Flash RECOVERY with `tools/flash.sh` (heimdall, Download Mode).
4. For later iterations without reflashing, see `docs/runbooks/iterate-over-usb.md`.

`NOTES.md` is the build and flash log (newest at the bottom), `reference/` has the stock
device tree extracted from the stock firmware, and `tests/` has the checks run before each
flash.

## Credits

The boot shim is based on boot/shim from
[steamos-tabs7](https://github.com/Iamtianyuyang/steamos-tabs7) (GPL-2.0).

## License

GPL-2.0-only, see `LICENSE`. The kernel patches follow the Linux kernel licensing.
`tools/keys/testkey_rsa4096.pem` is the public AOSP AVB test key.
