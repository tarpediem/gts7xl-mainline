# shellcheck shell=bash
# Sourced by tools/build-omarchy-rootfs.sh (and tests/test_omarchy_pacman_sync.py).
# Needs: $R (root tree), $WORK (logs), log(), in_root() (runs a command chrooted in $R).
#
# Why: the image once shipped the live Arch Linux ARM mirror's sync databases (newer than
# Omarchy's stable snapshot). pacman never replaced them from the older stable mirror
# (If-Modified-Since), so the tablet saw openssl 4 / rust 1.100 and ended up half upgraded
# (fixed on the tablet 2026-11-18, NOTES.md). The image must only carry databases fetched
# from the configured stable mirrors, and no package newer than that snapshot.

# Packages allowed to be newer than the stable snapshot (space separated, documented reason
# required in NOTES.md). Empty by default: a fresh build installs everything from the snapshot.
ALLOW_NEWER_PKGS=${ALLOW_NEWER_PKGS:-}

refresh_sync_dbs() {
	local ml=$R/etc/pacman.d/mirrorlist sync=$R/var/lib/pacman/sync repos f name newer=() n v inst
	# The live ALARM mirror is only ever a download fallback during a step; it must be gone
	# before the databases are fetched for good.
	if grep -Eq '^[[:space:]]*Server[[:space:]]*=.*mirror\.archlinuxarm\.org' "$ml"; then
		echo "refresh_sync_dbs: live ALARM mirror still listed in $ml" >&2
		return 1
	fi
	rm -f "$sync"/*.db "$sync"/*.db.sig "$sync"/*.files "$sync"/*.files.sig
	in_root pacman -Syy --noconfirm > "$WORK/pacman-syy.log" 2>&1 ||
		{ echo "refresh_sync_dbs: pacman -Syy failed (see $WORK/pacman-syy.log)" >&2; return 1; }
	repos=$(in_root pacman-conf --repo-list)
	for name in $repos; do
		[ -s "$sync/$name.db" ] || { echo "refresh_sync_dbs: no database for repo $name" >&2; return 1; }
	done
	# Nothing else (e.g. the build-only [offline] repo's database).
	for f in "$sync"/*.db; do
		[ -e "$f" ] || continue
		name=$(basename "$f" .db)
		grep -qxF "$name" <<< "$repos" || { rm -f "$f" "$f.sig"; log "sync: removed stray $name.db"; }
	done
	# Installed packages newer than the snapshot = pulled from another mirror.
	while read -r n v; do
		[ -n "$n" ] || continue
		inst=$(in_root pacman -Q "$n" 2>/dev/null | awk '{print $2}')
		[ -n "$inst" ] && [ "$(in_root vercmp "$inst" "$v")" -gt 0 ] || continue
		if [[ " $ALLOW_NEWER_PKGS " == *" $n "* ]]; then
			log "sync: $n $inst newer than the snapshot ($v), allowed by ALLOW_NEWER_PKGS"
		else
			newer+=("$n $inst (snapshot $v)")
		fi
	done < <(in_root pacman -Suu --print --print-format '%n %v' 2>/dev/null)
	if [ ${#newer[@]} -gt 0 ]; then
		printf 'refresh_sync_dbs: newer than the stable snapshot: %s\n' "${newer[@]}" >&2
		echo "refresh_sync_dbs: downgrade them (pacman -Suu) or list them in ALLOW_NEWER_PKGS" >&2
		return 1
	fi
	log "sync databases: $(echo $repos) from the stable mirrors, no package newer than the snapshot"
}
