# Iterating over USB: kexec and module push

From kernel 7.3.4-r12 on, a new kernel, DTB or initramfs can be booted from the pmOS debug
shell with kexec (from r10 on, the touchscreen module can be replaced in place), all over the USB
network. Flashing RECOVERY (Download Mode, heimdall) is only needed when kexec is not
enough (see "Limits").

**The running kernel does the jump, so it must be r12 or later** (`uname -v` = `#13-…` or
higher). r10 and r11 oops in `machine_kexec()` on `kexec -e` (see "kexec -e oops on r10/r11"
below): boot an r12+ RECOVERY through Download Mode once, then kexec from there.

Prerequisites: the tablet runs an r12+ image in the debug shell (`telnet 172.16.42.1`),
The host has 172.16.42.2 on the USB RNDIS link, `python3`, `dtc` (`fdtget`/`fdtput`),
`zstd`. Artefacts come from `pmbootstrap export build/` (see the build steps in NOTES.md).

## What the image provides

- `CONFIG_KEXEC=y`, `CONFIG_KEXEC_FILE=y`, no `KEXEC_SIG`, lockdown off: unsigned Images load.
- r12+: `machine_kexec()` is `__nocfi` (kernel patch 0018), required with `CONFIG_CFI=y`.
- `kexec` (Alpine `kexec-tools`) in the initramfs (`device-samsung-gts7xl`: dependency and
  `30-gts7xl.files`).
- `stmfts1b` (touchscreen) built as a module, shipped in the initramfs (`30-gts7xl.modules`),
  blacklisted for udev there (`/etc/modprobe.d/gts7xl-initramfs.conf`, initramfs only) and
  loaded by the hook `50-gts7xl-modules.sh` in the background once telnetd runs (or after
  30 s), then buffyboard is restarted to pick up the new input device. `gts7xl.nomodules`
  on the command line skips it.
- Power key (r11+): hook `60-gts7xl-powerkey.sh`, a short press (< 3 s) toggles the display
  (`fb0/blank`) and the touchscreen (`inhibited`); `gts7xl.nopowerkey` disables it.
- Built in on purpose (the debug shell must come up even if a module breaks): display
  (msm, panel), UFS, USB, regulators, geni-i2c and GPI DMA. geni-i2c drives i2c0, where the
  initramfs switches the USB data lines through the MAX77705 MUIC; GPI DMA is listed in
  i2c0's `dmas`, so fw_devlink makes i2c0 wait for it — as a module it would delay or stop USB.

## kexec a new build

    tools/kexec-push.sh                     # build/vmlinuz, build/dtbs/…dtb, build/initramfs
    tools/kexec-push.sh --append gts7xl.nomodules
    tools/kexec-push.sh --no-exec           # load only, then `kexec -e` in the shell
    tools/kexec-push.sh --dry-run           # print the steps, contact nothing
    tools/kexec-push.sh --force             # skip the running-kernel check (r12+ only!)

What it does:

0. refuses if `uname -v` on the tablet is older than `#13` (r12), unless `--force`;
1. pulls `/sys/firmware/fdt` (the DTB the running kernel booted with: the shim filled its
   `/memory` from the ABL's DTB);
2. `tools/kexec_dtb.py`: copies that `/memory` `reg` into the new DTB — the shim does not
   run under kexec, and the mainline DTB's `/memory` is only a placeholder;
3. pushes the decompressed Image, the patched DTB and the initramfs to `/tmp/kx` (RAM) with
   `tools/usbsh.py push` (one-file HTTP server here, busybox `wget` there, sha256 checked);
4. `kexec -c -l /tmp/kx/Image --dtb=/tmp/kx/kexec.dtb --initrd=/tmp/kx/initramfs --reuse-cmdline`
   (or `--command-line=…` / `--append=…`): kexec fills `/chosen` (bootargs, initrd range).
   `-c` forces the kexec_load syscall: kexec-tools 2.0.32 otherwise picks kexec_file_load,
   which on arm64 ignores `--dtb` and hands the new kernel the running tree (until r13 every
   kexec silently booted the old DTB; harmless only while the DTS did not change);
   run with a 300 s usbsh timeout (it took more than 30 s once with a 50 MB Image), then
   checks `/sys/kernel/kexec_loaded` = 1;
5. `kexec -e`, detached from the telnet session: `( trap '' HUP; exec setsid sh -c 'sleep 2;
   sync; exec kexec -e' ) … & true`. A plain `&` job dies when usbsh closes the connection.
   The USB link drops and comes back with the new kernel.

By hand (owner present), after `--no-exec`:

    tools/usbsh.py run "( trap '' HUP; exec setsid sh -c 'sleep 2; sync; exec kexec -e' ) </dev/null >/dev/null 2>&1 & true"

If the jump fails, the old kernel panics (`oops=panic panic=5`) and reboots through the normal
boot path; read the reason back with
`tools/usbsh.py pull /sys/fs/pstore/dmesg-ramoops-0 build/…` (keep it out of git: serials).

`kexec -s` (kexec_file_load) is not an alternative: on arm64 the kernel builds the new DTB
from the running one (no `--dtb`), so DTS changes are lost, and it ends in the same
`machine_kexec()` anyway. Use `kexec -l --dtb` as above.

### kexec -e oops on r10/r11 (kCFI)

First real attempt (r10, `#11`): `kexec -l` OK (`kexec_loaded` = 1), `kexec -e` →
`Unable to handle kernel paging request at virtual address <kern_reloc - 4>`, level 3
translation fault, `pc : machine_kexec+0x12c`, then panic and reboot. In the r10 Image,
+0x12c is `ldur w16, [x8, #-4]` with x8 = `kimage->arch.kern_reloc`: the kCFI check of the
indirect call `kernel_reloc(kimage)` loads the type hash 4 bytes before the target. The
target is the physical address of the relocation page, mapped only by the kexec idmap in
TTBR0; the page before it is not mapped. (And the copied relocation code has no hash.)
Not a placement problem: kexec-tools only uses "System RAM" from `/proc/iomem`, the no-map
holes are excluded. Fix: `machine_kexec()` `__nocfi`, as `swsusp_arch_resume()` already is
(upstream master still has the bug). r12's Image has `ldr x8, [x19, #0x310]; blr x8` there.

## Wi-Fi and Bluetooth (QCA6390, kernel r13 / device r9 on)

The modules hook loads, after the touchscreen: `pwrseq_qcom_wcn` (QCA6390 PMU),
`pci_pwrctrl_pwrseq` (the builtin PCIe controller defers until this is bound, then trains
the link), `ath11k_pci`, `qrtr_mhi`, `hci_uart`. `gts7xl.nowireless` on the command line
skips them (`gts7xl.nomodules` skips everything). Firmware: linux-firmware
`ath11k/QCA6390/hw2.0/{amss,m3,board-2}.bin` and `qca/htbtfw20.tlv`, `qca/htnv20.bin`.

    tools/usbsh.py run 'iw dev; ls /sys/class/bluetooth'
    tools/usbsh.py run 'ip link set wlan0 up; iw dev wlan0 scan passive | grep -c "^BSS "'
    # hci0 starts "unconfigured" (no BD address): give it a random one, then scan
    tools/usbsh.py run 'a=$(od -An -N5 -tx1 /dev/urandom | tr -s " " ":" | sed "s/^://;s/:$//");
        btmgmt -i 0 public-addr C2:$a; btmgmt -i 0 le on; btmgmt -i 0 power on;
        btmgmt -i 0 find | grep -c dev_found'

Do not paste scan output anywhere public: it has network names and addresses.

### Stock Wi-Fi calibration (optional, local only)

The chip reports board id 0xff, so ath11k uses the generic `qmi-board-id=255` entry of
board-2.bin. The DTS asks for the variant `Samsung_gts7xl` first; to give it the stock
board data (`bdwlan.elf` from the vendor partition, not redistributable):

    tools/extract-qca6390-vendor.sh <AP_….tar.md5 of the stock firmware> build/firmware-vendor
    tools/wlan-fw-overlay.py --board-2 /usr/lib/firmware/ath11k/QCA6390/hw2.0/board-2.bin.zst \
        --bdf build/firmware-vendor/bdwlan.elf \
        --name 'bus=pci,qmi-chip-id=0,qmi-board-id=255,variant=Samsung_gts7xl' \
        -o build/wlan-overlay.cpio
    tools/kexec-push.sh --overlay build/wlan-overlay.cpio

The overlay is a plain cpio appended to the initramfs; its uncompressed `board-2.bin`
is found before the package's `board-2.bin.zst`. Keep it in `build/` (ignored by git).

## Replace the touchscreen module

    tools/module-push.sh --apk ~/.local/var/pmbootstrap/packages/edge/aarch64/linux-samsung-gts7xl-7.3.4-r10.apk
    tools/module-push.sh --ko path/to/stmfts1b.ko[.zst]
    tools/module-push.sh --dry-run --ko …

Pushes the (decompressed) `.ko` to `/tmp`, `rmmod stmfts1b; insmod /tmp/stmfts1b.ko`, prints
the last dmesg lines. The vermagic release must equal `uname -r`; the module must come from
the same kernel build (no MODVERSIONS: a module from another config can crash). Unsigned or
foreign-key modules load (MODULE_SIG not forced) and taint the kernel.

## Other commands

    tools/usbsh.py run 'dmesg | tail'
    tools/usbsh.py pull /sys/fs/pstore/console-ramoops-0 build/pstore.txt
    tools/usbsh.py push some.file /tmp/some.file

## Limits — when to do a real boot through RECOVERY

- kexec keeps the hardware state the old kernel left: regulators, GDSCs, clocks, the panel
  (msm resets MDSS, the panel driver resets the panel on first enable), the touch IC, the
  MUIC switch, GPI channels. A bug that only shows from a cold bootloader state (or that a
  previous kernel hid) needs a real boot. When in doubt, flash RECOVERY and boot it.
- `kexec -e` takes the secondary CPUs down through PSCI CPU_OFF; if the Samsung firmware
  refuses, the jump hangs (reboot with Power + Vol Down).
- The new kernel gets no fresh `kaslr-seed`/`rng-seed` from the ABL.
- `oops=panic panic=5`: a crashing module still reboots the tablet (into the normal boot
  path). Use `--append gts7xl.nomodules` to come back without it.
- Command line: `--reuse-cmdline` repeats the running one, including `pmos.debug-shell` and
  the pmOS uuids.
