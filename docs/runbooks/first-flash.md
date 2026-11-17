# First flash runbook — gts7xl (SM-T976B)

Goal: put our mainline image in **RECOVERY** and try to boot it, while One UI keeps
booting from BOOT. BOOT, DTBO and userdata are never written. The maintainer runs every
command that touches the tablet; nothing here is run by an agent.

State expected before starting: bootloader unlocked, stock T976BXXS7DXH1 + Magisk, USB
debugging on, tablet charged above 50 %.

## 0. What is flashed, and why not DTBO

| Partition | Image | Why |
|---|---|---|
| RECOVERY | `build/recovery-stockfooter.img` (attempt A) or `build/recovery-signed.img` (attempt B) | our kernel + initramfs + mainline DTB, with its own `recovery_dtbo` section |
| VBMETA | untouched (A) or `tools/images/vbmeta-disabled.img` (B) | see step 4 |
| DTBO | **never** | One UI needs the stock overlays; a non-stock DTBO also fails AVB (dtbo is a chain partition of the stock vbmeta) |

When the ABL boots RECOVERY with a header v2 image it reads the overlays from the image's
`recovery_dtbo` section, not from the DTBO partition. Ours holds `build/recovery-dtbo-noop.img`:
the stock table shape (8 entries, same board ids and `dtbo-version`) with overlays that
change nothing.

Rebuild the two candidates after every new `build/boot-signed.img`:

```sh
python3 tools/dtbo.py noop reference/raw/dtbo.img build/recovery-dtbo-noop.img
python3 tools/mkrecovery.py --stock-recovery build/stock/recovery.img \
    --recovery-dtbo build/recovery-dtbo-noop.img --stock-footer \
    build/boot-signed.img build/recovery-stockfooter.img
python3 tools/mkrecovery.py --stock-recovery build/stock/recovery.img \
    --recovery-dtbo build/recovery-dtbo-noop.img \
    build/boot-signed.img build/recovery-signed.img
```

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
tools/flash.sh --dry-run --pit build/gts7xl.pit --keep-vbmeta RECOVERY=build/recovery-stockfooter.img
tools/flash.sh           --pit build/gts7xl.pit --keep-vbmeta RECOVERY=build/recovery-stockfooter.img
```

The real run calls `heimdall detect`, lists what will be written and waits for the word
`FLASH`. It ends with the tablet still in Download Mode (`--no-reboot`) and logs the image
hashes in `NOTES.md`.

Why first: this image keeps the stock recovery's own AVB footer and vbmeta blob, so the
normal boot (One UI) verifies exactly as before. Only booting RECOVERY reports a hash
mismatch, the same kind the unlocked bootloader already accepts for the Magisk BOOT.

### Attempt B — RECOVERY + VBMETA disabled (only if A is refused by the bootloader)

```sh
tools/flash.sh --dry-run --pit build/gts7xl.pit RECOVERY=build/recovery-signed.img
tools/flash.sh           --pit build/gts7xl.pit RECOVERY=build/recovery-signed.img
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
sudo dmesg -w | grep -iE "usb|cdc|rndis"      # on the host, in another terminal
```

| What you see | Meaning |
|---|---|
| Red text "Custom Binary(recovery) Blocked By OEM Lock" or straight back to Download Mode within a few seconds | the bootloader refused the image (AVB) — try attempt B |
| Unlocked-bootloader warning, then logo, then Download Mode / block screen after about 20-30 s | the bootloader hung or gave up on the device tree (seen on the Tab S7 11" with a mainline DTB) |
| Logo stays, nothing on USB, tablet reboots by itself | the kernel probably started and died: read pstore (step 7) |
| New USB device `18d1:d001` / RNDIS on the host | the pmOS initramfs is up: `telnet 172.16.42.1` |
| Stock recovery menu | RECOVERY was not written, or the key combo booted the old image: check `NOTES.md` |

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
`/sys/fs/pstore` means nothing was recorded: either the kernel never started, or our
device tree has no matching `ramoops` node.

The stock kernel only decodes the region if our node has the same layout:

```dts
reserved-memory {
	ramoops@9fa00000 {
		compatible = "ramoops";
		reg = <0x0 0x9fa00000 0x0 0x100000>;
		record-size = <0x40000>;
		console-size = <0x40000>;
		ftrace-size = <0x40000>;
		pmsg-size = <0x40000>;
		no-map;
	};
};
```

(`record-size` is `0x40000` on this tablet's live tree; upstream
`sm8250-samsung-common.dtsi` uses `0x4000`, which the stock kernel would not parse.)

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
