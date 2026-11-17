#!/usr/bin/env bash
# Replace a kernel module on the running gts7xl over USB (debug shell): rmmod + insmod.
#
# usage: tools/module-push.sh [--dry-run] [--host IP] [--local-ip IP] [--name NAME]
#                             (--ko FILE | --apk FILE)
#
#   --ko    module file (.ko or .ko.zst)
#   --apk   linux-samsung-gts7xl-*.apk: the module NAME is taken from it
#   --name  module name, default stmfts1b
#
# The module must come from the same kernel build as the running kernel (vermagic is
# checked against `uname -r`; struct layouts are not). Busybox insmod cannot read zstd,
# so the file is decompressed here.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tools=$root/tools
dry=0 host=172.16.42.1 local_ip=172.16.42.2 name=stmfts1b ko="" apk=""

while [ $# -gt 0 ]; do
	case "$1" in
	--dry-run) dry=1 ;;
	--host) host=$2; shift ;;
	--local-ip) local_ip=$2; shift ;;
	--name) name=$2; shift ;;
	--ko) ko=$2; shift ;;
	--apk) apk=$2; shift ;;
	-h|--help) sed -n '2,13p' "$0"; exit 0 ;;
	*) echo "module-push.sh: unknown argument $1" >&2; exit 2 ;;
	esac
	shift
done
if [ -z "$ko" ] && [ -z "$apk" ]; then
	echo "module-push.sh: --ko or --apk needed" >&2; exit 2
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

if [ -n "$apk" ]; then
	member=$(tar -tzf "$apk" 2>/dev/null | grep -E "/$name\.ko(\.zst)?$" | head -1) || true
	[ -n "$member" ] || { echo "module-push.sh: $name.ko not in $apk" >&2; exit 1; }
	tar -xzf "$apk" -C "$work" "$member" 2>/dev/null
	ko=$work/$member
fi
[ -e "$ko" ] || { echo "module-push.sh: missing $ko" >&2; exit 1; }
case "$ko" in
*.zst) zstd -q -d -f "$ko" -o "$work/$name.ko" ;;
*) cp "$ko" "$work/$name.ko" ;;
esac
vermagic=$(strings "$work/$name.ko" | sed -n 's/^vermagic=//p' | head -1)
echo "== $name.ko, vermagic: ${vermagic:-?}"

cmd="rmmod $name 2>/dev/null; insmod /tmp/$name.ko && echo loaded; dmesg | tail -n 20"
if [ "$dry" = 1 ]; then
	echo "== [dry-run] run: uname -r (must match the vermagic release)"
	echo "== [dry-run] push $work/$name.ko -> $host:/tmp/$name.ko"
	echo "== [dry-run] run: $cmd"
	exit 0
fi

usbsh() { python3 "$tools/usbsh.py" --host "$host" --local-ip "$local_ip" "$@"; }
release=$(usbsh run "uname -r" | tr -d '\r\n')
if [ "${vermagic%% *}" != "$release" ]; then
	echo "module-push.sh: module is for '${vermagic%% *}', tablet runs '$release'" >&2; exit 1
fi
usbsh push "$work/$name.ko" "/tmp/$name.ko"
usbsh run "$cmd"
