# First flash runbook — gts7xl (SM-T976B)

Goal: put our mainline image (behind a boot shim, see step 0) in **RECOVERY** and try to
boot it, while One UI keeps booting from BOOT. BOOT, DTBO and userdata are never written. The maintainer runs every
command that touches the tablet; nothing here is run by an agent.

State expected before starting: bootloader unlocked, stock T976BXXS7DXH1 + Magisk, USB
debugging on, tablet charged above 50 %.

## 0. What is flashed, and why not DTBO

| Partition | Image | Why |
|---|---|---|
| RECOVERY | `build/recovery-shim.img` (attempt A) or `build/recovery-shim-signed.img` (attempt B) | boot shim + mainline kernel + mainline DTB + initramfs, behind the **stock** DTB and overlays |
| VBMETA | untouched (A) or `tools/images/vbmeta-disabled.img` (B) | see step 4 |
| DTBO | **never** | One UI needs the stock overlays; a non-stock DTBO also fails AVB (dtbo is a chain partition of the stock vbmeta) |

Why a shim: on the Tab S7 11" the Samsung bootloader (ABL) refused every image whose DTB
was a mainline DTB ("Custom Binary Blocked By OEM Lock" after 19-26 s), from BOOT and from
RECOVERY, while a 184-byte test program booted fine with the vendor DTB. The ABL only goes
through with the vendor device tree; what sits in the kernel slot is not checked.
So the image the ABL sees is as stock as possible:

- `dtb` section = the stock recovery's DTB (4 FDTs, the first one `qcom,msm-id = <0x164 0x20001>`), byte for byte;
- `recovery_dtbo` section = the stock recovery's overlays (entry 04 = `qcom,board-id = <8 6>`), byte for byte;
- header fields = the stock boot image's; cmdline = ours;
- kernel slot = `build/shim-Image`: a small program (`tools/shim/`) that carries our mainline
  `Image` and our mainline DTB. Its Image header announces what the stock kernel announces
  (`text_offset 0x80000`, an `image_size` covering all it uses).

The ABL applies its overlay to the vendor DTB, fills in `/memory`, the command line and the
ramdisk address, and jumps to the shim with that DTB. The shim copies those values into the
mainline DTB, puts the mainline Image on a 2 MiB boundary and jumps to it. The kernel never
sees the vendor DTB. The same chain boots mainline 6.18 on the Tab S7 11"
(github.com/Iamtianyuyang/steamos-tabs7, from BOOT; here from RECOVERY).

Rebuild both candidates after every `pmbootstrap install` + `pmbootstrap export build/`:

```sh
tools/build-recovery-shim.sh        # mkshim.py, sign_boot.py, mkrecovery.py --kernel --stock-dt
```

The first flash carries no root filesystem: USERDATA is not written. The command line has
`pmos.debug-shell`, so the initramfs stops in its debug shell and waits (step 5).

`build/stock/` holds the rollback images taken from the T976BXXS7DXH1 firmware:
`recovery.img`, `vbmeta.img`, `dtbo.img`, `boot-stock.img`, `boot-magisk.img`
(the Magisk-patched boot currently on the tablet).

## 1. Pre-flight, tablet still in One UI (read-only)

Check that what is on the tablet is what we think we can restore. Each command only reads.

```sh
for p in recovery vbmeta dtbo boot; do
  adb -s <serial> exec-out su -c "dd if=/dev/block/by-name/$p bs=1M 2>/dev/null" | sha256sum
done
sha256sum build/stock/recovery.img build/stock/vbmeta.img build/stock/boot-magisk.img
```

`recovery` must equal `build/stock/recovery.img`. `vbmeta` and `dtbo` are padded on the
device: compare only the first bytes (`head -c <size of the stock file>` before `sha256sum`).
If `recovery` or `vbmeta` differ from stock, stop: keep the device copies as the rollback
images instead (save them under `build/device/`).

## 2. Download Mode

1. Power the tablet off completely (unplug USB).
2. Hold **Vol Up + Vol Down** together and plug the USB cable from the host. Keep holding
   until the blue warning screen.
3. **Short** press **Vol Up** to continue. The screen shows "Downloading…".
   Do not long-press Vol Up: that is the bootloader lock/unlock screen, and it erases the tablet.

The USB handshake only works on the "Downloading…" screen.

Leave Download Mode at any time without flashing: hold **Vol Down + Power** about 7 s
until the screen goes black, then release. One UI boots.

## 3. Read the PIT (once)

```sh
sudo heimdall print-pit > build/gts7xl.pit      # the tablet reboots to One UI afterwards
grep -c "^Partition Name:" build/gts7xl.pit
grep -B4 -A1 -E "^Partition Name: (BOOT|RECOVERY|DTBO|VBMETA|USERDATA|boot|recovery|dtbo|vbmeta|userdata)$" build/gts7xl.pit
```

Check by eye:

- the five names exist. `flash.sh` passes them to heimdall in the PIT's own letter case
  (upper case is expected, as on the Tab S7 FE; the GPT names are lower case);
- **block size**: BOOT is 71303168 bytes. Its "Partition Block Count" must be `17408`
  (4096-byte blocks). If it reads `139264` the PIT counts 512-byte blocks: run `flash.sh`
  with `FLASH_BLOCK_SIZE=512`. RECOVERY must come out at 86888448 bytes (`21213` blocks of 4096).

Using `print-pit` without `--no-reboot` is on purpose: the next step starts a fresh
Download session. (With `--no-reboot` the flash would need `flash.sh --resume`; a second
handshake in the same session is known to fail on this family.)

## 4. Dry run, then flash

Enter Download Mode again (step 2).

### Attempt A — RECOVERY only, vbmeta untouched (do this first)

```sh
tools/flash.sh --dry-run --pit build/gts7xl.pit --keep-vbmeta RECOVERY=build/recovery-shim.img
tools/flash.sh           --pit build/gts7xl.pit --keep-vbmeta RECOVERY=build/recovery-shim.img
```

The real run calls `heimdall detect`, lists what will be written and waits for the word
`FLASH`. It ends with the tablet still in Download Mode (`--no-reboot`) and logs the image
hashes in `NOTES.md`.

Why first: this image keeps the stock recovery's own AVB footer and vbmeta blob, so the
normal boot (One UI) verifies exactly as before. Only booting RECOVERY reports a hash
mismatch, the same kind the unlocked bootloader already accepts for the Magisk BOOT.

### Attempt B — RECOVERY + VBMETA disabled (only if A is refused by the bootloader)

```sh
tools/flash.sh --dry-run --pit build/gts7xl.pit RECOVERY=build/recovery-shim-signed.img
tools/flash.sh           --pit build/gts7xl.pit RECOVERY=build/recovery-shim-signed.img
```

Risk of B: a vbmeta with verification disabled changes how One UI boots. On Samsung
tablets this can end in "verification failed, reset the device" (factory reset of One UI).
Back up anything needed from One UI before B.

## 5. Boot RECOVERY (our Linux)

From Download Mode: hold **Vol Down + Power** about 7 s until the screen goes black, then
at once switch to **Vol Up + Power**; release both at the Samsung logo. Keep the USB cable
plugged in.

From One UI instead: `adb -s <serial> reboot recovery`.

Start a stopwatch and watch the host:

```sh
sudo dmesg -w | grep -iE "usb|cdc|rndis|ncm"      # on the host, in another terminal
```

What the screen tells, in boot order:

| What you see | Meaning |
|---|---|
| Red text "Custom Binary(recovery) Blocked By OEM Lock" or straight back to Download Mode within a few seconds | the bootloader refused the image (AVB) — try attempt B |
| Unlocked-bootloader warning, then logo, then Download Mode / block screen after about 20-30 s | the bootloader gave up even with the vendor DTB: note the exact text and time, go back to One UI |
| Stock recovery menu | RECOVERY was not written, or the key combo booted the old image: check `NOTES.md` |
| Whole screen **yellow** | shim: the bootloader did not pass a device tree |
| Whole screen **red** | shim: the bootloader put its DTB or the ramdisk inside the shim's memory window |
| Whole screen **magenta** | shim: its embedded mainline DTB is unusable |
| Whole screen **cyan** | shim: no `/memory` in the bootloader's DTB |
| **Green bar** across the top of the logo | the shim finished and jumped into the mainline kernel |
| Green bar, then nothing changes, tablet reboots by itself or hangs | the kernel started and died before the display driver: read pstore (step 7) |
| Kernel text on the screen | mainline is running (`simple-framebuffer` + `console=tty0`) |
| postmarketOS debug shell text on screen | the initramfs is up and waiting |

A coloured screen or a hang never ends by itself: hold Vol Down + Power 7 s (step 6).

### The debug shell over USB

The initramfs sets up a USB network gadget (`18d1:d001`, NCM, plus a serial port), then the
hook `00-gts7xl-usb-muic.sh` switches the tablet's USB data lines to the SoC (they go through
the MAX77705 MUIC, which the bootloader leaves open), then it enters the debug shell
(`pmos.debug-shell`). On the host:

```sh
ip -br addr | grep 172.16.42            # the new usb interface gets 172.16.42.2 by DHCP
telnet 172.16.42.1                      # root shell of the initramfs, no password
```

If the interface exists but has no address: `sudo ip addr add 172.16.42.2/24 dev <iface>`
(and `sudo ip link set <iface> up`). The gadget's serial port is the fallback:
`/dev/ttyACM0` on the host, with any serial terminal. The tablet screen shows a login
prompt too, but nothing can be typed there yet (no touchscreen driver in the device tree).

First things to save from the shell (copy the telnet output into `build/`):

```sh
dmesg                                   # full kernel log
cat /proc/cmdline; cat /proc/iomem
dmesg | grep -iE "gts7xl-usb-muic|dwc3|ufs|rpmh|deferred"
cat /sys/kernel/debug/devices_deferred
ls /dev/disk/by-partlabel 2>/dev/null || cat /proc/partitions    # UFS seen?
```

Nothing is mounted and nothing on UFS is written: without a root filesystem in USERDATA the
initramfs has nowhere to go (`pmos_continue_boot` would stop with "boot partition not found").
No USB device on the host does not mean Linux is down: check the screen, then pstore.

Write the result in `NOTES.md` under the flash entry (time to each event, exact screen text).

## 6. Back to One UI

Hold **Vol Down + Power** about 7 s until the screen goes black, release everything.
The tablet boots BOOT (One UI). This works from our Linux, from a hang and from Download Mode.

## 7. Read the previous kernel log from One UI

Boot One UI **directly** after the failed Linux boot (no power-off in between: the log
lives in RAM at `0x9fa00000`, 1 MiB).

```sh
adb -s <serial> shell su -c 'ls -la /sys/fs/pstore'
adb -s <serial> exec-out su -c 'cat /sys/fs/pstore/console-ramoops-0' > build/pstore-console-$(date +%H%M).txt
adb -s <serial> exec-out su -c 'cat /sys/fs/pstore/dmesg-ramoops-0'   > build/pstore-dmesg-$(date +%H%M).txt
adb -s <serial> shell su -c 'cat /proc/reset_reason /proc/reset_summary 2>/dev/null'
```

`pstore-console` holding lines of a 7.3 kernel proves our kernel ran. An empty
`/sys/fs/pstore` means nothing was recorded: the kernel never got as far as pstore
(green bar seen or not tells whether the shim handed over).

The stock kernel only decodes the region if our node has the same layout. The
`ramoops@9fa00000` node of `sm8250-samsung-gts7xl.dts` copies the live tree (1 MiB, record,
console, ftrace and pmsg all `0x40000`; `tests/test_dts_memory.py` compares them).

## 8. Rollback

Enter Download Mode (step 2) for each of these.

Attempt A only touched RECOVERY:

```sh
tools/flash.sh --pit build/gts7xl.pit --keep-vbmeta RECOVERY=build/stock/recovery.img
```

After attempt B, restore RECOVERY and the stock vbmeta together:

```sh
tools/flash.sh --pit build/gts7xl.pit --vbmeta build/stock/vbmeta.img RECOVERY=build/stock/recovery.img
```

If `flash.sh` reports `FAIL! Auth` / an upload error right after a blocked boot: the
Download session opened by the bootloader after a block is not trustworthy. Hold
Vol Down + Power 7 s, let One UI boot, enter Download Mode by hand again, retry.

If One UI no longer boots (should not happen: BOOT and DTBO are never written):

```sh
tools/flash.sh --pit build/gts7xl.pit --allow-dtbo --vbmeta build/stock/vbmeta.img \
    BOOT=build/stock/boot-magisk.img RECOVERY=build/stock/recovery.img DTBO=build/stock/dtbo.img
```

Last resort, full stock firmware, data kept (HOME_CSC), from `<stock-firmware>/`:

```sh
cd <stock-firmware>
sudo ./odin4 -b fw/BL_*.tar.md5 -a fw/AP_*.tar.md5 -c fw/CP_*.tar.md5 -s fw/HOME_CSC_*.tar.md5
```

This rewrites the bootloader and modem partitions too and removes Magisk; use it only if
the three commands above did not bring One UI back. Never use `CSC_*` (it wipes the tablet).
