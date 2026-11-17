# Iterating over USB: kexec and module push

From kernel 7.3.4-r10 on, a new kernel, DTB or initramfs can be booted from the pmOS debug
shell with kexec, and the touchscreen module can be replaced in place, all over the USB
network. Flashing RECOVERY (Download Mode, heimdall) is only needed when kexec is not
enough (see "Limits").

Prerequisites: the tablet runs an r10+ image in the debug shell (`telnet 172.16.42.1`),
The host has 172.16.42.2 on the USB RNDIS link, `python3`, `dtc` (`fdtget`/`fdtput`),
`zstd`. Artefacts come from `pmbootstrap export build/` (see the build steps in NOTES.md).

## What the image provides

- `CONFIG_KEXEC=y`, `CONFIG_KEXEC_FILE=y`, no `KEXEC_SIG`, lockdown off: unsigned Images load.
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

What it does:

1. pulls `/sys/firmware/fdt` (the DTB the running kernel booted with: the shim filled its
   `/memory` from the ABL's DTB);
2. `tools/kexec_dtb.py`: copies that `/memory` `reg` into the new DTB — the shim does not
   run under kexec, and the mainline DTB's `/memory` is only a placeholder;
3. pushes the decompressed Image, the patched DTB and the initramfs to `/tmp/kx` (RAM) with
   `tools/usbsh.py push` (one-file HTTP server here, busybox `wget` there, sha256 checked);
4. `kexec -l /tmp/kx/Image --dtb=/tmp/kx/kexec.dtb --initrd=/tmp/kx/initramfs --reuse-cmdline`
   (or `--command-line=…` / `--append=…`): kexec fills `/chosen` (bootargs, initrd range);
5. `kexec -e` in the background; the USB link drops and comes back with the new kernel.

`kexec -s` (kexec_file_load) also works for a new kernel or initramfs with the *same* DTB:
on arm64 it reuses the running kernel's DTB, so DTS changes need `kexec -l --dtb` as above.

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
