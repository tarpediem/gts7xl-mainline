# XDA thread draft — Galaxy Tab S7+ > Development

Draft for the owner's review. Not posted. Forum: Samsung Galaxy Tab S7+ → Development.
The body below is BBCode (XDA's editor accepts it as is); markdown headings outside the
`bbcode` block are notes for the owner only.

## Title

`[DEV][Mainline Linux][SM-T976B] Galaxy Tab S7+ 5G (gts7xl): Linux 7.3 with display 120 Hz, touch, GPU, Wi-Fi, speakers — Omarchy / postmarketOS`

Shorter alternative: `[DEV] Mainline Linux on the Tab S7+ 5G (SM-T976B, SM8250)`

## Body

```bbcode
[CENTER][SIZE=6][B]Mainline Linux on the Galaxy Tab S7+ 5G (SM-T976B, gts7xl)[/B][/SIZE]
[I]Upstream Linux 7.3 kernel, no Android underneath. Early development — read the warnings.[/I][/CENTER]

[SCREENSHOT 1: Omarchy desktop, landscape]
[SCREENSHOT 2: app launcher with the on-screen keyboard]

[SIZE=5][B]What this is[/B][/SIZE]
A port of the mainline Linux kernel (Linux 7.3.4 plus a few dozen device patches) to the Tab S7+ 5G, with a regular desktop Linux userspace on top:
[LIST]
[*][B]Omarchy[/B] (Arch Linux ARM based, Hyprland), the main image today
[*][B]GNOME[/B] (installed on top of the Omarchy image, touch-friendly setup)
[*][B]postmarketOS[/B], used during bring-up (the kernel and device packages are pmaports)
[/LIST]
The stock Samsung bootloader loads a small boot shim together with the stock device tree; the shim then starts the mainline kernel with the mainline device tree. One UI can be restored by flashing the stock images back (see the runbooks).

[SIZE=5][B]What works[/B][/SIZE]
[LIST]
[*][B]Display[/B]: 2800x1752 OLED at [B]120 Hz[/B] (new panel driver, DSC, command mode). Display off/on with the power key.
[*][B]Touchscreen[/B]: multitouch (new driver for the ST FTS1BA90A). No S Pen yet.
[*][B]GPU[/B]: Adreno 650 with freedreno (OpenGL ES 3.2) and [B]turnip (Vulkan 1.3)[/B]. Hyprland and GNOME are GPU-accelerated; glmark2-es2 scores ~800 at full resolution.
[*][B]Wi-Fi[/B] (QCA6390, ath11k) and [B]Bluetooth[/B] (QCA6390; keyboards pair and work).
[*][B]Speakers[/B]: all four (4x CS35L41 through the ADSP), stereo. Volume is deliberately capped and a protective filter is applied — see "Speaker protection" below.
[*][B]Charging[/B] from USB with a [B]safety monitor[/B]: temperature window, charge timer, hardware watchdog, and an [B]80 % charge limit[/B] by default (resumes below 75 %, adjustable). Charging current is kept conservative, so it is slow (see warnings).
[*][B]Battery level[/B] (fuel gauge).
[*][B]USB networking[/B] to a PC (USB device mode, NCM/RNDIS) with SSH — the main development link.
[*]UFS storage, volume keys, power key, ramoops (kernel log survives a crash and can be read back).
[*][B]kexec[/B]: new kernels are tested by kexec over USB without flashing anything — handy if you want to hack on it.
[/LIST]

[SIZE=5][B]What does not work (yet)[/B][/SIZE]
[LIST]
[*]Cameras
[*]Sensors: no accelerometer, so [B]no auto-rotation[/B]; no light sensor, no fingerprint
[*]Microphones, headset audio over USB-C
[*][B]USB host[/B] (no keyboard/hub/drive on the USB-C port; only device mode to a PC)
[*][B]Hardware speaker protection[/B] (Cirrus DSP firmware is not loaded; a software filter and a volume cap stand in)
[*][B]Suspend[/B] (the screen turns off, but the SoC does not sleep: battery drain is high when idle)
[*]Modem / 5G / mobile data, GPS
[*]S Pen, keyboard cover pogo pins
[*]Fast charging (the direct charger is left off on purpose)
[/LIST]

[SIZE=5][B][COLOR=rgb(184, 49, 47)]WARNINGS — read all of this[/COLOR][/B][/SIZE]
[LIST]
[*][B]Unlocked bootloader required.[/B] Unlocking [B]wipes the tablet[/B] and [B]trips Knox permanently[/B] (Samsung Pay, Secure Folder, some banking apps and Samsung Health features will not work again, even after relocking).
[*][B]Data loss.[/B] Installing the Linux root filesystem [B]overwrites USERDATA[/B]: everything in One UI is erased. Back up first.
[*][B]Only RECOVERY, BOOT and USERDATA are written.[/B] DTBO, VBMETA, EFS, modem and the other partitions are never touched by the runbooks. Do not flash anything else, and do not use any other tool or image.
[*][B]Back up EFS first[/B] (IMEI, calibration, Wi-Fi/BT addresses) with root in One UI, and keep the backup off the device. The runbooks never write EFS, but a backup is your only way back if something else ever does.
[*][B]Battery safety.[/B] The charger driver is new code. It stops charging outside 2-41 °C, after 10 h, at 80 %, and if the kernel stops (watchdog); limits are below every stock setting. Still: [B]do not leave the tablet charging unattended[/B], and stop if it gets hot or the battery swells.
[*][B]Speakers.[/B] Without the Samsung speaker-protection DSP the amplifiers can damage the speakers at high volume. Keep the provided volume cap and filter; do not play loud bass-heavy audio.
[*][B]Only the SM-T976B (Tab S7+ 5G, SM8250)[/B] has been tested. The Wi-Fi-only Tab S7+ (SM-T970, SM8250) and the Tab S7 (T870/T875) are different boards: [B]do not flash these images on them[/B].
[*]No warranty of any kind. You can brick or damage your device. You do this at your own risk.
[/LIST]

[SIZE=5][B]Installation (overview)[/B][/SIZE]
There are no one-click images yet. Everything is built from source and every step is described in the runbooks, which explain what is written and why, and how to go back. Read them completely before running anything.
[LIST=1]
[*]Unlock the bootloader, update to the stock firmware the runbooks expect, back up EFS and your data.
[*][B]First flash runbook[/B]: build the kernel and the boot shim, flash [B]RECOVERY only[/B] with heimdall (Download Mode), and boot it with Vol Up + Power. One UI keeps booting normally from BOOT.
[URL]https://github.com/tarpediem/gts7xl-mainline/blob/main/docs/runbooks/first-flash.md[/URL]
[*][B]Root filesystem runbook[/B]: write the root filesystem to [B]USERDATA[/B] (this erases One UI's data), then flash the matching [B]BOOT[/B] image. Includes going back to One UI.
[URL]https://github.com/tarpediem/gts7xl-mainline/blob/main/docs/runbooks/rootfs-on-userdata.md[/URL]
[*]For development: kexec and module push over USB, no flashing.
[URL]https://github.com/tarpediem/gts7xl-mainline/blob/main/docs/runbooks/iterate-over-usb.md[/URL]
[/LIST]

[SIZE=5][B]Source code[/B][/SIZE]
[LIST]
[*]Tooling, notes, runbooks: [URL]https://github.com/tarpediem/gts7xl-mainline[/URL]
[*]Kernel (branch gts7xl, on Linux 7.3.4): [URL]https://github.com/tarpediem/gts7xl-linux[/URL]
[*]postmarketOS packages (branch gts7xl): [URL]https://github.com/tarpediem/gts7xl-pmaports[/URL]
[/LIST]
The kernel patches are being prepared for submission to upstream Linux (panel, touchscreen, charger, audio, device tree).

[SIZE=5][B]Credits[/B][/SIZE]
[LIST]
[*][B]postmarketOS[/B] — pmbootstrap, the initramfs and the packaging this port is built with
[*][B]linux-msm[/B] and the Qualcomm mainline maintainers and contributors — SM8250 support in mainline (display, GPI, audio, remoteprocs, ...)
[*]The [B]SM8250 mainline community[/B] — device trees of other SM8250 phones and boards that showed the way
[*][B]freedreno / Mesa[/B] — the Adreno 650 OpenGL and Vulkan (turnip) drivers
[*][B]Omarchy[/B] — the desktop userspace
[*][B]steamos-tabs7[/B] (Iamtianyuyang) — the boot shim idea and code, from the Tab S7 11" work
[*]Upstream MAX77705 and CS35L41 driver authors
[/LIST]

[SIZE=5][B]Bugs / contributions[/B][/SIZE]
Issues and pull requests on GitHub. When reporting, include the kernel version, what you did, and the kernel log (dmesg; or the ramoops log after a crash). Do not post your EFS or IMEI.

[SPOILER="Changelog"]
2026-11-18: first public thread. Kernel 7.3.4-r20, Omarchy image.
[/SPOILER]
```

## Notes for the owner (not part of the post)

### Screenshots

Local captures in `build/gui/` (not in git) and what fits:

| File | Use? | Why |
|---|---|---|
| `omarchy-firstboot/06-after-reboot.png` | **Yes** — screenshot 1 | Clean Omarchy desktop, dock, status bar; nothing personal visible |
| `omarchy-firstboot/04-osk.png` | **Yes** — screenshot 2 | App launcher over squeekboard (touch use) |
| `omarchy-firstboot/02-polkit.png` | Optional | Desktop with first-run notifications; nothing personal, but less nice |
| `omarchy-firstboot/01-boot.png` | **No** | Error banner shows a home directory path with the user name |
| `omarchy-firstboot/03-polkit.png` | No | Password prompt for a temporary sudoers script |
| `omarchy-firstboot/05-after-reboot.png` | No | Black frame |
| `201251/01-desktop.png` | No | Not a valid PNG |
| `hyprland-desktop.png` | **No** | Shows the network name |
| `gnome/` | — | Empty: GNOME blocks screenshots from SSH; take some on the tablet (Print Screen) |
| `docs/photos/2026-11-17-first-console.jpg` (in git) | Optional | Photo of the first console boot; good "bring-up" image |

Before uploading any image, check the status bar and notifications for SSIDs, IP addresses,
host names and clock/time zone. Nice additions: a photo of the tablet running vkcube or
glmark2, and a GNOME screenshot taken on the device.

### Facts to double-check before posting

- Brightness: not claimed in the post; the panel driver has a backlight, confirm the slider in GNOME and
  Hyprland.
- Wi-Fi: only one 5 GHz WPA2 network tested; band support is not claimed in the post.
- Bluetooth: a keyboard was paired; audio over Bluetooth not tested.
- Suspend: the cmdline still has `cpuidle.off=1`; idle drain not measured — keep the wording
  vague or measure it first.
- The charge current is 450 mA (battery side) with 475 mA input, 1.8 A input on a wall
  charger: a full charge to 80 % takes many hours. Say a number only after measuring.
- Whether the stock firmware version expected by the runbooks should be named in the post.
- Whether to mention the Tab S7 (SM-T870) as "possible with work" or not at all.

### Privacy

The draft contains no real name, address, network name, IP address, host name or serial
number. Keep it that way in replies (logs pasted in the thread: strip the Wi-Fi name and the
Bluetooth/Wi-Fi MAC addresses).
