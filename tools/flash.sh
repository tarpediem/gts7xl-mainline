#!/usr/bin/env bash
# Flash images to the Tab S7+ 5G with one Heimdall command (Download Mode).
#
# usage: flash.sh [--dry-run] [--pit FILE] [--keep-vbmeta | --vbmeta FILE] [--resume]
#                 [--allow-dtbo] [--allow-userdata] PART=IMAGE ...
#
#   PART              one of BOOT RECOVERY DTBO USERDATA (VBMETA is added by the script).
#   --dry-run         print the heimdall command, run nothing, ask nothing.
#   --pit FILE        text output of `heimdall print-pit`. Every partition must exist in it
#                     (the name is passed to heimdall in the PIT's own letter case) and every
#                     image must fit (block count x FLASH_BLOCK_SIZE). Required for a real run.
#   --keep-vbmeta     do not add tools/images/vbmeta-disabled.img (the device keeps its vbmeta).
#   --vbmeta FILE     write FILE to VBMETA instead (e.g. the stock vbmeta.img, to roll back).
#   --resume          pass --resume to heimdall (session left open by a --no-reboot action).
#   --allow-dtbo      DTBO is refused without it: a non-stock DTBO stops One UI from booting.
#   --allow-userdata  USERDATA is refused without it: it erases One UI's data.
#
# A real run checks `heimdall detect`, shows what will be written and waits for the word FLASH.
#
# Environment:
#   FLASH_SSH         transport used to reach root (default: "ssh -t localhost");
#                     it receives the whole remote command as ONE argument.
#   FLASH_NOTES       log file (default: <repo>/NOTES.md); written only on a real run.
#   FLASH_BLOCK_SIZE  bytes per PIT block (default 4096: UFS logical block of this tablet).
set -euo pipefail
ALLOWED=" BOOT DTBO VBMETA RECOVERY USERDATA "
die() { echo "$*" >&2; exit 1; }
usage() { sed -n '4,5p' "$0" | sed 's/^# //' >&2; exit 2; }

dry=0; pit=""; vbmeta=""; keep_vbmeta=0; resume=0; allow_dtbo=0; allow_userdata=0
parts=(); imgs=()
while [ $# -gt 0 ]; do
  case $1 in
    --dry-run) dry=1 ;;
    --pit) [ $# -ge 2 ] || usage; pit=$2; shift ;;
    --keep-vbmeta) keep_vbmeta=1 ;;
    --vbmeta) [ $# -ge 2 ] || usage; vbmeta=$2; shift ;;
    --resume) resume=1 ;;
    --allow-dtbo) allow_dtbo=1 ;;
    --allow-userdata) allow_userdata=1 ;;
    -*) echo "unknown option: $1" >&2; usage ;;
    *=*) break ;;
    *) usage ;;
  esac
  shift
done
[ $# -gt 0 ] || usage
bs=${FLASH_BLOCK_SIZE:-4096}
[[ $bs =~ ^[1-9][0-9]*$ ]] || die "bad FLASH_BLOCK_SIZE: $bs"

# Resolve everything against the caller's cwd before moving to the repo root.
for kv in "$@"; do
  [[ $kv == *=* ]] || usage
  part=${kv%%=*}; img=${kv#*=}; part=${part^^}
  [[ $ALLOWED == *" $part "* ]] || die "refused partition: $part"
  [ "$part" != VBMETA ] || die "VBMETA is added automatically"
  [ "$part" != USERDATA ] || [ $allow_userdata = 1 ] || die "refused partition: USERDATA (erases One UI data; needs --allow-userdata)"
  [ "$part" != DTBO ] || [ $allow_dtbo = 1 ] || die "refused partition: DTBO (One UI needs the stock DTBO; needs --allow-dtbo)"
  [[ " ${parts[*]:-} " != *" $part "* ]] || die "partition given twice: $part"
  [ -f "$img" ] || die "missing image: $img"
  parts+=("$part"); imgs+=("$(realpath -- "$img")")
done
if [ -n "$vbmeta" ]; then
  [ $keep_vbmeta = 0 ] || die "--vbmeta and --keep-vbmeta exclude each other"
  [ -f "$vbmeta" ] || die "missing image: $vbmeta"
  vbmeta=$(realpath -- "$vbmeta")
fi
if [ -n "$pit" ]; then
  [ -f "$pit" ] || die "missing PIT file: $pit"
  pit=$(realpath -- "$pit")
fi
notes=${FLASH_NOTES:-}
[ -n "$notes" ] && notes=$(realpath -m -- "$notes")

cd "$(dirname "$0")/.."
root=$(pwd -P)
notes=${notes:-$root/NOTES.md}
if [ $keep_vbmeta = 0 ]; then
  vbmeta=${vbmeta:-$root/tools/images/vbmeta-disabled.img}
  [ -f "$vbmeta" ] || die "missing image: $vbmeta (build it first)"
  parts+=(VBMETA); imgs+=("$vbmeta")
fi

# PIT: exact partition name and size in bytes of each target.
names=("${parts[@]}"); sizes=()
if [ -n "$pit" ]; then
  table=$(awk -F': ' '/^Partition Block Count:/ {c=$2} /^Partition Name:/ {print $2, c}' "$pit")
  [ -n "$table" ] || die "no partition entries in PIT file: $pit"
  for i in "${!parts[@]}"; do
    hit=$(awk -v p="${parts[i]}" 'toupper($1) == p' <<< "$table")
    [ -n "$hit" ] || die "partition ${parts[i]} not in PIT ($pit)"
    [ "$(wc -l <<< "$hit")" = 1 ] || die "partition ${parts[i]} is ambiguous in PIT ($pit)"
    read -r name count <<< "$hit"
    [[ $count =~ ^[0-9]+$ ]] || die "bad block count for $name in PIT"
    room=$((count * bs)); size=$(stat -c %s -- "${imgs[i]}")
    [ "$size" -le "$room" ] || die "image too large for $name: $size bytes > $room ($count blocks x $bs): ${imgs[i]}"
    names[i]=$name; sizes[i]=$room
  done
fi

cmd=(heimdall flash)
for i in "${!parts[@]}"; do cmd+=("--${names[i]}" "${imgs[i]}"); done
cmd+=(--no-reboot)
[ $resume = 1 ] && cmd+=(--resume)
if [ $dry = 1 ]; then echo "${cmd[*]}"; exit 0; fi

[ -n "$pit" ] || die "a real flash needs --pit FILE (heimdall print-pit > FILE)"
read -ra ssh <<< "${FLASH_SSH:-ssh -t localhost}"
remote() { "${ssh[@]}" "sudo bash -c $(printf %q "cd $(printf %q "$root") && $(printf '%q ' "$@")")"; }

remote heimdall detect </dev/null || die "no device in Download Mode (heimdall detect failed)"

echo "About to write (${#parts[@]} partitions, one heimdall command):"
for i in "${!parts[@]}"; do
  printf '  %-9s %10s / %10s bytes  sha256 %s  %s\n' "${names[i]}" "$(stat -c %s -- "${imgs[i]}")" \
    "${sizes[i]}" "$(sha256sum "${imgs[i]}" | cut -c1-16)" "${imgs[i]}"
done
printf 'Type FLASH to continue: '
answer=""; read -r answer || true
[ "$answer" = FLASH ] || die "aborted: confirmation not given"

set +e
remote "${cmd[@]}" </dev/null
rc=$?
set -e

{
  if [ $rc = 0 ]; then echo; echo "## $(date -Is) flash"
  else echo; echo "## $(date -Is) flash FAILED (exit $rc)"; fi
  for i in "${!parts[@]}"; do
    # NOTES.md is public: the path relative to the repo, else the file name only.
    shown=$(realpath -m --relative-to="$root" -- "${imgs[i]}")
    case "$shown" in ../*|/*) shown=${imgs[i]##*/} ;; esac
    echo "- ${parts[i]}: $(sha256sum "${imgs[i]}" | cut -d' ' -f1) $shown"
  done
} >> "$notes"
exit $rc
