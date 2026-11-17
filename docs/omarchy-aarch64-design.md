# Omarchy aarch64 on the gts7xl: design and build (image built, USERDATA not written)

Goal: replace the postmarketOS root filesystem on USERDATA with an Omarchy (Arch Linux ARM
based) root filesystem, keeping our boot chain (ABL → boot shim → our kernel r19 + the pmOS
initramfs) and every device fix found so far. Status: design only. Writing USERDATA wipes the
current pmOS rootfs; that step waits for the owner's go after the backup (section 6).

## 1. What Omarchy provides on aarch64 (researched 2026-11-17)

- Omarchy 4.5 (Nov 2026) ships an **aarch64 ISO**: `https://iso.omarchy.org/omarchy-4.5.0-rc2-aarch64.iso`
  (SHA256 `ee885285d6cba0dfc9a9ead22cf5bcc203b9f460970721b3c0b8a1dca4c867a8`, from the GitHub
  release notes; rc3 and edge nightlies exist at `https://nightly.omarchy.org/edge-aarch64/`).
- Installed aarch64 systems take packages from **Omarchy's aarch64 repository on
  pkgs.omarchy.org, ordered ahead of Arch Linux ARM** (Omarchy Central; release notes "Prioritize
  Omarchy's package repository over Arch's"). The exact `[repo]` names, server URLs and the
  signing key are **to be read from the ISO** (its `/etc/pacman.conf` and keyring package), not
  guessed.
- Supported aarch64 targets: Apple Silicon (separate Mac installer), NVIDIA DGX Spark / N1x,
  Snapdragon X laptops. They all boot **UEFI + limine + UKI** with `linux-omarchy-aarch64` and
  a `linux-omarchy-dtbs` package (DTB selected through UKI `.dtbauto`/`.hwids`).
- None of that boot path exists on this tablet: Samsung's ABL boots Android boot images only, no
  UEFI. So the ISO installer cannot be used as is; we take Omarchy's **userspace** (packages,
  configs, `omarchy-*` tooling) and keep **our** kernel and boot images.

## 2. Boot chain: unchanged, no flash needed

Today BOOT (r19) and RECOVERY (r15) carry: shim → kernel → pmOS initramfs, cmdline with
`pmos_boot_uuid` / `pmos_root_uuid`. The initramfs (`mount_subpartitions`) attaches USERDATA as a
loop disk with exactly two partitions, finds the root filesystem **by UUID**, grows it on the
first boot, and `switch_root`s into `/sbin/init` (systemd). It does not care which distribution
the root filesystem holds.

So the Omarchy image reuses the current layout and **the same filesystem UUIDs**:

| Partition (GPT, 4096-byte sectors) | Filesystem | UUID |
|---|---|---|
| p1 `pmOS_boot` | ext2 | `pmos_boot_uuid` of the current cmdline |
| p2 `pmOS_root` | ext4 | `pmos_root_uuid` of the current cmdline |

Same UUIDs = BOOT r19 and RECOVERY r15 boot it without a flash. (Later kernels keep using
`tools/build-recovery-shim.sh --cmdline-from …` as now.) The root stays ext4 for v1: no btrfs/
snapper, no LUKS (the pmOS initramfs could do both, out of scope for the first boot).

## 3. Building the root filesystem on the host

Host: the build PC (x86_64, Omarchy). aarch64 code runs under qemu-user (binfmt): pmbootstrap
already registers it; otherwise `qemu-user-static` + `qemu-user-static-binfmt`.

1. **Base**: Arch Linux ARM generic aarch64 tarball (`ArchLinuxARM-aarch64-latest.tar.gz`,
   signature checked) extracted into `build/omarchy/root` (as root, numeric owners kept), or
   `pacman --arch aarch64 --root` with ALARM's mirrorlist and keyring. Remove its kernel
   (`linux-aarch64`) and `uboot` bits.
2. **Omarchy repos**: copy `/etc/pacman.conf`, mirrorlists and the Omarchy keyring from the
   aarch64 ISO's live root (`unsquashfs` of its airootfs, read only), `pacman-key --init`,
   `--populate archlinuxarm omarchy`. `IgnorePkg = linux-omarchy* linux-aarch64 linux-firmware-*`
   is **not** used for firmware (we want Arch's qcom/ath11k firmware); only the kernels are ignored.
3. **Omarchy userspace**: in `arch-chroot` (qemu): `pacman -Syu` then the package set of the
   ISO's install manifest (read `install/` and the package lists from the omarchy git tag matching
   the ISO, run its non-interactive install steps as the user). Steps that touch the bootloader,
   UKI, limine, snapper, plymouth-on-UEFI, LUKS, or hardware detection for other machines are
   skipped by a small list in our build script (each one logged).
4. **Kernel**: no Arch kernel package. Copy `/usr/lib/modules/7.3.4-r19` from our
   `linux-samsung-gts7xl` apk, run `depmod -a 7.3.4-r19`. A `pacman` hook and a stub keep
   Omarchy's update tooling from rebuilding a UKI or calling `limine-mkinitcpio`
   (`/usr/local/bin/limine-mkinitcpio` → no-op with a message; mkinitcpio presets removed).
   Kernel updates = our pmaports build → `tools/install-kernel-arch.sh` (copies the module
   directory over SSH, depmod) + BOOT image as today.
5. **Firmware**: Arch `linux-firmware-qcom` (a650_sqe/a650_gmu, ADSP…) and the ath11k/QCA
   packages; the local zap shader at `/usr/lib/firmware/qcom/sm8250/samsung/gts7xl/a650_zap.mbn`
   (from `tools/extract-gpu-zap.py`, never published); the stock QCA6390 board files if the pmOS
   rootfs uses them (check `/lib/firmware/ath11k` on the tablet before wiping).
6. **Device layer** (ported from `device-samsung-gts7xl` subpackages; packaged as an Arch
   `PKGBUILD` `gts7xl-device` in this repo so it is reproducible):
   - Bluetooth address service (`gts7xl-bt-addr`), HID modules list;
   - power key: keep `gts7xl-powerkey` (touchscreen inhibit) + Hyprland bind
     `XF86PowerOff → dpms toggle` (validated under pmOS: the DPMS script works; the physical
     press still to be confirmed by the owner);
   - `/etc/udev/hwdb.d/70-bt-keyboard-esc.hwdb` (Esc on Fn+`);
   - polkit rules (wheel: NetworkManager, power), sshd key-only drop-in, the owner's public key;
   - console: kmscon optional (Omarchy uses getty + its own login flow; keep getty on tty2+);
   - sysctl console quietness; no zram module in our kernel (Omarchy's zram setup disabled).
7. **Omarchy overrides for this tablet** (in `~/.config`, Omarchy's user-override places):
   - `monitor = DSI-1, 2800x1752@120, 0x0, 2` (scale 2 validated under pmOS Hyprland);
   - touchscreen: `input { touchdevice { output = DSI-1 } }` (the kernel DT already rotates);
   - **keyboard `kb_layout = us`** (the BT keyboard is QWERTY; Omarchy's installer may pick the
     host's fr) and **mod key ALT** instead of Super (the keyboard has no Super key): override
     Omarchy's `$mainMod`/bindings in its user bindings file;
   - an on-screen keyboard (wvkbd, toggle from the bar) since login and first setup happen by touch;
   - `misc:vfr = true` (command-mode panel).
8. **Users and access**: user `tarpediem` (groups wheel, video, render, input), password set
   by the owner on the device (never in the repo or logs); SSH key login; the **SSH host keys of
   the current rootfs are copied** so known_hosts stays valid. Hostname as now.
9. **Image**: `truncate` a ~12 GiB file, GPT with 4096-byte sectors, two partitions as in
   section 2, `mkfs.ext2 -U <boot uuid> -L pmOS_boot`, `mkfs.ext4 -U <root uuid> -L pmOS_root`,
   copy the tree (`tar --numeric-owner --xattrs --acls`), `/etc/fstab` by UUID. Output
   `build/omarchy/omarchy-gts7xl-<date>.img` (+ sha256). Checks before writing: partition
   count 2, UUIDs = current cmdline, `/sbin/init` → systemd, module dir present, firmware files
   present, a `systemd-nspawn`/qemu chroot boot to `multi-user` passes `systemd-analyze verify`.

## 4. Writing and first boot

- `tools/write-userdata.sh build/omarchy/<image>` from the debug shell (RECOVERY r15, Vol Up +
  Power) exactly as for `rootfs-r15.img` (read-back sha256 check). First boot: the initramfs grows
  `pmOS_root` to the whole USERDATA (as on r15).
- Then reboot normally (BOOT r19). Expected: getty or Omarchy's login on tty1, Hyprland with
  freedreno (same Mesa path as validated under pmOS).

## 5. Risks and open points

- Omarchy's aarch64 repo may not carry every x86 package (some apps x86-only); the build script
  logs what was skipped. hyprland-guiutils is packaged there (missing on Alpine).
- Omarchy's update path (`omarchy-update`) assumes limine/UKI: must be neutralised (step 3.4) and
  re-checked after each Omarchy update.
- systemd version/units differ from pmOS: the pmOS initramfs expects nothing from the rootfs
  except `/sbin/init`; verified on r15 with pmOS only.
- Audio work (separate agent) targets pmOS; its device files must be ported too.
- No accelerometer (only PMIC ADCs under IIO): no auto-rotation.
- qemu-user builds are slow (hours for the full package set); acceptable, one-off.

## 6. Backup before wiping (required)

Over SSH, as root, to `build/backup-pmos-<date>/` (local only, 700, never committed):
`/home/<user>`, `/etc` (NetworkManager connections hold the Wi-Fi key: keep root-only),
`/usr/lib/modules`, `/lib/firmware/qcom/sm8250/samsung`, `/var/lib/bluetooth`,
SSH host keys, the list of installed packages, and a full `tar` of the pmOS root (~3 GB used).
Rollback: `tools/write-userdata.sh build/rootfs-r15.img` then restore the tar (or just the tar
onto a freshly written r15 image).

## 7. Order of work

1. Download the aarch64 ISO, verify SHA256, extract pacman.conf/keyring/package lists. Report.
2. Build the rootfs and image on the host (no tablet access).
3. Backup of the pmOS rootfs (tablet lock, read only).
4. Owner go → write USERDATA, first boot, validate (GPU, touch, BT keyboard, Wi-Fi, charger
   line in dmesg, power key), screenshots to `build/gui/`.

## 8. Decisions (owner, 2026-11-17) and what the build does

- v1 = ext4, no LUKS, no snapshots. **Phase 2: LUKS** with an on-screen keyboard in the
  initramfs (unl0kr, buffybox family): the BT keyboard is not available that early.
- Text consoles: kmscon (us layout, JetBrainsMono Nerd Font 20) on tty2+ (`autovt@` →
  `kmsconvt@`); SDDM autologin into the Omarchy session on tty1.
- English (`LANG=en_US.UTF-8`), us keyboard; the BT keyboard's left Alt acts as Super
  (`kb_options = altwin:swap_lalt_lwin` on that device only) so Omarchy's Super bindings work.
- Kernel: our `linux-gts7xl` package (arch/linux-gts7xl), Arch kernels in `IgnorePkg`. It
  ships the modules and the matching BOOT image (built on the host by
  `tools/build-recovery-shim.sh`); its pacman hook `90-gts7xl-boot.hook` runs
  `gts7xl-write-boot`, which writes BOOT from the tablet (sha256 check, Android header check,
  backup of the old BOOT in /var/lib/gts7xl, read-back, restore on mismatch). **Dry run
  unless `WRITE_BOOT=yes` in /etc/gts7xl/write-boot.conf.** RECOVERY is never written by it
  and stays on a known-good kernel (Vol Up + Power).

What the ISO gave: `arch/aarch64/omarchy-root.img.zst` is the installed system as a btrfs
image (subvolume `omarchy-root`); the installer (`/usr/share/omarchy-iso/orchestrator`) writes
it, then runs `omarchy-apply-system --install-user U --first-install` (root) and
`omarchy-provision-user --force --first-install` (user). `tools/build-omarchy-rootfs.sh` does
the same in a qemu-user chroot, inside a private mount namespace (stage / setup / device /
image), with these deviations:
- repos: Omarchy's `pacman-stable.conf`; no `-Syu` (today's repos are past the 4.5.0 snapshot:
  openssl 4, aquamarine 0.16 under the pinned hyprland 0.56). linux-firmware-qcom and
  vulkan-freedreno from the ISO's offline repo (same snapshot); kmscon from the ALARM mirror
  (Omarchy's stable mirror lists it but returns 404), signatures checked; squeekboard online.
  The online package set therefore must be re-checked before the first `omarchy-update`.
- removed: linux-omarchy (+headers), limine, limine-mkinitcpio-hook, limine-snapper-sync;
  mkinitcpio pacman hooks masked.
- Omarchy install steps skipped in the build: `config/snapper.sh` (no btrfs), `config/firewall.sh`
  (ufw cannot reach the kernel through qemu: runs on the first boot, `gts7xl-firstboot.service`,
  SSH allowed first), and every hardware script except network, wireless regdom and bluetooth
  (Omarchy detects the build host: it tried to install the host's NVIDIA driver).
- Hyprland config is Lua in Omarchy 4.5: overrides in `~/.config/hypr/gts7xl.lua`, required
  last from `hyprland.lua`.
- The pmOS initramfs needs nothing from the root but `/sbin/init`; p1 (`pmOS_boot`) is the
  tablet's current boot filesystem byte-for-byte content (from the backup).

Host safety: a chroot teardown with shared rbind mounts unmounts the host's /sys and /dev
submounts. The script now runs in `unshare --mount --propagation private`, makes the chroot
rprivate and tears down with `umount -R` only. Separately, host mounts re-created by hand while
pmbootstrap chroots exist propagate into their `/sys` binds, and pmbootstrap's own teardown
then removes them from the host again (seen 21:23 and 21:24): re-created host mounts must be
made private (`mount --make-private`).
