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
- end of the image (attempt A) = the shape of the Magisk-patched BOOT this bootloader already
  boots: the 16 bytes `SEANDROIDENFORCE` right after the last section, an AVB footer whose
  original size is the end of that trailer, and the stock recovery's vbmeta blob at its stock
  offset (so One UI still verifies the recovery chain exactly as before);
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

### 1b. Does a log in RAM survive a reset? (pstore test, before any flash)

Everything we can learn from a failed boot is read from ramoops (`0x9fa00000`, 1 MiB) by One UI
afterwards (step 7). That only works if the reset in between keeps the RAM contents. Measure it
now, on the untouched tablet. The test writes a text marker into the stock kernel's own log
buffers; nothing on storage is written.

```sh
adb -s <serial> shell su -c 'ls -la /dev/pmsg0 /sys/fs/pstore; cat /proc/reset_reason 2>/dev/null'
M=marker-$(date +%s); echo $M
# keeps writing the marker (Android logs share the 256 KiB pmsg buffer and would push it out)
adb -s <serial> shell su -c "while :; do echo $M > /dev/pmsg0; echo $M > /dev/kmsg; sleep 1; done"
```

**Test W, forced reset** (the exit from a hang, step 6): while the loop runs, hold
**Vol Down + Power** about 7 s until the screen goes black, release. One UI boots. Then:

```sh
adb -s <serial> shell su -c 'ls -la /sys/fs/pstore; cat /proc/reset_reason 2>/dev/null'
adb -s <serial> exec-out su -c 'cat /sys/fs/pstore/pmsg-ramoops-0'    | grep -a -c "$M"
adb -s <serial> exec-out su -c 'cat /sys/fs/pstore/console-ramoops-0' | grep -a -c "$M"
```

**Test R, plain reboot**: new marker, same loop, then from another terminal
`adb -s <serial> reboot`, and the same three commands.

Write both results (the two counts, the reset reason) in `NOTES.md`.

| Result | What it means for the flash |
|---|---|
| W: marker found | a warm reset keeps ramoops, and One UI decodes it. Our kernel reboots warm by itself after a panic or a stuck CPU (see step 5), so that log will be readable |
| W: marker **not** found | One UI does not show the previous boot's log at all: step 7 cannot prove anything. Stop and tell the agent before flashing (ramoops layout or ECC to recheck) |
| R: marker found / not found | tells whether the reset type the stock kernel picks for a normal reboot keeps RAM; one more data point, not a condition |

Limit of test W: under One UI the key combo is caught by the stock power-key driver about
6.7 s in, and it does a warm reset. Under our kernel nobody catches it, and the PMIC does its
own **hard** reset about 1 s later (stage 2 of the Vol Down + Power reset is configured as a
hard reset in the stock device tree); RAM is then powered off for a moment. So after a
**forced** reset out of our kernel an empty pstore proves nothing. This is why step 6 says to
wait for the kernel's own reboot first.

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
| Green bar, then nothing changes, tablet reboots by itself or hangs | the kernel started and died before the display driver: **wait 60 s** for it to reboot by itself, then read pstore (step 7) |
| Kernel text on the screen | mainline is running (`simple-framebuffer` + `console=tty0`) |
| Kernel text, then the screen goes black after a few seconds | most likely the kernel switched the display clocks/power off once all drivers were loaded (nothing holds the display yet); Linux is still running: use the debug shell over USB. For the next image: `clocks`/`power-domains` on the simple-framebuffer node |
| Tablet reboots to One UI by itself, 10-40 s after the green bar | a panic, an oops or a stuck CPU: the kernel rebooted warm on purpose, the log is in pstore (step 7) |
| postmarketOS debug shell text on screen | the initramfs is up and waiting |

A coloured screen (shim) never ends by itself: hold Vol Down + Power 7 s (step 6).

A hang **after the green bar** usually does end by itself. The command line has
`panic=5 oops=panic softlockup_panic=1 nmi_watchdog=panic reboot=warm`: an oops, or a CPU
stuck for 20 s (10 s with interrupts off), becomes a panic, and 5 s later the kernel does a
**warm** reset, which keeps the log in RAM. So with a frozen screen, wait a full minute
before touching the keys; only then force the reset. What is not covered: all CPUs dead at
once, or a hang before the kernel's timers run. The hardware watchdog is not armed by us
(what this firmware does when it fires is not known yet).

### The debug shell over USB

The initramfs sets up a USB network gadget (`18d1:d001`, NCM, plus a serial port), then the
hook `00-gts7xl-usb-muic.sh` switches the tablet's USB data lines to the SoC (they go through
the MAX77705 MUIC, which the bootloader leaves open), then it enters the debug shell
(`pmos.debug-shell`).

The hook waits for the hardware: it polls once a second, for up to **30 s**, for the i2c bus
of the MAX77705 and for the USB controller, and if the initramfs found no controller at its
own (single) try, the hook creates and binds the gadget and starts the DHCP server itself.
So the USB device can show up on the host as late as about 35 s after the kernel text
appears, and the debug shell prompt on the screen only comes after the hook. Each step is
logged with the prefix `gts7xl-usb-muic:` (in `dmesg`, so also in pstore). On the host:

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
dmesg | grep -iE "PS_HOLD|wdt|watchdog|lockup|ramoops|pstore"
cat /proc/sys/kernel/softlockup_panic /proc/sys/kernel/hardlockup_panic /sys/kernel/reboot/mode
ls /sys/class/watchdog/ /sys/fs/pstore
cat /sys/kernel/debug/devices_deferred
ls /dev/disk/by-partlabel 2>/dev/null || cat /proc/partitions    # UFS seen?
```

Nothing is mounted and nothing on UFS is written: without a root filesystem in USERDATA the
initramfs has nowhere to go (`pmos_continue_boot` would stop with "boot partition not found").
No USB device on the host does not mean Linux is down: check the screen, then pstore.
To get the log of a boot that had no USB: type nothing (no input device), wait until the
debug shell text is on the screen, note the time, then leave with step 6. The forced reset
will probably lose the log (step 1b); write down what the screen showed instead.

`dmesg` must show `PS_HOLD reset type set to warm (reboot=warm)` (kernel patch 0003: the PMIC
is told once, at the power-key driver's probe, that the next reset is a warm one, because a
panic restarts without going through the code that normally sets it). If the line is missing,
a panic may reboot cold and lose its log.

Write the result in `NOTES.md` under the flash entry (time to each event, exact screen text).

## 6. Back to One UI

From the debug shell, prefer `reboot` (telnet or serial): it is a warm reset and keeps the log.

From a frozen screen after the green bar: first wait one minute for the kernel's own warm
reboot (step 5).

Otherwise hold **Vol Down + Power** about 7 s (up to 10 s from our kernel) until the screen
goes black, release everything. The tablet boots BOOT (One UI). This works from our Linux,
from a hang, from a coloured shim screen and from Download Mode. Out of our kernel this is a
hard reset: RAM, and with it the log, is probably lost (step 1b).

## 7. Read the previous kernel log from One UI

Boot One UI **directly** after the failed Linux boot (no power-off in between: the log
lives in RAM at `0x9fa00000`, 1 MiB).

```sh
adb -s <serial> shell su -c 'ls -la /sys/fs/pstore'
adb -s <serial> exec-out su -c 'cat /sys/fs/pstore/console-ramoops-0' > build/pstore-console-$(date +%H%M).txt
adb -s <serial> exec-out su -c 'cat /sys/fs/pstore/dmesg-ramoops-0'   > build/pstore-dmesg-$(date +%H%M).txt
adb -s <serial> shell su -c 'cat /proc/reset_reason /proc/reset_summary 2>/dev/null'
```

`pstore-console` holding lines of a 7.3 kernel proves our kernel ran. How to read an empty
`/sys/fs/pstore` depends on how the tablet got back to One UI:

- it rebooted **by itself** (warm reset): nothing was recorded, the kernel never got as far
  as pstore (green bar seen or not tells whether the shim handed over);
- the reset was **forced** with the keys: no conclusion, a hard reset loses RAM (step 1b).

A panic log starts with `Kernel panic - not syncing:`; a stuck CPU shows as
`watchdog: BUG: soft lockup` or `Watchdog detected hard LOCKUP` just before it.

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

If One UI no longer boots (should not happen in this runbook: BOOT and DTBO are never written
here; once BOOT holds Linux, follow `rootfs-on-userdata.md` section 8 instead):

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
