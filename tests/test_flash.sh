#!/usr/bin/env bash
# tests/test_flash.sh — behaviour of tools/flash.sh.
# The real path is exercised only through a fake FLASH_SSH transport with stub
# sudo/heimdall first in PATH; the real heimdall and sudo are never reachable.
set -u; cd "$(dirname "$0")/.." || exit 1; fail=0
repo=$(pwd -P)
t=$(mktemp -d); t=$(cd "$t" && pwd -P); trap 'rm -rf "$t"' EXIT
echo x > "$t/boot.img"; echo y > "$t/dtbo.img"

# --- dry-run composition
out=$(tools/flash.sh --dry-run BOOT="$t/boot.img" DTBO="$t/dtbo.img")
[[ $out == *"heimdall flash"* && $out == *"--BOOT $t/boot.img"* && $out == *"--DTBO $t/dtbo.img"* \
   && $out == *"--VBMETA $repo/tools/images/vbmeta-disabled.img"* && $out == *"--no-reboot"* ]] || { echo "FAIL compose: $out"; fail=1; }
tools/flash.sh --dry-run EFS="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: EFS accepted"; fail=1; }
tools/flash.sh --dry-run BOOT="$t/missing.img" >/dev/null 2>&1 && { echo "FAIL: missing file accepted"; fail=1; }
tools/flash.sh --dry-run VBMETA="$t/boot.img" >/dev/null 2>&1 && { echo "FAIL: VBMETA accepted"; fail=1; }

# --- relative image path from another cwd is resolved against the caller's cwd
out=$(cd "$t" && "$repo/tools/flash.sh" --dry-run BOOT=boot.img) || { echo "FAIL relpath: rc"; fail=1; }
[[ ${out:-} == *"--BOOT $t/boot.img "* ]] || { echo "FAIL relpath: ${out:-}"; fail=1; }

# --- dry-run leaves the notes file untouched
notes="$t/NOTES.md"; cp NOTES.md "$notes"; before=$(sha256sum < "$notes")
FLASH_NOTES="$notes" tools/flash.sh --dry-run BOOT="$t/boot.img" >/dev/null
[ "$(sha256sum < "$notes")" = "$before" ] || { echo "FAIL: dry-run touched notes"; fail=1; }

# --- fake transport with stubs (never the real sudo/heimdall)
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
export HEIMDALL_ARGV="$t/argv"
vb="$repo/tools/images/vbmeta-disabled.img"

# success: heimdall argv exact, full sha256 of every image logged after the flash
cp NOTES.md "$notes"
FLASH_SSH="$t/fake-ssh" FLASH_NOTES="$notes" tools/flash.sh BOOT="$t/boot.img" >/dev/null 2>&1 || { echo "FAIL real: rc"; fail=1; }
want=$(printf '%s\n' flash --BOOT "$t/boot.img" --VBMETA "$vb" --no-reboot)
[ "$(cat "$HEIMDALL_ARGV" 2>/dev/null)" = "$want" ] || { echo "FAIL argv: $(cat "$HEIMDALL_ARGV" 2>/dev/null)"; fail=1; }
log=$(tail -n 4 "$notes")
[[ $log == *" flash"* && $log != *FAILED* \
   && $log == *"- BOOT: $(sha256sum "$t/boot.img" | cut -d' ' -f1) $t/boot.img"* \
   && $log == *"- VBMETA: $(sha256sum "$vb" | cut -d' ' -f1) $vb"* ]] || { echo "FAIL success log: $log"; fail=1; }

# failure: FAILED entry, exit status propagated
cp NOTES.md "$notes"
HEIMDALL_RC=7 FLASH_SSH="$t/fake-ssh" FLASH_NOTES="$notes" tools/flash.sh BOOT="$t/boot.img" >/dev/null 2>&1; rc=$?
[ $rc = 7 ] || { echo "FAIL failure rc: $rc"; fail=1; }
grep -q "flash FAILED (exit 7)" "$notes" || { echo "FAIL failure log"; fail=1; }

[ $fail = 0 ] && echo "test_flash: OK"; exit $fail
