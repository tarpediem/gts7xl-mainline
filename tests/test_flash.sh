#!/usr/bin/env bash
# tests/test_flash.sh — behaviour of tools/flash.sh.
# Safety: before flash.sh is ever called, trap stubs for ssh/sudo/heimdall are put
# first in this test's PATH (they fail loudly with exit 99), and FLASH_SSH is
# exported to a fake transport. The real ssh, sudo and heimdall are unreachable.
set -u; cd "$(dirname "$0")/.." || exit 1; fail=0
repo=$(pwd -P)
t=$(mktemp -d); t=$(cd "$t" && pwd -P); trap 'rm -rf "$t"' EXIT

# --- trap stubs: anything that bypasses FLASH_SSH hits these
trapdir="$t/trap"; mkdir "$trapdir"
for b in ssh sudo heimdall; do
  cat > "$trapdir/$b" <<'STUB'
#!/usr/bin/env bash
echo "REAL-PATH REACHED: $0 $*" >&2
exit 99
STUB
  chmod +x "$trapdir/$b"
done
export PATH="$trapdir:$PATH"
[ "$(command -v heimdall)" = "$trapdir/heimdall" ] && [ "$(command -v ssh)" = "$trapdir/ssh" ] \
  && [ "$(command -v sudo)" = "$trapdir/sudo" ] || { echo "stub PATH not effective"; exit 1; }

# --- fake transport: working stub sudo/heimdall, used by every invocation
stub="$t/stub"; mkdir "$stub"
cat > "$stub/sudo" <<'STUB'
#!/usr/bin/env bash
exec "$@"
STUB
cat > "$stub/heimdall" <<'STUB'
#!/usr/bin/env bash
echo "$1" >> "$HEIMDALL_ARGV.calls"
if [ "$1" = detect ]; then exit "${HEIMDALL_DETECT_RC:-0}"; fi
printf '%s\n' "$@" > "$HEIMDALL_ARGV"
exit "${HEIMDALL_RC:-0}"
STUB
cat > "$t/fake-ssh" <<FAKE
#!/usr/bin/env bash
export PATH="$stub:\$PATH"
[ "\$(command -v heimdall)" = "$stub/heimdall" ] || { echo "real heimdall reachable" >&2; exit 97; }
[ "\$(command -v sudo)" = "$stub/sudo" ] || { echo "real sudo reachable" >&2; exit 98; }
[ \$# -eq 1 ] || { echo "expected one argument, got \$#" >&2; exit 96; }
exec bash -c "\$1"
FAKE
chmod +x "$stub/sudo" "$stub/heimdall" "$t/fake-ssh"
export FLASH_SSH="$t/fake-ssh"
export HEIMDALL_ARGV="$t/argv"

# Script under test (overridable only to verify the trap stubs with a broken copy).
flash=${FLASH_SH_UNDER_TEST:-$repo/tools/flash.sh}
vb="$repo/tools/images/vbmeta-disabled.img"
echo x > "$t/boot.img"; echo y > "$t/dtbo.img"

# PIT fixture in `heimdall print-pit` text format. Block size is 4096 on this UFS device:
# BOOT 17408 blocks = 68 MiB, RECOVERY 21213 blocks, VBMETA 16 blocks = 64 KiB.
pit="$t/pit.txt"
pit_entry() { printf -- '--- Entry #%s ---\nBinary Type: 0 (AP)\nDevice Type: 8 (Unknown)\nIdentifier: %s\nAttributes: 5 (Read/Write)\nUpdate Attributes: 1 (FOTA)\nPartition Block Size/Offset: 0\nPartition Block Count: %s\nFile Offset (Obsolete): 0\nFile Size (Obsolete): 0\nPartition Name: %s\nFlash Filename: %s\nFOTA Filename: \n\n' "$1" "$1" "$2" "$3" "$4"; }
{ pit_entry 1 17408 BOOT boot.img; pit_entry 2 21213 RECOVERY recovery.img; pit_entry 3 2560 DTBO dtbo.img
  pit_entry 4 16 VBMETA vbmeta.img; pit_entry 5 59359995 USERDATA userdata.img; pit_entry 6 5120 EFS efs.img; } > "$pit"
lpit="$t/pit-lower.txt"; sed -e 's/Name: BOOT/Name: boot/; s/Name: RECOVERY/Name: recovery/; s/Name: VBMETA/Name: vbmeta/' "$pit" > "$lpit"
calls() { cat "$HEIMDALL_ARGV.calls" 2>/dev/null | tr '\n' ' '; }
reset() { rm -f "$HEIMDALL_ARGV" "$HEIMDALL_ARGV.calls"; }

# --- dry-run composition
out=$("$flash" --dry-run BOOT="$t/boot.img")
[[ $out == *"heimdall flash"* && $out == *"--BOOT $t/boot.img"* \
   && $out == *"--VBMETA $vb"* && $out == *"--no-reboot"* ]] || { echo "FAIL compose: $out"; fail=1; }
"$flash" --dry-run EFS="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: EFS accepted"; fail=1; }
"$flash" --dry-run --pit "$pit" EFS="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: EFS accepted with pit"; fail=1; }
"$flash" --dry-run BOOT="$t/missing.img" >/dev/null 2>&1 && { echo "FAIL: missing file accepted"; fail=1; }
"$flash" --dry-run VBMETA="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: VBMETA accepted"; fail=1; }
"$flash" --dry-run BOOT="$t/boot.img" BOOT="$t/dtbo.img" >/dev/null 2>&1 && { echo "FAIL: duplicate partition accepted"; fail=1; }
"$flash" --dry-run --bogus BOOT="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: unknown option accepted"; fail=1; }

# --- USERDATA and DTBO need an explicit flag
"$flash" --dry-run USERDATA="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: USERDATA accepted without flag"; fail=1; }
out=$("$flash" --dry-run --allow-userdata USERDATA="$t/boot.img") && [[ $out == *"--USERDATA $t/boot.img"* ]] \
  || { echo "FAIL: --allow-userdata"; fail=1; }
"$flash" --dry-run DTBO="$t/dtbo.img" >/dev/null 2>&1 && { echo "FAIL: DTBO accepted without flag"; fail=1; }
out=$("$flash" --dry-run --allow-dtbo DTBO="$t/dtbo.img") && [[ $out == *"--DTBO $t/dtbo.img"* ]] \
  || { echo "FAIL: --allow-dtbo"; fail=1; }

# --- --keep-vbmeta leaves VBMETA out; --resume is passed through
out=$("$flash" --dry-run --keep-vbmeta --resume RECOVERY="$t/boot.img")
[[ $out == *"--RECOVERY $t/boot.img"* && $out != *VBMETA* && $out == *"--resume"* ]] || { echo "FAIL keep-vbmeta: $out"; fail=1; }

# --- PIT: names checked, case taken from the PIT, sizes checked (blocks x 4096)
out=$("$flash" --dry-run --pit "$lpit" RECOVERY="$t/boot.img") || { echo "FAIL lower pit rc"; fail=1; }
[[ ${out:-} == *"--recovery $t/boot.img"* && $out == *"--vbmeta $vb"* ]] || { echo "FAIL pit case: ${out:-}"; fail=1; }
sed '/Entry #2 ---/,/^$/d' "$pit" > "$t/pit-norec.txt"
err=$("$flash" --dry-run --pit "$t/pit-norec.txt" RECOVERY="$t/boot.img" 2>&1) && { echo "FAIL: partition absent from PIT accepted"; fail=1; }
[[ $err == *"not in PIT"* ]] || { echo "FAIL absent msg: $err"; fail=1; }
truncate -s $((17408*4096)) "$t/fit.img"; truncate -s $((17408*4096+1)) "$t/big.img"
"$flash" --dry-run --pit "$pit" BOOT="$t/fit.img" >/dev/null || { echo "FAIL: exact-size image refused"; fail=1; }
err=$("$flash" --dry-run --pit "$pit" BOOT="$t/big.img" 2>&1) && { echo "FAIL: oversized image accepted"; fail=1; }
[[ $err == *"too large"* ]] || { echo "FAIL oversize msg: $err"; fail=1; }
FLASH_BLOCK_SIZE=512 "$flash" --dry-run --pit "$pit" BOOT="$t/fit.img" >/dev/null 2>&1 && { echo "FAIL: block size override ignored"; fail=1; }
"$flash" --dry-run --pit "$t/nope.txt" BOOT="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: missing PIT file accepted"; fail=1; }
: > "$t/empty.txt"
"$flash" --dry-run --pit "$t/empty.txt" BOOT="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: empty PIT accepted"; fail=1; }

# --- relative image path from another cwd is resolved against the caller's cwd
out=$(cd "$t" && "$flash" --dry-run BOOT=boot.img) || { echo "FAIL relpath: rc"; fail=1; }
[[ ${out:-} == *"--BOOT $t/boot.img "* ]] || { echo "FAIL relpath: ${out:-}"; fail=1; }

# --- dry-run leaves the notes file untouched and never calls heimdall
notes="$t/NOTES.md"; cp NOTES.md "$notes"; before=$(sha256sum < "$notes"); reset
FLASH_NOTES="$notes" "$flash" --dry-run --pit "$pit" BOOT="$t/boot.img" >/dev/null
[ "$(sha256sum < "$notes")" = "$before" ] || { echo "FAIL: dry-run touched notes"; fail=1; }
[ -z "$(calls)" ] || { echo "FAIL: dry-run called heimdall: $(calls)"; fail=1; }

# --- a real run needs a PIT
reset
echo FLASH | FLASH_NOTES="$notes" "$flash" BOOT="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: real run without --pit"; fail=1; }
[ -z "$(calls)" ] || { echo "FAIL: heimdall called without PIT: $(calls)"; fail=1; }

# --- a real run needs the typed word FLASH (wrong word, lower case, empty stdin: all refused)
for word in yes flash ""; do
  reset; cp NOTES.md "$notes"
  printf '%s\n' "$word" | FLASH_NOTES="$notes" "$flash" --pit "$pit" BOOT="$t/boot.img" >/dev/null 2>&1 \
    && { echo "FAIL: confirmation '$word' accepted"; fail=1; }
  [[ " $(calls)" != *" flash "* ]] || { echo "FAIL: flashed after '$word'"; fail=1; }
  [ "$(sha256sum < "$notes")" = "$before" ] || { echo "FAIL: refused run touched notes"; fail=1; }
done
reset
FLASH_NOTES="$notes" "$flash" --pit "$pit" BOOT="$t/boot.img" </dev/null >/dev/null 2>&1 && { echo "FAIL: EOF accepted as confirmation"; fail=1; }
[[ " $(calls)" != *" flash "* ]] || { echo "FAIL: flashed on EOF"; fail=1; }

# --- no device: heimdall detect fails, nothing is flashed, no confirmation asked
reset
out=$(echo FLASH | HEIMDALL_DETECT_RC=1 FLASH_NOTES="$notes" "$flash" --pit "$pit" BOOT="$t/boot.img" 2>&1) \
  && { echo "FAIL: flashed without a detected device"; fail=1; }
[ "$(calls)" = "detect " ] || { echo "FAIL detect-only calls: $(calls)"; fail=1; }
[[ $out == *"no device in Download Mode"* ]] || { echo "FAIL detect msg: $out"; fail=1; }

# --- success: detect then flash, heimdall argv exact, full sha256 of every image logged
cp NOTES.md "$notes"; reset
out=$(echo FLASH | FLASH_NOTES="$notes" "$flash" --pit "$pit" BOOT="$t/boot.img") || { echo "FAIL real: rc"; fail=1; }
[ "$(calls)" = "detect flash " ] || { echo "FAIL call order: $(calls)"; fail=1; }
[[ $out == *"BOOT"* && $out == *"$(sha256sum "$t/boot.img" | cut -c1-16)"* && $out == *"Type FLASH"* ]] || { echo "FAIL summary: $out"; fail=1; }
want=$(printf '%s\n' flash --BOOT "$t/boot.img" --VBMETA "$vb" --no-reboot)
[ "$(cat "$HEIMDALL_ARGV" 2>/dev/null)" = "$want" ] || { echo "FAIL argv: $(cat "$HEIMDALL_ARGV" 2>/dev/null)"; fail=1; }
log=$(tail -n 4 "$notes")
[[ $log == *" flash"* && $log != *FAILED* \
   && $log == *"- BOOT: $(sha256sum "$t/boot.img" | cut -d' ' -f1) $t/boot.img"* \
   && $log == *"- VBMETA: $(sha256sum "$vb" | cut -d' ' -f1) $vb"* ]] || { echo "FAIL success log: $log"; fail=1; }

# --- failure: FAILED entry, exit status propagated
cp NOTES.md "$notes"; reset
echo FLASH | HEIMDALL_RC=7 FLASH_NOTES="$notes" "$flash" --pit "$pit" BOOT="$t/boot.img" >/dev/null; rc=$?
[ $rc = 7 ] || { echo "FAIL failure rc: $rc"; fail=1; }
grep -q "flash FAILED (exit 7)" "$notes" || { echo "FAIL failure log"; fail=1; }

[ $fail = 0 ] && echo "test_flash: OK"; exit $fail
