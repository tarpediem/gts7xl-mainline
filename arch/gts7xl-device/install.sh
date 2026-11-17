#!/usr/bin/env bash
# Install the gts7xl device layer into an Arch/Omarchy root tree.
# usage: arch/gts7xl-device/install.sh ROOT USER   (as root; also used by the PKGBUILD later)
set -euo pipefail
R=$1 U=$2
f=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/files
inst() { install -D -m"$1" "$f/$2" "$R/$3"; }
inst 755 gts7xl-bt-addr.sh usr/lib/gts7xl/gts7xl-bt-addr
sed 's|/usr/libexec/gts7xl-bt-addr|/usr/lib/gts7xl/gts7xl-bt-addr|' "$f/gts7xl-bt-addr.service" > "$R/usr/lib/systemd/system/gts7xl-bt-addr.service"
inst 644 gts7xl-bt-addr.conf usr/lib/systemd/system/bluetooth.service.d/gts7xl-bt-addr.conf
inst 644 gts7xl-bt-hid.conf usr/lib/modules-load.d/gts7xl-bt-hid.conf
inst 755 60-gts7xl-powerkey.sh usr/lib/gts7xl/gts7xl-powerkey
sed 's|/usr/libexec/gts7xl-powerkey|/usr/lib/gts7xl/gts7xl-powerkey|' "$f/gts7xl-powerkey.service" > "$R/usr/lib/systemd/system/gts7xl-powerkey.service"
printf '\n[Install]\nWantedBy=multi-user.target\n' >> "$R/usr/lib/systemd/system/gts7xl-powerkey.service"
inst 755 gts7xl-hypr-dpms usr/bin/gts7xl-hypr-dpms
inst 755 gts7xl-volume usr/bin/gts7xl-volume
inst 755 gts7xl-session-dpms usr/lib/gts7xl/gts7xl-session-dpms
inst 644 60-gts7xl-speaker-protection.conf usr/share/pipewire/pipewire.conf.d/60-gts7xl-speaker-protection.conf
inst 755 gts7xl-firstboot usr/lib/gts7xl/gts7xl-firstboot
inst 644 gts7xl-firstboot.service usr/lib/systemd/system/gts7xl-firstboot.service
inst 755 gts7xl-osk usr/bin/gts7xl-osk
inst 644 70-bt-keyboard-esc.hwdb etc/udev/hwdb.d/70-bt-keyboard-esc.hwdb
inst 644 90-gts7xl-udisks-ignore.rules etc/udev/rules.d/90-gts7xl-udisks-ignore.rules
install -D -m440 "$f/10-gts7xl-wheel.sudoers" "$R/etc/sudoers.d/10-gts7xl-wheel"
inst 644 00-gts7xl-no-foreign-kernel.hook usr/share/libalpm/hooks/00-gts7xl-no-foreign-kernel.hook
inst 755 gts7xl-pacman-ignore "home/$U/.config/omarchy/hooks/pre-refresh-pacman.d/gts7xl-ignorepkg"
chroot "$R" chown -R "$U:$U" "/home/$U/.config/omarchy"
# IgnorePkg now (Omarchy's setup rewrote pacman.conf from its template).
L='IgnorePkg = linux linux-aarch64 linux-omarchy linux-omarchy-headers linux-omarchy-aarch64 linux-omarchy-aarch64-headers linux-omarchy-dtbs limine limine-mkinitcpio-hook limine-snapper-sync'
sed -i "/^IgnorePkg/d; 0,/^\[options\]$/s||[options]\n$L|" "$R/etc/pacman.conf"
inst 644 gts7xl-wheel.rules usr/share/polkit-1/rules.d/40-gts7xl-wheel.rules
inst 644 sshd-keyonly.conf etc/ssh/sshd_config.d/40-gts7xl-keyonly.conf
inst 644 gts7xl-console.sysctl usr/lib/sysctl.d/60-gts7xl-console.conf
inst 644 logind-powerkey.conf etc/systemd/logind.conf.d/40-gts7xl-powerkey.conf
inst 644 kmscon.conf etc/kmscon/kmscon.conf
# kmscon on the text VTs (tty2+, logind autovt); SDDM/Hyprland keep tty1.
ln -sfn /usr/lib/systemd/system/kmsconvt@.service "$R/etc/systemd/system/autovt@.service"
# English, UTF-8.
sed -i 's/^#\(en_US.UTF-8 UTF-8\)/\1/' "$R/etc/locale.gen"
chroot "$R" locale-gen >/dev/null
printf 'LANG=en_US.UTF-8\n' > "$R/etc/locale.conf"
printf 'KEYMAP=us\n' > "$R/etc/vconsole.conf"
printf "poubelle\n" > "$R/etc/hostname"
grep -q "poubelle" "$R/etc/hosts" 2>/dev/null || printf "127.0.0.1\tlocalhost\n::1\t\tlocalhost\n127.0.1.1\tpoubelle\n" >> "$R/etc/hosts"
chroot "$R" systemd-hwdb update
ln -sfn /usr/share/zoneinfo/Asia/Bangkok "$R/etc/localtime"
chroot "$R" systemctl enable systemd-timesyncd.service >/dev/null 2>&1 || true
chroot "$R" systemctl enable gts7xl-bt-addr.service gts7xl-powerkey.service gts7xl-firstboot.service >/dev/null
# No zram module in our kernel.
chroot "$R" systemctl mask systemd-zram-setup@zram0.service >/dev/null 2>&1 || true
# Hyprland overrides (Omarchy 4.5 uses a Lua config): ~/.config/hypr/gts7xl.lua, required last.
h=$R/home/$U/.config/hypr
install -D -m644 "$f/hypr-gts7xl.lua" "$h/gts7xl.lua"
grep -q 'require("hypr.gts7xl")' "$h/hyprland.lua" ||
	printf '\n-- gts7xl device overrides (keep last)\nrequire("hypr.gts7xl")\n' >> "$h/hyprland.lua"
chroot "$R" chown -R "$U:$U" "/home/$U/.config/hypr"
# GNOME (if installed): dconf defaults, no squeekboard/fcitx5 there (GNOME's own OSK).
if [ -d "$R/usr/share/gnome-shell" ]; then
	inst 644 gnome-dconf-gts7xl etc/dconf/db/local.d/00-gts7xl
	inst 644 dconf-profile-user etc/dconf/profile/user
	chroot "$R" dconf update
	a=$R/home/$U/.config/autostart; mkdir -p "$a"
	for d in org.fcitx.Fcitx5.desktop sm.puri.Squeekboard.desktop; do
		[ -e "$R/etc/xdg/autostart/$d" ] && { cp "$R/etc/xdg/autostart/$d" "$a/$d"; printf 'NotShowIn=GNOME;\n' >> "$a/$d"; }
	done
	# Omarchy starts fcitx5 as a user unit: not under GNOME (it takes over GNOME's own OSK input).
	d=$R/home/$U/.config/systemd/user/omarchy-fcitx5.service.d; mkdir -p "$d"
	printf '[Service]\nExecCondition=/bin/sh -c '"'"'case "$XDG_CURRENT_DESKTOP" in *GNOME*) exit 1;; esac'"'"'\n' > "$d/gts7xl-not-gnome.conf"
	chroot "$R" chown -R "$U:$U" "/home/$U/.config/autostart" "/home/$U/.config/systemd"
fi
