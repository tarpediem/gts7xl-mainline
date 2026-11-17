# Morning report — 2026-11-18

## State of the tablet

- Running: Omarchy 4.5 (Arch Linux ARM) on USERDATA, **BOOT r20** (kernel 7.3.4-r20), RECOVERY r15.
- Default session GNOME 51 (Wayland) via SDDM autologin; Hyprland/Omarchy still selectable in SDDM.
- User password = the home Wi-Fi password (change it with `passwd`).

## What changed overnight

- **Kernel r21 ready, not flashed**: Landlock (pacman's sandbox, needed for Omarchy updates),
  netfilter matches for ufw (the firewall now starts cleanly), GPU cooling device (thermal
  throttling of the Adreno). Kexec-tested from r20: everything up, firewall active, pacman sandbox OK.
- Omarchy already carries `linux-gts7xl 7.3.4.r21-1` (r21 modules + the BOOT image). The r20 and
  RECOVERY (r15) module directories are kept, so both fallbacks still boot with their modules.
- GNOME: dock at the bottom (64 px icons; Firefox, Console, Files, Settings, cliamp), dark theme
  with a pink accent to match the wallpaper, battery percentage, bigger panel, Omarchy's apps grouped
  into folders (Omarchy, Terminal tools, Office, System), Tweaks and Extension Manager installed,
  screen blank after 5 min, no idle suspend, built-in on-screen keyboard.
- Firefox: touch events, kinetic scrolling, swipe back/forward, portal file picker.
- Text consoles (Ctrl+Alt+F2): kmscon font size 28.
- zram swap 7.2 GB (zstd) active.
- USB host/OTG: design only (docs/usb-dual-role-design.md); nothing changed on the USB side.

## To flash this morning (optional, r21)

Put the tablet in Download Mode: power off, unplug, hold **Vol Up + Vol Down** while plugging the
PC cable, then a short **Vol Up**. Then, on the PC, in `~/Work/samsung/gts7xl-mainline`:

    printf 'FLASH\n' | FLASH_SSH="ssh localhost" tools/flash.sh --pit build/gts7xl.pit --keep-vbmeta \
        BOOT=build/archive/boot-shim-r21-fbb8aa14.img

(sha256 fbb8aa1401e3c2c0f86d74f22c5ca37d0b0648011dfc4cd396726516f2401343.) Rollback: the same
command with `BOOT=build/archive/boot-shim-r20-09873501.img`, or Vol Up + Power for RECOVERY.

## Please test by hand

1. **Sound**: play something in Firefox or cliamp at low volume; it should come out of the
   speakers, clean; the volume key should stop at 60 %.
2. **Power key**: short press = screen off, again = screen on (in GNOME and in Hyprland).
3. **On-screen keyboard**: tap a text field in GNOME; the keyboard should appear.
4. **Bluetooth keyboard**: press a key (it reconnects), type; in Hyprland/Omarchy the left Alt
   works as Super (Alt+Space = Omarchy menu).
5. **Dock and app grid**: tap the dock icons; open the app grid and check the folders.
6. **USB**: the USB-C port is still device-only (PC link). Hubs/keyboards on USB-C need the OTG
   work, which is designed but not started.

## Camera & sensors (prepared overnight, not tested on the tablet)

Nothing here is on the tablet's kernel yet, and nothing was flashed. The agents could not test it:
it needs root on the tablet (your password), which they do not type.

- **Screen rotation (accelerometer)**: the sensors (accelerometer/gyroscope, compass, two light
  sensors) sit behind the sensor DSP (SLPI). Ready: device tree (SLPI on), the SLPI firmware and
  sensor files from your stock firmware and your tablet's own calibration, hexagonrpcd (built on
  the tablet in `~/src`), udev and service files. Files staged in `~/staging-sensors` on the tablet.
  Feasible and likely to work; GNOME then rotates the screen by itself.
- **Book cover**: the two magnet sensors become a lid switch and a "cover" switch. Closing the
  cover will **not** suspend (set to ignore); GNOME just turns the screen off.
- **S Pen (drawing)**: new driver for the Wacom digitizer (Samsung's protocol differs from the
  mainline Wacom driver): pen position, pressure, hover, tilt, side button, eraser. Needs a
  kernel built with it (pmaports branch `gts7xl-sensors`). Pen holder detection not done.
  **S Pen Bluetooth (Air actions)**: proprietary Samsung protocol; not touched, low chance.
- **Cameras**: rear 13 MP Samsung S5K3M5 has a mainline driver: a test device tree is ready
  (separate file, not used at boot). Front 8 MP (S5K4HA) and ultra-wide 5 MP (S5K5E9) have no
  Linux driver: each would need one written. Expect photos only through libcamera's software
  pipeline (no autofocus at first).
- **Fingerprint**: not possible (owned by the secure firmware). **Light sensor**: comes with the
  sensor DSP work above (GNOME auto-brightness).

To test (about 10 minutes, the tablet reboots twice, back on r20 at the end): from the PC,
`tools/sensors-kexec-test.sh <root runner>`, or ask the coordinator to run it. Results land in
`build/sensors-test-*/`.
