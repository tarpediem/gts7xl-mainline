#!/usr/bin/env bash
# Flash images to the Tab S7+ 5G with one Heimdall command (Download Mode).
# vbmeta-disabled is always included: single-image commits are unreliable on SM8250.
#
# Environment:
#   FLASH_SSH    transport used to reach root (default: "ssh -t localhost");
#                it receives the whole remote command as ONE argument.
#   FLASH_NOTES  log file (default: <repo>/NOTES.md); written only on a real run.
set -euo pipefail
ALLOWED=" BOOT DTBO VBMETA RECOVERY USERDATA "
dry=0; args=(); parts=(); imgs=()
[ "${1:-}" = "--dry-run" ] && { dry=1; shift; }
[ $# -gt 0 ] || { echo "usage: flash.sh [--dry-run] PART=IMAGE ..." >&2; exit 2; }

# Resolve everything against the caller's cwd before moving to the repo root.
for kv in "$@"; do
  part=${kv%%=*}; img=${kv#*=}
  [[ $ALLOWED == *" $part "* ]] || { echo "refused partition: $part" >&2; exit 1; }
  [ "$part" = VBMETA ] && { echo "VBMETA is added automatically" >&2; exit 1; }
  [ -f "$img" ] || { echo "missing image: $img" >&2; exit 1; }
  img=$(realpath -- "$img")
  args+=("--$part" "$img"); parts+=("$part"); imgs+=("$img")
done
notes=${FLASH_NOTES:-}
[ -n "$notes" ] && notes=$(realpath -m -- "$notes")

cd "$(dirname "$0")/.."
root=$(pwd -P)
notes=${notes:-$root/NOTES.md}
vbmeta=$root/tools/images/vbmeta-disabled.img
[ -f "$vbmeta" ] || { echo "missing image: $vbmeta (build it first)" >&2; exit 1; }
parts+=(VBMETA); imgs+=("$vbmeta")

cmd=(heimdall flash "${args[@]}" --VBMETA "$vbmeta" --no-reboot)
if [ $dry = 1 ]; then echo "${cmd[*]}"; exit 0; fi

read -ra ssh <<< "${FLASH_SSH:-ssh -t localhost}"
inner="cd $(printf %q "$root") && $(printf '%q ' "${cmd[@]}")"
set +e
"${ssh[@]}" "sudo bash -c $(printf %q "$inner")"
rc=$?
set -e

{
  if [ $rc = 0 ]; then echo; echo "## $(date -Is) flash"
  else echo; echo "## $(date -Is) flash FAILED (exit $rc)"; fi
  for i in "${!parts[@]}"; do
    echo "- ${parts[i]}: $(sha256sum "${imgs[i]}" | cut -d' ' -f1) ${imgs[i]}"
  done
} >> "$notes"
exit $rc
