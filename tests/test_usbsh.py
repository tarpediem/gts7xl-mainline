# tests/test_usbsh.py
"""tools/usbsh.py against a fake debug shell: a local TCP server that speaks a bit of
telnet (option requests, \\r\\n line ends, a banner and a prompt) in front of a real sh,
with a `wget` stand-in. Covers run (exit status), pull (base64) and push (HTTP + sha256)."""
import importlib.util, os, socket, subprocess, sys, threading
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("usbsh", ROOT / "tools" / "usbsh.py")
usbsh = importlib.util.module_from_spec(spec); spec.loader.exec_module(usbsh)

WGET = '''#!/usr/bin/env python3
import sys, urllib.request
args = sys.argv[1:]
out = args[args.index("-O") + 1]
url = [a for a in args if a.startswith("http")][0]
open(out, "wb").write(urllib.request.urlopen(url).read())
'''


def strip_iac(data):
    out, i = bytearray(), 0
    while i < len(data):
        if data[i] == 255 and i + 1 < len(data):
            i += 3 if data[i + 1] in (251, 252, 253, 254) else 2
        else:
            out.append(data[i]); i += 1
    return bytes(out)


class FakeShell:
    def __init__(self, tmp_path):
        self.bin = tmp_path / "bin"; self.bin.mkdir()
        (self.bin / "wget").write_text(WGET); (self.bin / "wget").chmod(0o755)
        self.cwd = tmp_path
        self.srv = socket.socket(); self.srv.bind(("127.0.0.1", 0)); self.srv.listen(4)
        self.port = self.srv.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._session, args=(conn,), daemon=True).start()

    def _session(self, conn):
        env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}"}
        sh = subprocess.Popen(["sh", "-i"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, cwd=self.cwd, env=env)
        # telnetd asks for options first, then the getty banner and a prompt
        conn.sendall(bytes([255, 251, 1, 255, 251, 3, 255, 253, 24]))
        conn.sendall(b"postmarketOS debug shell\r\n~ # \x1b[6n")

        def out():
            for chunk in iter(lambda: sh.stdout.read1(4096), b""):
                try:
                    conn.sendall(chunk.replace(b"\n", b"\r\n"))
                except OSError:
                    return
        threading.Thread(target=out, daemon=True).start()
        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                data = strip_iac(data)                                 # option replies
                sh.stdin.write(data); sh.stdin.flush()
        except (OSError, BrokenPipeError):
            pass
        sh.kill(); conn.close()

    def close(self):
        self.srv.close()


@pytest.fixture
def fake(tmp_path):
    f = FakeShell(tmp_path); yield f; f.close()


def shell(fake):
    return usbsh.Shell("127.0.0.1", fake.port, timeout=10)


def test_run_returns_status_and_output(fake):
    sh = shell(fake)
    assert sh.run("echo hello") == (0, b"hello\n")
    assert sh.run("false")[0] == 1
    assert sh.run("echo a; echo b >&2; exit_code=3; (exit 3)") == (3, b"a\nb\n")
    sh.close()


def test_pull_binary(fake, tmp_path):
    blob = bytes(range(256)) * 300
    (tmp_path / "remote.bin").write_bytes(blob)
    sh = shell(fake)
    assert usbsh.pull(sh, str(tmp_path / "remote.bin"), tmp_path / "got.bin") == len(blob)
    assert (tmp_path / "got.bin").read_bytes() == blob
    sh.close()


def test_pull_missing_file_fails(fake, tmp_path):
    sh = shell(fake)
    with pytest.raises(usbsh.ShellError):
        usbsh.pull(sh, str(tmp_path / "nope"), tmp_path / "x")
    sh.close()


def test_push(fake, tmp_path):
    src = tmp_path / "local.bin"; src.write_bytes(os.urandom(200_000))
    sh = shell(fake)
    usbsh.push(sh, src, str(tmp_path / "pushed.bin"), local_ip="127.0.0.1")
    assert (tmp_path / "pushed.bin").read_bytes() == src.read_bytes()
    sh.close()


def test_dry_run_connects_to_nothing(capsys):
    assert usbsh.main(["--host", "192.0.2.1", "--dry-run", "run", "kexec -e"]) == 0
    assert "[dry-run] run: kexec -e" in capsys.readouterr().out


def test_decode_ignores_noise():
    assert usbsh.decode_base64_listing(b"\x1b[6n\nAAEC\nAw==\n") == bytes([0, 1, 2, 3])
