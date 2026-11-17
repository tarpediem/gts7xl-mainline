# Root filesystem on USERDATA — gts7xl (SM-T976B)

> From r15 on, BOOT holds Linux too (section 4): a normal power-on boots postmarketOS.

Goal: boot past the initramfs debug shell into a real postmarketOS root filesystem on the
tablet's UFS, in the **USERDATA** partition. **This erases One UI's data** (photos, apps,
accounts). EFS and the modem partitions are not touched (and are backed up). The owner
runs every command that writes to the tablet; nothing here is run by an agent.

## 0. Layout: pmOS subpartitions inside userdata

The image from `pmbootstrap install --no-split --sector-size 4096` is a small disk: its own
GPT (4096-byte sectors, header at byte 4096) with `pmOS_boot` (ext2) and `pmOS_root`
(ext4). It is written raw to the start of userdata (`sda37`). This is the standard
postmarketOS layout for Android devices; postmarketos-initramfs 3.12 handles it:

- `mount_subpartitions` scans every partition (including `/dev/disk/by-partlabel/userdata`),
  counts the partitions in it with `fdisk -l`, and when there are exactly two, attaches it
  with `losetup -P --direct-io=on --sector-size $deviceinfo_rootfs_image_sector_size`
  (4096 here: the UFS logical block size; a 512-byte image would show no partitions);
- the root and boot filesystems are then found by `pmos_root_uuid` / `pmos_boot_uuid` from
  the command line (the UUIDs of this image, written into `boot.img` by mkinitfs and kept by
  `tools/sign_boot.py`): **the RECOVERY image and the userdata image are a pair**;
- on the first boot `resize_root_partition` grows `pmOS_root` to the end of userdata
  (`parted resizepart 2 100%`, which also moves the backup GPT) and `resize2fs` follows.

Formatting userdata directly as one ext4 would need the `pmos.stowaway` path and a hand-made
fstab; not used.

What is in the image (pmbootstrap config `ui = console`, `ssh_keys = True`,
`ssh_key_glob = ~/.ssh/gts7xl_ed25519.pub`, hostname `gts7xl`):

- console UI (getty on tty1), systemd, NetworkManager + wpa_supplicant, `iw`, nftables;
- sshd, key only: `device-samsung-gts7xl-sshd-keyonly` (`PasswordAuthentication no`,
  `KbdInteractiveAuthentication no`, `PermitRootLogin no`); the public key
  `~/.ssh/gts7xl_ed25519.pub` of the build host is in the user's `authorized_keys`;
  the private key stays on the host;
- the user's password (console login, sudo) is random, kept outside the repository by the
  maintainer; change it after the first login (`passwd`);
- USB networking as in the debug shell: the initramfs sets up the gadget and
  `172.16.42.1`, `unudhcpd@usb0` in the root filesystem keeps serving `172.16.42.2`;
- Bluetooth: `device-samsung-gts7xl-bluetooth` = bluez (`bluetoothd`, `bluetoothctl`,
  enabled at boot), `hidp` and `uhid` loaded at boot (`/usr/lib/modules-load.d`) for
  keyboards, and `gts7xl-bt-addr.service` (see 6);
- Wi-Fi/BT firmware and the board modules as in the debug shell. The initramfs hook
  `50-gts7xl-modules.sh` no longer loads them on a normal boot: the root filesystem's udev
  does (the udev blacklist is initramfs only).

The command line no longer has `pmos.debug-shell` (device package r10); see 5 for the ways
back to the debug shell.

## 1. Build

Every pmbootstrap call through `ssh localhost`, udiskie paused during the install:

```sh
pmbootstrap build --force -i -n device-samsung-gts7xl
pmbootstrap config ssh_keys True
pmbootstrap config ssh_key_glob '~/.ssh/gts7xl_ed25519.pub'
pkill -STOP -f '^/usr/bin/python /usr/bin/udiskie'
pmbootstrap -y zap && pmbootstrap install --no-split --no-sparse --sector-size 4096 \
    --add device-samsung-gts7xl-sshd-keyonly,device-samsung-gts7xl-bluetooth \
    --password "$(cat <password file>)"
pkill -CONT -f '^/usr/bin/python /usr/bin/udiskie'
pmbootstrap export build/
cp --sparse=always build/samsung-gts7xl.img build/rootfs-rNN.img   # raw, not Android sparse
sha256sum build/rootfs-rNN.img
tools/build-recovery-shim.sh            # RECOVERY and BOOT with the same UUIDs on their cmdline
```

`build/samsung-gts7xl.img` is a symlink into the pmbootstrap chroot: a later `zap` or
`install` replaces it, hence the copy. Check the pair: the `pmos_root_uuid` printed by
`build-recovery-shim.sh` must be the ext4 UUID of the image's second partition.
Archive the two flashable outputs under their sha256 prefix:
`build/archive/recovery-shim-rNN-<sha8>.img` and `build/archive/boot-shim-rNN-<sha8>.img`.

## 2. Write USERDATA (debug shell, over USB)

The tablet runs a debug-shell image (RECOVERY r12-r14, or kexec) and `telnet 172.16.42.1`
works. Nothing on userdata may be in use (the script refuses otherwise).

```sh
tools/write-userdata.sh --dry-run --image build/rootfs-r15.img --expect-sha256 <sha256>
tools/write-userdata.sh --image build/rootfs-r15.img --expect-sha256 <sha256>
```

The script finds the one partition with `PARTNAME=userdata`, checks that it is on `sda`, has
4096-byte blocks, is not read-only, mounted, swap or held by loop/dm, is larger than the
image and starts where the PIT says USERDATA starts (`build/gts7xl.pit`), prints the plan
and waits for the word `ERASE-USERDATA`. Then it checks the target again, serves the image
from the host (`tools/serve_file.py` on 172.16.42.2) and runs on the tablet, detached from
telnet:

    wget -O - http://172.16.42.2:<port>/f | dd of=/dev/sda37 bs=4M conv=fsync

It polls until dd ends, checks the byte count, drops the page cache, reads the image length
back from the partition, compares sha256 and logs the result to NOTES.md (exit 3 on a
mismatch). Over USB 2 RNDIS expect a few minutes for ~1.4 GB.

Alternative without the network: `tools/flash.sh --allow-userdata --pit build/gts7xl.pit
--keep-vbmeta USERDATA=build/rootfs-r15.img` in Download Mode (heimdall writes the same
bytes; no read-back).

## 3. Boot it by kexec first (RECOVERY unchanged)

Still in the debug shell, boot the same kernel with the image's own command line (no
`pmos.debug-shell`, the new UUIDs):

```sh
cmd=$(python3 -c 'import sys; sys.path.insert(0, "tools"); import sign_boot; print(sign_boot.get_cmdline(open("build/boot.img", "rb").read()))')
tools/kexec-push.sh --dry-run --cmdline "$cmd"
tools/kexec-push.sh --cmdline "$cmd"
```

The USB link drops; the initramfs finds the subpartitions, resizes `pmOS_root` (first boot
only, can take a minute on 226 GiB), switches root, and the link comes back with sshd:

```sh
ssh -i ~/.ssh/gts7xl_ed25519 -o IdentitiesOnly=yes <user>@172.16.42.1
```

Known kexec limit: if Wi-Fi was up in the previous kernel, the QCA6390 does not come back
after kexec (NOTES.md, r14 caveat); Wi-Fi and Bluetooth need a real boot (step 4) or a
previous kernel with the wireless modules never loaded (`--append gts7xl.nowireless` on the
kexec that led to it). The screen shows the getty login on tty1.

If it does not come up: wait for the USB link; a failed root mount drops into the debug
shell (telnet works again). `oops=panic panic=5` turns a crash into a reboot into
RECOVERY (still the debug-shell image).

## 4. Flash the matching RECOVERY and BOOT

Once the kexec boot works, make it the real boot. RECOVERY and BOOT are written together, in
one heimdall command, both with the same kernel slot (boot shim), initramfs and command line:

| Partition | Image (r15) | sha256 |
|---|---|---|
| RECOVERY | `build/archive/recovery-shim-r15-59538de5.img` | `59538de5022a9d1dfcd0c201de334266d42dcf5cc11d5e42d969f3f15dc6c505` |
| BOOT | `build/archive/boot-shim-r15-eba2068f.img` | `eba2068f68d3359be75544008c0322fd81bae276fa512b245479ebea6ea94535` |

Download Mode (Vol Down + Vol Up, then USB), then:

```sh
tools/flash.sh --dry-run --keep-vbmeta --pit build/gts7xl.pit \
    RECOVERY=build/archive/recovery-shim-r15-59538de5.img BOOT=build/archive/boot-shim-r15-eba2068f.img
tools/flash.sh --keep-vbmeta --pit build/gts7xl.pit \
    RECOVERY=build/archive/recovery-shim-r15-59538de5.img BOOT=build/archive/boot-shim-r15-eba2068f.img
```

The dry run must print exactly one command,
`heimdall flash --RECOVERY <recovery> --BOOT <boot> --no-reboot` (no VBMETA, DTBO or USERDATA).

**A normal power-on (Power alone) now boots Linux**, and so does off-mode charging (plugging
the charger into a powered-off tablet starts BOOT: Linux comes up instead of the charging
animation). One UI is gone from the tablet; Android's `fs_mgr` no longer runs, so nothing
formats userdata behind our back. Vol Up + Power still boots RECOVERY (same Linux).

How the BOOT image is made (`tools/mkboot.py`, called by `build-recovery-shim.sh`):

- header v2 fields of the stock `boot.img` (addresses, OS version, board name), the pmOS
  command line and the same xz initramfs as RECOVERY r15;
- kernel slot = the boot shim (`build/shim-Image`); dtb = the stock **boot.img**'s dtb byte
  for byte; no recovery_dtbo section. On a normal boot the ABL applies the overlays of the
  DTBO partition (left stock) to that dtb; the shim only takes `/memory`, the command line
  and the ramdisk location from it;
- AVB as on the Magisk BOOT that already boots on this tablet: `SEANDROIDENFORCE` after the
  last section, footer `original_image_size` = end of that trailer, stock vbmeta blob byte
  for byte; the stock vbmeta partition stays as it is (`--keep-vbmeta`);
- size: BOOT (71303168 bytes) is ~16 MB smaller than RECOVERY. Kernel slot 51.4 MB +
  initramfs 15.2 MB + dtb 1.6 MB = 68198416 bytes with the trailer: past the stock vbmeta
  blob offset (56000512) and the stock hashed size (55996944). So the blob moves to the first
  4096-byte boundary after the image (68202496), exactly as magiskboot does (the Magisk BOOT
  has it at 56143872, and its dtb ends 142832 bytes past the stock hashed size). With an
  unlocked bootloader libavb loads the whole partition, not just the hashed size
  (`avb_slot_verify.c`: "Loading entire partition" when verification errors are allowed).
  Fitting under the hashed size instead would need the initramfs under ~2.9 MB (it is
  8.7 MB with no module and no firmware at all): not done.

If BOOT does not start Linux (blocked, bootloop, black screen): Vol Down + Power 7 s, then
Vol Up + Power for RECOVERY (still Linux), or Download Mode and flash `build/stock/boot-magisk.img`
back to BOOT. Do **not** let One UI boot while pmOS is on userdata (see 8).

## 5. Back to the debug shell

- Hold **Volume Down** while the initramfs runs its hooks (a few seconds after the
  Samsung logo): `check_keys` drops into the debug shell, `telnet 172.16.42.1`.
  Volume Up held at that moment makes the initramfs fail the boot on purpose, which also
  ends in the debug shell (after dumping logs): release Vol Up after the logo.
- Any failure to find or mount the root filesystem ends in the debug shell too.
- Reflash a debug-shell RECOVERY: `build/archive/recovery-shim-r14-ec0a2a64.img`
  (`pmos.debug-shell`, old UUIDs: it never looks at userdata).
- From the running root filesystem: `sudo kexec -c -l …` with
  `--append=pmos.debug-shell` (kexec-tools is in the image), as in `tools/kexec-push.sh`.

## 6. Bluetooth address and keyboards

hci0 comes up unconfigured: the QCA6390 has no BD address, stock Android keeps it in EFS,
and Linux never reads EFS. `gts7xl-bt-addr.service` (pulled in by a `bluetooth.service`
drop-in, ordered before it) waits for hci0 and sets
`btmgmt --index 0 public-addr <addr>`, with `<addr>` = first 6 bytes of
`sha256("gts7xl-bt-addr:" + /etc/machine-id)`, first octet made locally administered and
unicast. `/etc/machine-id` is generated on the first boot of the install, so the address is
stable across reboots (pairings survive) and changes only with a new install.

Pair a keyboard over SSH:

```sh
bluetoothctl
  power on
  agent on
  default-agent
  scan on            # wait for the keyboard, then
  pair <MAC>         # type the PIN on the keyboard if asked
  trust <MAC>
  connect <MAC>
```

## 7. Wi-Fi in the root filesystem

No credentials are in the image. Over SSH: `nmcli device wifi connect <SSID> --ask`.
sshd also listens on wlan0 (key only); the firewall (nftables) accepts SSH on every
interface.

## 8. Restore One UI

BOOT and RECOVERY both hold Linux, userdata holds pmOS. One UI needs all three back:

1. Download Mode, flash the stock boot and the stock recovery in one command:
   `tools/flash.sh --keep-vbmeta --pit build/gts7xl.pit BOOT=build/stock/boot-stock.img RECOVERY=build/stock/recovery.img`
   (`BOOT=build/stock/boot-magisk.img` instead to keep root).
2. Boot RECOVERY right away (Vol Up + Power), **before any normal boot**, and choose
   **Wipe data/factory reset**: it formats userdata.
3. Reboot: One UI starts from BOOT as a fresh device.
   The full stock firmware (Odin/heimdall) restores everything else if needed.
