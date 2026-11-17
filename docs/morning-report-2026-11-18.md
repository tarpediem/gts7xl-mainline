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
