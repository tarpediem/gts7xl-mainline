# tests/test_omarchy_pacman_sync.py
"""refresh_sync_dbs (tools/omarchy-pacman-sync.sh): the Omarchy image must ship only sync
databases fetched from the stable mirrors (never the live ALARM ones, never the build-only
[offline] repo's) and no package newer than the stable snapshot unless explicitly allowed."""
import subprocess
from pathlib import Path

LIB = Path(__file__).parent.parent / "tools" / "omarchy-pacman-sync.sh"
REPOS = ["core", "extra", "alarm", "omarchy"]


def run(tmp_path, mirrorlist="Server = https://arm-stable-mirror.omarchy.org/$arch/$repo\n",
        upgrades="", installed=None, allow="", syy_rc=0):
    root = tmp_path / "root"
    sync = root / "var/lib/pacman/sync"
    sync.mkdir(parents=True)
    (root / "etc/pacman.d").mkdir(parents=True)
    (root / "etc/pacman.d/mirrorlist").write_text(mirrorlist)
    for stale in ("core.db", "extra.db", "offline.db", "extra.files"):
        (sync / stale).write_text("STALE")
    calls = tmp_path / "calls"
    installed = installed or {}
    q_cases = "".join(f'{n}) echo "{n} {v}";; ' for n, v in installed.items())
    script = f"""
set -euo pipefail
R={root}; WORK={tmp_path}; ALLOW_NEWER_PKGS="{allow}"
log() {{ echo "LOG $*"; }}
in_root() {{
  echo "$*" >> {calls}
  case "$1 ${{2:-}}" in
    "pacman -Syy") for r in {' '.join(REPOS)}; do echo FRESH > {sync}/$r.db; done
                   echo FRESH > {sync}/offline.db; return {syy_rc};;
    "pacman-conf --repo-list") printf '%s\\n' {' '.join(REPOS)};;
    "pacman -Suu") printf '{upgrades}';;
    "pacman -Q") case "$3" in {q_cases} *) return 1;; esac;;
    "vercmp "*) python3 -c 'import sys; a,b=sys.argv[1:]; print((a>b)-(a<b))' "$2" "$3";;
  esac
}}
. {LIB}
refresh_sync_dbs
"""
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    return p, sync, calls.read_text() if calls.exists() else ""


def test_fresh_dbs_only(tmp_path):
    p, sync, calls = run(tmp_path)
    assert p.returncode == 0, p.stderr
    assert "pacman -Syy --noconfirm" in calls
    assert sorted(f.name for f in sync.iterdir()) == sorted(f"{r}.db" for r in REPOS)
    assert all(f.read_text().strip() == "FRESH" for f in sync.iterdir())
    assert "removed stray offline.db" in p.stdout


def test_live_alarm_mirror_refused(tmp_path):
    p, sync, calls = run(tmp_path, mirrorlist="Server = http://mirror.archlinuxarm.org/$arch/$repo\n")
    assert p.returncode != 0 and "live ALARM mirror" in p.stderr
    assert calls == ""                      # nothing fetched
    assert (sync / "core.db").read_text() == "STALE"


def test_commented_live_mirror_ok(tmp_path):
    p, _, _ = run(tmp_path, mirrorlist="# Server = http://mirror.archlinuxarm.org/$arch/$repo\n"
                                         "Server = https://arm-stable-mirror.omarchy.org/$arch/$repo\n")
    assert p.returncode == 0, p.stderr


def test_syy_failure(tmp_path):
    p, _, _ = run(tmp_path, syy_rc=1)
    assert p.returncode != 0 and "pacman -Syy failed" in p.stderr


def test_newer_package_refused(tmp_path):
    p, _, _ = run(tmp_path, upgrades="firefox 150\\nbtop 2\\n", installed={"firefox": "160", "btop": "1"})
    assert p.returncode != 0
    assert "firefox 160 (snapshot 150)" in p.stderr and "btop" not in p.stderr


def test_newer_package_allowed(tmp_path):
    p, _, _ = run(tmp_path, upgrades="firefox 150\\n", installed={"firefox": "160"}, allow="firefox")
    assert p.returncode == 0, p.stderr
    assert "allowed by ALLOW_NEWER_PKGS" in p.stdout
