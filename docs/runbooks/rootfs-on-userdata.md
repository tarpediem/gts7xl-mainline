# Root filesystem on USERDATA — gts7xl (SM-T976B)

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
tools/build-recovery-shim.sh            # RECOVERY with the same UUIDs on its cmdline
```

`build/samsung-gts7xl.img` is a symlink into the pmbootstrap chroot: a later `zap` or
`install` replaces it, hence the copy. Check the pair: the `pmos_root_uuid` printed by
`build-recovery-shim.sh` must be the ext4 UUID of the image's second partition.

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

## 4. Flash the matching RECOVERY

Once the kexec boot works, make it the real boot. Download Mode (Vol Down + Vol Up, then
USB), then:

```sh
tools/flash.sh --dry-run --keep-vbmeta --pit build/gts7xl.pit RECOVERY=build/archive/recovery-shim-r15-<sha8>.img
tools/flash.sh --keep-vbmeta --pit build/gts7xl.pit RECOVERY=build/archive/recovery-shim-r15-<sha8>.img
```

Boot with **Vol Up + Power**, release both when the Samsung logo shows.

**Do not boot normally (Power alone) once userdata holds pmOS.** BOOT still has One UI;
Android's `fs_mgr` formats a `formattable` userdata that it sees as wiped (no ext4/f2fs
superblock where it looks), which would erase pmOS. Off-mode charging also starts from BOOT.
Until BOOT is dealt with, start the tablet only into RECOVERY.

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

1. Download Mode, flash the stock recovery:
   `tools/flash.sh --keep-vbmeta --pit build/gts7xl.pit RECOVERY=build/stock/recovery.img`
2. Boot it (Vol Up + Power), choose **Wipe data/factory reset**: it formats userdata.
3. Reboot: One UI starts from BOOT (still the Magisk-patched stock boot) as a fresh device.
   The full stock firmware (Odin/heimdall) restores everything else if needed.
