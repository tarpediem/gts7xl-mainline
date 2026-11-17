#!/usr/bin/env bash
# Flash images to the Tab S7+ 5G with one Heimdall command (Download Mode).
# vbmeta-disabled is always included: single-image commits are unreliable on SM8250.
set -euo pipefail
cd "$(dirname "$0")/.."
ALLOWED=" BOOT DTBO VBMETA RECOVERY USERDATA "
dry=0; args=(); parts=(); imgs=()
[ "${1:-}" = "--dry-run" ] && { dry=1; shift; }
[ $# -gt 0 ] || { echo "usage: flash.sh [--dry-run] PART=IMAGE ..." >&2; exit 2; }
for kv in "$@"; do
  part=${kv%%=*}; img=${kv#*=}
  [[ $ALLOWED == *" $part "* ]] || { echo "refused partition: $part" >&2; exit 1; }
  [ "$part" = VBMETA ] && { echo "VBMETA is added automatically" >&2; exit 1; }
  [ -f "$img" ] || { echo "missing image: $img" >&2; exit 1; }
  args+=("--$part" "$img"); parts+=("$part"); imgs+=("$img")
done
cmd=(heimdall flash "${args[@]}" --VBMETA tools/images/vbmeta-disabled.img --no-reboot)
if [ $dry = 1 ]; then echo "${cmd[*]}"; exit 0; fi
{
  echo; echo "## $(date -Is) flash"
  for i in "${!parts[@]}"; do
    echo "- ${parts[i]}: $(sha256sum "${imgs[i]}" | cut -c1-16) ${imgs[i]}"
  done
} >> NOTES.md
ssh -t localhost sudo bash -c "$(printf '%q ' cd "$PWD") && $(printf '%q ' "${cmd[@]}")"
