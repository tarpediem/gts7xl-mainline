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

# --- dry-run composition
out=$("$flash" --dry-run BOOT="$t/boot.img" DTBO="$t/dtbo.img")
[[ $out == *"heimdall flash"* && $out == *"--BOOT $t/boot.img"* && $out == *"--DTBO $t/dtbo.img"* \
   && $out == *"--VBMETA $vb"* && $out == *"--no-reboot"* ]] || { echo "FAIL compose: $out"; fail=1; }
"$flash" --dry-run EFS="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: EFS accepted"; fail=1; }
"$flash" --dry-run BOOT="$t/missing.img" >/dev/null 2>&1 && { echo "FAIL: missing file accepted"; fail=1; }
"$flash" --dry-run VBMETA="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: VBMETA accepted"; fail=1; }

# --- relative image path from another cwd is resolved against the caller's cwd
out=$(cd "$t" && "$flash" --dry-run BOOT=boot.img) || { echo "FAIL relpath: rc"; fail=1; }
[[ ${out:-} == *"--BOOT $t/boot.img "* ]] || { echo "FAIL relpath: ${out:-}"; fail=1; }

# --- dry-run leaves the notes file untouched
notes="$t/NOTES.md"; cp NOTES.md "$notes"; before=$(sha256sum < "$notes")
FLASH_NOTES="$notes" "$flash" --dry-run BOOT="$t/boot.img" >/dev/null
[ "$(sha256sum < "$notes")" = "$before" ] || { echo "FAIL: dry-run touched notes"; fail=1; }

# --- success: heimdall argv exact, full sha256 of every image logged after the flash
cp NOTES.md "$notes"
FLASH_NOTES="$notes" "$flash" BOOT="$t/boot.img" || { echo "FAIL real: rc"; fail=1; }
want=$(printf '%s\n' flash --BOOT "$t/boot.img" --VBMETA "$vb" --no-reboot)
[ "$(cat "$HEIMDALL_ARGV" 2>/dev/null)" = "$want" ] || { echo "FAIL argv: $(cat "$HEIMDALL_ARGV" 2>/dev/null)"; fail=1; }
log=$(tail -n 4 "$notes")
[[ $log == *" flash"* && $log != *FAILED* \
   && $log == *"- BOOT: $(sha256sum "$t/boot.img" | cut -d' ' -f1) $t/boot.img"* \
   && $log == *"- VBMETA: $(sha256sum "$vb" | cut -d' ' -f1) $vb"* ]] || { echo "FAIL success log: $log"; fail=1; }

# --- failure: FAILED entry, exit status propagated
cp NOTES.md "$notes"
HEIMDALL_RC=7 FLASH_NOTES="$notes" "$flash" BOOT="$t/boot.img" >/dev/null; rc=$?
[ $rc = 7 ] || { echo "FAIL failure rc: $rc"; fail=1; }
grep -q "flash FAILED (exit 7)" "$notes" || { echo "FAIL failure log"; fail=1; }

[ $fail = 0 ] && echo "test_flash: OK"; exit $fail
