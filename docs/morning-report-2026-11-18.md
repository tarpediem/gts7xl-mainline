# Morning report — 2026-11-18

## Read first (coordinator)

- **Module cleanup masked.** Omarchy's `linux-modules-cleanup.service` deleted the module folders of
  the BOOT (r20) and RECOVERY (r15) kernels after kexec tests overnight (no Wi-Fi/BT/audio on r20
  until they were restored). It is now masked on the tablet and in `arch/gts7xl-device/install.sh`;
  all module folders (7.3.4, r20, r21, r50) are present. Keep it masked: our kernels' module dirs are
  not all pacman-owned.
- **sudo without password** for `tarpediem` on the tablet (`/etc/sudoers.d/90-tarpediem-nopasswd`);
  the agents' helper that piped the Wi-Fi password into sudo is deleted.
- **Host PC:** 44 stale pmbootstrap chroot mounts are visible in the build PC's mount namespace. Do not
  run `pmbootstrap shutdown`/`zap` or unmount them by hand; they go away at the next reboot of the PC.
  Every pmbootstrap command must run under `sudo unshare --mount --propagation private`.
- **Static DHCP lease** on the OPNsense: the tablet has a fixed LAN address (see the private notes). USB: 172.16.42.1, the PC
  has a NetworkManager profile `gts7xl-usb` (172.16.42.2/24).
- **Drafts waiting for you:** XDA thread (`docs/xda/thread-draft.md`), upstream kernel series
  (`docs/upstream/`, patches in `build/upstream-series/`, Signed-off-by placeholder: your identity).

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

## Camera & sensors (kexec-tested overnight, nothing flashed)

Tested by booting a test kernel without flashing (kexec), then back to r20 each time. Your
BOOT kernel (r20) is unchanged; these features need the next kernel build (pmaports branch
`gts7xl-sensors`, test release r50) to be in what you flash.

- **Screen rotation (accelerometer): works.** The sensors sit behind the sensor DSP (SLPI),
  which now boots with your own factory calibration; the accelerometer gives steady readings
  (about 9.8 m/s² total) and iio-sensor-proxy (what GNOME uses) sees it. Not checked yet: that
  GNOME rotates the right way when you turn the tablet (needs hands).
  Compass also reads. **Light sensor: not found** on the sensor DSP (Samsung seems to expose it
  differently), so no auto-brightness yet.
- **Book cover**: two cover switches show up (book cover and pen-digitizer cover); both read
  "open" at night. Close the cover once to check. Closing it will **not** suspend (set to
  ignore); GNOME just turns the screen off.
- **S Pen (drawing): driver works, pen not yet tried.** The digitizer is detected (firmware
  0x403d) and appears as a pen tablet with pressure (4096 levels), hover, tilt, side button and
  eraser. Please draw something (e.g. in a paint app) on the test kernel: check that the
  cursor sits under the pen tip in the corners. Pen-holder detection not done.
  **S Pen Bluetooth (Air actions)**: Samsung's own protocol; not touched, low chance.
- **Rear camera: detected, no pictures yet.** The 13 MP sensor (Samsung S5K3M5) powers up on its
  stock rails and clock, answers with the right chip ID, and libcamera lists
  "Internal back camera". Taking pictures needs one more step (the driver only has settings for a
  24 MHz sensor clock; stock uses 19.2 MHz). Front (8 MP) and ultra-wide (5 MP) sensors have no
  Linux driver.
- **Fingerprint**: not possible (owned by the secure firmware).

**Fixed during the night (important):** a package on Omarchy (`kernel-modules-hook`) deletes the
module folders of every kernel that pacman does not own at each boot. Booting test kernels made it
delete the r20 (your BOOT) and RECOVERY module folders: r20 then came up without Wi-Fi, Bluetooth
and sound. They were restored and that cleanup service is now disabled on the tablet (and in the
image build). Checked after the last reboot: r20 with Wi-Fi, Bluetooth and speakers.

**Update after your morning test (fixed in test kernel r51, not flashed):**
- Wrong rotation: the axes were turned by 90°; corrected from your test (the tablet in the same
  pose now reads "normal").
- S Pen and the missing sensor service: every test kernel started by kexec flooded the system
  with an audio-DSP error (about 70 000 messages, the red text on screen), which jammed the
  device manager, so GNOME probably never picked up the pen and the sensor service did not
  start. Fixed (0 errors on r51), and the sensor service now starts when the sensor DSP is ready.
- **To test (5 minutes, you hold the tablet):** in a terminal on the PC, in
  `~/Work/samsung/gts7xl-mainline`: `tools/sensors-k50-test.sh` . When it prints "On the tablet now"
  you have 60 s to hover and draw with the S Pen (corners, side button), then turn the tablet
  around for 30 s; then press Enter in the terminal and the tablet goes back to r21.

## Kernel r22 (sensors, S Pen, rotation) — ready to flash

r22 = r21 + rotation, S Pen, cover switches and the fix for the red error flood. Kexec-tested
from r21: Wi-Fi, Bluetooth, speakers, charging, GPU all as before. Omarchy already has the r22
package installed. To flash: put the tablet in **Download Mode** (power off, unplug, hold
Vol Up + Vol Down while plugging the PC cable, then a short Vol Up); the PC flashes BOOT r22 by
itself and checks the tablet after it reboots. Rollback: same with r21 (`boot-shim-r21-fbb8aa14.img`)
or Vol Up + Power for RECOVERY.

## Audio (speakers, overnight, no sound played)

- **Crackle**: the data path is clean. A silent loopback test (speakers muted, the amplifiers
  echo what they receive back over the bus) shows the speaker data arrives bit-exact; PipeWire
  shows no device underruns even under full CPU load; the amplifiers' noise gates and ramps are
  off. So the crackle is not a bus or driver error. Likely suspects: the speakers being driven
  past their limits at high volume (no Samsung protection yet), or the amplifier boost. To find
  out, a short test with you this morning at low volume while recording the amplifiers' current
  sense.
- **Speaker protection (the Android "Cirrus" part)**: Samsung's protection firmware and your
  tablet's factory calibration are found and load on mainline; a silent run with calibration
  worked. Not switched on yet (two details to fix first). Next: a low-volume listening test with
  protection on, then it can replace the simple bass filter and give the bass back safely.
- **Microphones and USB-C headset**: investigated only. Mics need a small kernel change (same
  setup as the Qualcomm RB5 board). USB-C headsets need USB host mode first (digital dongles);
  analog USB-C headsets are not supported by this hardware path.
- Nothing flashed for audio; BOOT r20/r21 audio is unchanged.
