#!/usr/bin/env bash
# Build an Omarchy (aarch64) root filesystem for the gts7xl from the official Omarchy aarch64
# ISO's prebuilt root image, with our kernel modules, firmware and device layer.
# Design: docs/omarchy-aarch64-design.md. Runs as root on the x86_64 host (qemu-aarch64 binfmt).
#
#   sudo tools/build-omarchy-rootfs.sh stage    # copy the ISO root image into WORK/root
#   sudo tools/build-omarchy-rootfs.sh setup    # pacman, user, Omarchy finalizers (chroot)
#   sudo tools/build-omarchy-rootfs.sh device   # kernel modules, firmware, device layer
#   sudo tools/build-omarchy-rootfs.sh image    # WORK/omarchy-gts7xl.img (same UUIDs as now)
#   sudo tools/build-omarchy-rootfs.sh chroot [cmd...]   # debugging shell in WORK/root
#
# Environment (defaults in brackets):
#   WORK       [build/omarchy]           work dir (root image tree, outputs)
#   ROOTIMG    [WORK/x/arch/aarch64/omarchy-root.img]  from the ISO, sha256-checked
#   BACKUP     [newest build/backup-pmos-*]  pmOS rootfs backup (host keys, ssh key, boot fs)
#   KERNEL_APK [newest linux-samsung-gts7xl apk in the pmbootstrap repo]
#   ZAP        [build/firmware-gpu/a650_zap.mbn]
#   USERNAME   [tarpediem]   PASSWORD_FILE [WORK/credentials/password] (generated, 600)
# Nothing here talks to the tablet.
set -euo pipefail

root_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
WORK=${WORK:-$root_dir/build/omarchy}
R=$WORK/root
ROOTIMG=${ROOTIMG:-$WORK/x/arch/aarch64/omarchy-root.img}
BACKUP=${BACKUP:-$(ls -d "$root_dir"/build/backup-pmos-* 2>/dev/null | tail -1)}
KERNEL_APK=${KERNEL_APK:-$(ls -v "${PMB_PACKAGES:-/home/${SUDO_USER:-tarpediem}/.local/var/pmbootstrap/packages/edge/aarch64}"/linux-samsung-gts7xl-*.apk | tail -1)}
ZAP=${ZAP:-$root_dir/build/firmware-gpu/a650_zap.mbn}
USERNAME=${USERNAME:-tarpediem}
PASSWORD_FILE=${PASSWORD_FILE:-$WORK/credentials/password}
DEV=$root_dir/arch/gts7xl-device
log() { echo "[$(date +%T)] $*"; }
[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
# Run everything in a private mount namespace: no mount or unmount made here can reach the
# host, and all of them vanish when the script exits, even if it crashes (incident
# 2026-11-17: a shared rbind teardown unmounted the host's /sys/fs/cgroup, /dev/pts...).
if [ "${GTS7XL_NS:-}" != 1 ]; then
	export GTS7XL_NS=1
	exec unshare --mount --propagation private -- "$0" "$@"
fi
[ "$(findmnt -n -o PROPAGATION -M /)" = private ] || { echo "not in a private mount namespace" >&2; exit 1; }

mounted=()
mount_chroot() {
	# The root itself must be a mount point (pacman CheckSpace, as arch-chroot does).
	mountpoint -q "$R" || { mount --bind "$R" "$R"; mounted+=("$R"); }
	# The host mounts are "shared". Without this, every mount made under $R is propagated
	# to the peer (the same path in /home), so a second copy of /sys and /dev appears there,
	# and that copy stays a peer of the host's /sys and /dev: unmounting it also unmounted
	# /sys/fs/cgroup, /dev/pts, /dev/shm... on the host (incident 2026-11-17 21:12 and 21:16).
	# Private before any submount; the rbinds below are then made slaves of the host.
	mount --make-rprivate "$R"
	for d in proc sys dev dev/pts run tmp; do mkdir -p "$R/$d"; done
	mountpoint -q "$R/proc" || { mount -t proc proc "$R/proc"; mounted+=("$R/proc"); }
	mountpoint -q "$R/sys" || { mount --rbind /sys "$R/sys"; mount --make-rslave "$R/sys"; mounted+=("$R/sys"); }
	mountpoint -q "$R/dev" || { mount --rbind /dev "$R/dev"; mount --make-rslave "$R/dev"; mounted+=("$R/dev"); }
	mountpoint -q "$R/run" || { mount -t tmpfs tmpfs "$R/run"; mounted+=("$R/run"); }
	mountpoint -q "$R/tmp" || { mount -t tmpfs tmpfs "$R/tmp"; mounted+=("$R/tmp"); }
	install -Dm755 /usr/bin/qemu-aarch64-static "$R/usr/bin/qemu-aarch64-static"
	cp -L /etc/resolv.conf "$R/run/host-resolv.conf"
	# Omarchy's /etc/resolv.conf points at systemd-resolved's stub (not running in a chroot).
	[ -e "$R/etc/resolv.conf" ] || [ -L "$R/etc/resolv.conf" ] || ln -s ../run/systemd/resolve/stub-resolv.conf "$R/etc/resolv.conf"
	mkdir -p "$R/run/systemd/resolve"
	cp "$R/run/host-resolv.conf" "$R/run/systemd/resolve/stub-resolv.conf"
}
umount_chroot() {
	local i m rc=0
	# Only what this run mounted, last first, recursively, never lazy: a lazy unmount
	# detaches whatever is busy, and on a propagating tree that reached the host.
	for ((i=${#mounted[@]}-1; i>=0; i--)); do
		mountpoint -q "${mounted[i]}" || continue
		umount -R "${mounted[i]}" || { echo "umount_chroot: cannot unmount ${mounted[i]} (busy?), left mounted" >&2; rc=1; }
	done
	mounted=()
	# The host must still have its pseudo-filesystems.
	for m in /sys/fs/cgroup /dev/pts /dev/shm; do
		findmnt -n -M "$m" >/dev/null || { echo "umount_chroot: HOST LOST $m" >&2; rc=1; }
	done
	[ "$rc" = 0 ] || echo "umount_chroot: check findmnt before doing anything else" >&2
	rm -f "$R/usr/bin/qemu-aarch64-static"
}
trap umount_chroot EXIT
in_root() { chroot "$R" /usr/bin/env -i PATH=/usr/bin:/usr/sbin HOME=/root TERM=xterm LANG=C.UTF-8 "$@"; }
as_user() {
	chroot --userspec="$USERNAME:$USERNAME" "$R" /usr/bin/env -i PATH=/usr/bin:/usr/sbin \
		HOME="/home/$USERNAME" USER="$USERNAME" LOGNAME="$USERNAME" SHELL=/bin/bash TERM=xterm \
		LANG=C.UTF-8 XDG_RUNTIME_DIR=/tmp/xdg-$USERNAME "$@"
}

stage() {
	[ -s "$ROOTIMG" ] || { echo "missing $ROOTIMG (extract it from the ISO)" >&2; exit 1; }
	[ ! -e "$R" ] || { echo "$R exists; remove it first" >&2; exit 1; }
	src=$WORK/src-stage
	mkdir -p "$src" "$R"
	mount -o ro,loop,subvol=omarchy-root "$ROOTIMG" "$src"
	rsync -aHAX --numeric-ids "$src"/ "$R"/
	umount "$src"
	rmdir "$src"
	log "staged $(du -sh "$R" | cut -f1)"
}

setup() {
	mount_chroot
	# Kernel, bootloader and initramfs tooling of the UEFI machines: not used here. Our kernel
	# comes from linux-gts7xl; the pmOS initramfs in BOOT/RECOVERY mounts this root by UUID.
	cp "$R/usr/share/omarchy/default/pacman/aarch64/pacman-stable.conf" "$R/etc/pacman.conf"
	# Omarchy's stable snapshot of Arch Linux ARM (matches its own packages; the live ALARM
	# mirror is newer and breaks hyprland's library pins).
	cp "$R/usr/share/omarchy/default/pacman/aarch64/mirrorlist-stable" "$R/etc/pacman.d/mirrorlist"
	sed -i 's/^#\?IgnorePkg.*/IgnorePkg = linux linux-aarch64 linux-omarchy linux-omarchy-headers linux-omarchy-aarch64 linux-omarchy-aarch64-headers linux-omarchy-dtbs/' "$R/etc/pacman.conf"
	grep -q '^IgnorePkg' "$R/etc/pacman.conf" || sed -i 's/^\[options\]$/[options]\nIgnorePkg = linux linux-aarch64 linux-omarchy linux-omarchy-headers linux-omarchy-aarch64 linux-omarchy-aarch64-headers linux-omarchy-dtbs/' "$R/etc/pacman.conf"
	# qemu-user has no Landlock: pacman's download sandbox cannot start under it.
	grep -q '^DisableSandbox' "$R/etc/pacman.conf" || sed -i 's/^\[options\]$/[options]\nDisableSandbox/' "$R/etc/pacman.conf"
	# Same masks as the ISO installer while it runs, kept: no mkinitcpio/UKI/limine here.
	mkdir -p "$R/etc/pacman.d/hooks"
	for h in 90-mkinitcpio-install.hook 60-mkinitcpio-remove.hook 90-limine-mkinitcpio.hook; do
		ln -sfn /dev/null "$R/etc/pacman.d/hooks/$h"
	done
	in_root pacman-key --init
	in_root pacman-key --populate archlinuxarm omarchy
	in_root pacman -Rdd --noconfirm linux-omarchy linux-omarchy-headers 2>/dev/null || true
	# Bootloader of the UEFI machines: none here (ABL + shim). Its hooks expect an ESP.
	in_root pacman -Rdd --noconfirm limine limine-mkinitcpio-hook limine-snapper-sync 2>/dev/null || true
	rm -rf "$R"/usr/lib/modules/*-omarchy "$R/boot/dtbs"
	# Package set = what Omarchy 4.5.0 shipped. Extra packages come from the ISO's offline
	# mirror (same snapshot as the image). The online repos have moved on (openssl 4,
	# aquamarine 0.16 under Omarchy's pinned hyprland 0.56): no -Syu here.
	off=$WORK/live-offline
	if [ ! -d "$off" ]; then
		mkdir -p "$WORK/live-sfs"
		mount -o ro,loop "$WORK/x/arch/aarch64/airootfs.sfs" "$WORK/live-sfs"
		cp -a "$WORK/live-sfs/var/cache/omarchy/mirror/offline" "$off"
		umount "$WORK/live-sfs"
	fi
	# The ISO's own repo only (same snapshot as the image).
	mkdir -p "$R/var/cache/gts7xl-offline"
	mountpoint -q "$R/var/cache/gts7xl-offline" || { mount --bind "$off" "$R/var/cache/gts7xl-offline"; mounted+=("$R/var/cache/gts7xl-offline"); }
	sed -e '/^\[/,$d' "$R/etc/pacman.conf" > "$R/tmp/offline.conf"
	printf '[offline]\nSigLevel = Never\nServer = file:///var/cache/gts7xl-offline\n' >> "$R/tmp/offline.conf"
	in_root pacman --config /tmp/offline.conf -Sy --noconfirm --needed linux-firmware-qcom vulkan-freedreno 2>&1 | tail -5
	# Optional extras from the online repos, only if they install without upgrading anything.
	# Omarchy's stable ALARM mirror lists some files it does not host (404): fall back to the
	# official ALARM mirror for the download (same signed packages), during the build only.
	cp "$R/etc/pacman.d/mirrorlist" "$R/tmp/mirrorlist.stable"
	echo 'Server = http://mirror.archlinuxarm.org/$arch/$repo' >> "$R/etc/pacman.d/mirrorlist"
	# kmscon: the 404'd files fetched from the ALARM mirror with their signatures (checked by
	# pacman against the archlinuxarm keyring).
	ex=$WORK/extra-pkgs
	mkdir -p "$ex"
	for f in kmscon-10.1.0-1-aarch64.pkg.tar.xz kmscon-terminfo-10.1.0-1-aarch64.pkg.tar.xz; do
		[ -s "$ex/$f" ] || { curl -sSfL -o "$ex/$f" "http://mirror.archlinuxarm.org/aarch64/extra/$f" && curl -sSfL -o "$ex/$f.sig" "http://mirror.archlinuxarm.org/aarch64/extra/$f.sig"; } || true
	done
	mkdir -p "$R/var/cache/gts7xl-extra"; cp "$ex"/*.pkg.tar.xz* "$R/var/cache/gts7xl-extra/" 2>/dev/null || true
	in_root sh -c 'pacman -Sy --noconfirm --needed libtsm >/dev/null 2>&1; pacman -U --noconfirm --needed /var/cache/gts7xl-extra/*.pkg.tar.xz' 2>&1 | tail -3 || true
	rm -rf "$R/var/cache/gts7xl-extra"
	for n in kmscon squeekboard; do
		in_root pacman -Sy --noconfirm --needed "$n" 2>&1 | tail -3 && in_root pacman -Q "$n" >/dev/null 2>&1 && log "installed $n" || log "SKIPPED $n"
	done
	cp "$R/tmp/mirrorlist.stable" "$R/etc/pacman.d/mirrorlist"
	# User (password generated here, kept only in PASSWORD_FILE: give it to the owner).
	if ! in_root id "$USERNAME" >/dev/null 2>&1; then
		in_root useradd -m -G wheel,video,render,input -s /bin/bash "$USERNAME"
	fi
	in_root usermod -aG wheel,video,render,input "$USERNAME"
	if [ ! -s "$PASSWORD_FILE" ]; then
		install -d -m700 "$(dirname "$PASSWORD_FILE")"
		(umask 077; tr -dc 'a-km-np-z2-9' < /dev/urandom | head -c 16 > "$PASSWORD_FILE")
	fi
	printf '%s:%s\n' "$USERNAME" "$(cat "$PASSWORD_FILE")" | in_root chpasswd
	# The ISO installer's finalizers (orchestrator run_system_finalizer, run_chroot_finalizer).
	# Omarchy's install scripts from a copy, with the steps that cannot apply here made no-ops:
	# snapper (no btrfs, no snapshots in this image; needs D-Bus).
	rm -rf "$R/tmp/omarchy-install"; cp -a "$R/usr/share/omarchy/install" "$R/tmp/omarchy-install"
	# firewall: ufw/iptables cannot talk to the host kernel through qemu-user; it runs on the
	# tablet's first boot instead (gts7xl-firstboot.service, device layer).
	# hardware: Omarchy detects the machine it runs on, which here is the x86 build host (it
	# tried to install the host's NVIDIA driver). Only the generic steps apply to the tablet.
	printf '%s\n' 'run_logged "$OMARCHY_INSTALL/hardware/network.sh"' \
		'run_logged "$OMARCHY_INSTALL/hardware/set-wireless-regdom.sh"' \
		'run_logged "$OMARCHY_INSTALL/hardware/bluetooth.sh"' > "$R/tmp/omarchy-install/hardware/all.sh"
	for f in config/snapper.sh config/firewall.sh; do printf '#!/bin/bash\necho "gts7xl: skipped %s"\n' "$f" > "$R/tmp/omarchy-install/$f"; done
	in_root env OMARCHY_INSTALL=/tmp/omarchy-install /usr/bin/omarchy-apply-system --install-user "$USERNAME" --first-install > "$WORK/apply-system.log" 2>&1 || log "apply-system: non-zero (see $WORK/apply-system.log)"
	grep -E 'Failed:' "$R/var/log/omarchy-install.log" | tail -5 || true
	mkdir -p "$R/tmp/xdg-$USERNAME"; chown "$(in_root id -u "$USERNAME"):$(in_root id -g "$USERNAME")" "$R/tmp/xdg-$USERNAME"
	(cd "$R/home/$USERNAME" && as_user /usr/bin/omarchy-provision-user --force --first-install 2>&1 | tail -40) || log "provision-user: non-zero"
	# Login: SDDM autologin into the Omarchy session (touch-only first use).
	mkdir -p "$R/etc/sddm.conf.d"
	printf '[Theme]\nCurrent=omarchy\n\n[Users]\nRememberLastUser=true\nRememberLastSession=true\n' > "$R/etc/sddm.conf.d/99-omarchy-login.conf"
	printf '[Autologin]\nUser=%s\nSession=omarchy.desktop\n' "$USERNAME" > "$R/etc/sddm.conf.d/autologin.conf"
	in_root systemctl enable sddm.service sshd.service NetworkManager.service 2>/dev/null || in_root systemctl enable sddm.service sshd.service
	ln -sfn ../run/systemd/resolve/stub-resolv.conf "$R/etc/resolv.conf"
	log "setup done"
}

device() {
	mount_chroot
	# pacman in qemu-user: no Landlock sandbox (removed again at the end of this step).
	grep -q '^DisableSandbox' "$R/etc/pacman.conf" || sed -i 's/^\[options\]$/[options]\nDisableSandbox/' "$R/etc/pacman.conf"
	# Kernel: modules of the r19 BOOT kernel (pmaports linux-samsung-gts7xl).
	t=$(mktemp -d)
	tar -xzf "$KERNEL_APK" -C "$t" usr/lib/modules 2>/dev/null
	rel=$(ls "$t/usr/lib/modules")
	rm -rf "$R/usr/lib/modules/$rel"
	cp -a "$t/usr/lib/modules/$rel" "$R/usr/lib/modules/"
	rm -rf "$t"
	chown -R 0:0 "$R/usr/lib/modules/$rel"
	in_root depmod -a "$rel"
	log "modules $rel: $(wc -l < "$R/usr/lib/modules/$rel/modules.alias") aliases"
	# Prefer the linux-gts7xl package (same modules + BOOT image + the dry-run write-boot hook),
	# built by: cd WORK/pkg && GTS7XL_APK=… GTS7XL_BOOT=… CARCH=aarch64 makepkg --nodeps
	kp=$(ls "$WORK"/pkg/linux-gts7xl-*-aarch64.pkg.tar.zst 2>/dev/null | tail -1 || true)
	if [ -n "$kp" ]; then
		rm -rf "$R/usr/lib/modules/$rel"
		mkdir -p "$R/var/cache/gts7xl-pkg"; cp "$kp" "$R/var/cache/gts7xl-pkg/"
		in_root sh -c 'pacman -U --noconfirm /var/cache/gts7xl-pkg/*.pkg.tar.zst' 2>&1 | tail -4 || true
		rm -rf "$R/var/cache/gts7xl-pkg"
		in_root depmod -a "$rel"
		log "linux-gts7xl installed: $(in_root pacman -Q linux-gts7xl)"
	fi
	# Modules for the RECOVERY fallback kernel (another release than BOOT's), outside pacman.
	for a in ${EXTRA_MODULE_APKS:-}; do
		t=$(mktemp -d); tar -xzf "$a" -C "$t" usr/lib/modules 2>/dev/null
		for d in "$t"/usr/lib/modules/*; do
			r=$(basename "$d"); [ -e "$R/usr/lib/modules/$r" ] && continue
			cp -a "$d" "$R/usr/lib/modules/"; chown -R 0:0 "$R/usr/lib/modules/$r"; in_root depmod -a "$r"
			log "fallback modules $r (from $(basename "$a"))"
		done
		rm -rf "$t"
	done
	# GPU zap shader (Samsung-signed, local only).
	install -Dm644 "$ZAP" "$R/usr/lib/firmware/qcom/sm8250/samsung/gts7xl/a650_zap.mbn"
	# Audio (r20 work): ADSP firmware (Samsung-signed, local package) and the UCM + WirePlumber
	# files from the pmaports packages; PipeWire ALSA/Pulse and alsa-utils from the repos.
	for a in ${AUDIO_APKS:-}; do
		t=$(mktemp -d); tar -xzf "$a" -C "$t" --exclude='.*' 2>/dev/null
		[ -d "$t/lib/firmware" ] && { mkdir -p "$t/usr/lib"; cp -a "$t/lib/firmware" "$t/usr/lib/"; rm -rf "$t/lib"; }
		cp -a "$t"/usr "$R"/ ; rm -rf "$t"; log "audio files from $(basename "$a")"
	done
	chown -R 0:0 "$R/usr/lib/firmware/qcom/sm8250/samsung" "$R/usr/share/alsa/ucm2/Samsung" 2>/dev/null || true
	# Omarchy's stable ALARM mirror 404s some files it lists: official ALARM mirror as a
	# download fallback during this step only (signed packages).
	cp "$R/etc/pacman.d/mirrorlist" "$R/tmp/mirrorlist.stable"
	echo 'Server = http://mirror.archlinuxarm.org/$arch/$repo' >> "$R/etc/pacman.d/mirrorlist"
	for n in alsa-utils pipewire-alsa pipewire-pulse btop firefox; do
		if in_root pacman -Q "$n" >/dev/null 2>&1; then log "present $n"; continue; fi
		in_root pacman -S --noconfirm --needed "$n" > "$WORK/pkg-$n.log" 2>&1 && log "installed $n" || log "FAILED $n (see $WORK/pkg-$n.log)"
	done
	cp "$R/tmp/mirrorlist.stable" "$R/etc/pacman.d/mirrorlist"
	# cliamp: official linux-arm64 release, sha256 checked against its checksums.txt.
	if [ -s "$WORK/cliamp/cliamp-linux-arm64" ] && (cd "$WORK/cliamp" && sha256sum -c --ignore-missing --status checksums.txt); then
		install -Dm755 "$WORK/cliamp/cliamp-linux-arm64" "$R/usr/local/bin/cliamp"; log "cliamp installed"
	else log "cliamp: missing or checksum mismatch, not installed"; fi
	# MOTD.
	[ -s "$root_dir/build/rebutos-motd.ansi" ] && install -m644 "$root_dir/build/rebutos-motd.ansi" "$R/etc/motd"
	# Device layer (bt address, power key, keyboard Esc, polkit, sshd, kmscon, Hyprland overrides).
	"$DEV/install.sh" "$R" "$USERNAME"
	# Identity carried over from the pmOS rootfs: SSH host keys and the authorized key.
	if [ -n "$BACKUP" ]; then
		t=$(mktemp -d)
		zstd -dc "$BACKUP/pmos-root.tar.zst" | tar -x -C "$t" --wildcards './etc/ssh/ssh_host_*' "./home/$USERNAME/.ssh/authorized_keys" 2>/dev/null || true
		cp -a "$t"/etc/ssh/ssh_host_* "$R/etc/ssh/" 2>/dev/null && chown 0:0 "$R"/etc/ssh/ssh_host_* && chmod 600 "$R"/etc/ssh/ssh_host_*_key
		if [ -s "$t/home/$USERNAME/.ssh/authorized_keys" ]; then
			install -d -m700 "$R/home/$USERNAME/.ssh"
			install -m600 "$t/home/$USERNAME/.ssh/authorized_keys" "$R/home/$USERNAME/.ssh/authorized_keys"
			in_root chown -R "$USERNAME:$USERNAME" "/home/$USERNAME/.ssh"
		fi
		rm -rf "$t"
	fi
	# Saved Wi-Fi connection(s) from the pmOS rootfs (root-only, never printed).
	if [ -n "$BACKUP" ]; then
		t=$(mktemp -d); chmod 700 "$t"
		zstd -dc "$BACKUP/pmos-root.tar.zst" | tar -x -C "$t" --wildcards './etc/NetworkManager/system-connections/*' 2>/dev/null || true
		n=0
		for c in "$t"/etc/NetworkManager/system-connections/*.nmconnection; do
			[ -f "$c" ] || continue
			install -D -m600 -o0 -g0 "$c" "$R/etc/NetworkManager/system-connections/$(basename "$c")"; n=$((n + 1))
		done
		rm -rf "$t"; log "NetworkManager connections carried over: $n"
	fi
	in_root ufw allow ssh >/dev/null 2>&1 || true
	sed -i '/^DisableSandbox$/d' "$R/etc/pacman.conf"
	log "device layer installed"
}

image() {
	boot_uuid=$(sed -n 's/^pmos_boot_uuid=//p' "$BACKUP/cmdline-uuids.txt")
	root_uuid=$(sed -n 's/^pmos_root_uuid=//p' "$BACKUP/cmdline-uuids.txt")
	[ -n "$boot_uuid" ] && [ -n "$root_uuid" ] || { echo "UUIDs not found in $BACKUP" >&2; exit 1; }
	used=$(du -sb --exclude=./proc --exclude=./sys "$R" | cut -f1)
	root_mib=$(( used / 1048576 * 13 / 10 + 2048 ))
	img=$WORK/omarchy-gts7xl.img
	rm -f "$img"
	# Same layout as rootfs-r15.img: 4096-byte sectors, p1 at LBA 2048 (480 MiB), p2 after it.
	truncate -s $(( (8 + 480 + root_mib + 8) * 1048576 )) "$img"
	sfdisk --sector-size 4096 -q "$img" <<-EOF
		label: gpt
		start=2048, size=$((480 * 256)), name=primary
		start=$((2048 + 480 * 256)), size=$((root_mib * 256)), name=primary
	EOF
	lo=$(losetup --sector-size 4096 -P -f --show "$img")
	trap 'umount "$WORK/img-mnt" 2>/dev/null; losetup -d "$lo"; umount_chroot' EXIT
	mkfs.ext2 -q -b 4096 -U "$boot_uuid" -L pmOS_boot "${lo}p1"
	mkfs.ext4 -q -U "$root_uuid" -L pmOS_root "${lo}p2"
	mkdir -p "$WORK/img-mnt"
	# p1: the pmOS boot filesystem as it is on the tablet (the pmOS initramfs reads it).
	mount "${lo}p1" "$WORK/img-mnt"
	zstd -dc "$BACKUP/pmos-boot.tar.zst" | tar --numeric-owner -xp -C "$WORK/img-mnt"
	umount "$WORK/img-mnt"
	mount "${lo}p2" "$WORK/img-mnt"
	rsync -aHAX --numeric-ids --exclude=/usr/bin/qemu-aarch64-static "$R"/ "$WORK/img-mnt"/
	cat > "$WORK/img-mnt/etc/fstab" <<-EOF
		# gts7xl: root found by the pmOS initramfs (pmos_root_uuid); boot = the pmOS boot fs.
		UUID=$root_uuid	/	ext4	defaults,noatime	0 1
	EOF
	for d in proc sys dev run tmp; do rm -rf "${WORK:?}/img-mnt/$d"/* 2>/dev/null || true; done
	umount "$WORK/img-mnt"
	losetup -d "$lo"
	trap umount_chroot EXIT
	(cd "$WORK" && sha256sum omarchy-gts7xl.img > omarchy-gts7xl.img.sha256 && cat omarchy-gts7xl.img.sha256)
	log "image: $img ($(du -h --apparent-size "$img" | cut -f1)), root $root_mib MiB, boot $boot_uuid, root $root_uuid"
}

case ${1:-} in
stage) stage ;;
setup) setup ;;
device) device ;;
image) image ;;
chroot) shift; mount_chroot; in_root "${@:-/bin/bash}" ;;
mounttest) mount_chroot; findmnt -rn -o TARGET,PROPAGATION | grep -F "$R" | sort; umount_chroot ;;
*) sed -n '2,20p' "$0"; exit 2 ;;
esac
