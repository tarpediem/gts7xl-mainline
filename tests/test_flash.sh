#!/usr/bin/env bash
# tests/test_flash.sh — dry-run behaviour of tools/flash.sh
set -u; cd "$(dirname "$0")/.." || exit 1; fail=0
t=$(mktemp -d); echo x > "$t/boot.img"; echo y > "$t/dtbo.img"
out=$(tools/flash.sh --dry-run BOOT="$t/boot.img" DTBO="$t/dtbo.img")
[[ $out == *"heimdall flash"* && $out == *"--BOOT $t/boot.img"* && $out == *"--DTBO $t/dtbo.img"* \
   && $out == *"--VBMETA tools/images/vbmeta-disabled.img"* && $out == *"--no-reboot"* ]] || { echo "FAIL compose: $out"; fail=1; }
tools/flash.sh --dry-run EFS="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: EFS accepted"; fail=1; }
tools/flash.sh --dry-run BOOT="$t/missing.img" >/dev/null 2>&1 && { echo "FAIL: missing file accepted"; fail=1; }
[ $fail = 0 ] && echo "test_flash: OK"; exit $fail
