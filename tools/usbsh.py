#!/usr/bin/env python3
"""Run commands on the gts7xl USB debug shell and move files over the USB network.

The pmOS initramfs debug shell offers telnet on 172.16.42.1 (the host gets 172.16.42.2
by DHCP). Busybox there has wget, base64 and sha256sum but no nc, so:
  - run:  telnet, one command at a time, exit status read back through a marker;
  - pull: `base64 FILE` over telnet, decoded here;
  - push: a one-file HTTP server on this side, `wget` on the tablet, sha256 checked.

usage: usbsh.py [--host H] [--local-ip IP] [--dry-run] run CMD
       usbsh.py ... pull REMOTE LOCAL
       usbsh.py ... push LOCAL REMOTE

Nothing here writes anywhere but REMOTE (push) and LOCAL (pull).
"""
import argparse, base64, binascii, hashlib, http.server, re, socket, sys, threading, time
from pathlib import Path

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240
END_RE = re.compile(rb"__END__ (\d+)")
READY = b"__READY__"


class ShellError(RuntimeError):
    pass


class Shell:
    """Telnet to the debug shell; refuses every option, so the stream is plain text."""

    def __init__(self, host="172.16.42.1", port=23, timeout=30.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.timeout = timeout
        self.buf = b""
        # Quiet shell: no echo of what we send, no prompt in the output.
        self._send(b"stty -echo 2>/dev/null; PS1=''; echo __RE\"\"ADY__\n")
        self._read_until(lambda b: READY in b)
        self.buf = b""

    def _send(self, data):
        self.sock.sendall(data.replace(bytes([IAC]), bytes([IAC, IAC])))

    def _recv(self):
        data = self.sock.recv(65536)
        if not data:
            raise ShellError("connection closed by the tablet")
        out, i = bytearray(), 0
        while i < len(data):
            c = data[i]
            if c != IAC:
                out.append(c); i += 1; continue
            if i + 1 >= len(data):
                break
            cmd = data[i + 1]
            if cmd in (DO, DONT, WILL, WONT) and i + 2 < len(data):
                opt = data[i + 2]
                if cmd == DO:
                    self.sock.sendall(bytes([IAC, WONT, opt]))
                elif cmd == WILL:
                    self.sock.sendall(bytes([IAC, DONT, opt]))
                i += 3
            elif cmd == SB:
                j = data.find(bytes([IAC, SE]), i)
                i = len(data) if j < 0 else j + 2
            elif cmd == IAC:
                out.append(IAC); i += 2
            else:
                i += 2
        self.buf += bytes(out)

    def _read_until(self, done):
        deadline = time.monotonic() + self.timeout
        while not done(self.buf):
            if time.monotonic() > deadline:
                raise ShellError(f"timeout, got: {self.buf[-200:]!r}")
            self._recv()

    def run(self, cmd):
        """Run one shell command, return (exit status, output bytes)."""
        self.buf = b""
        self._send(cmd.encode() + b'; echo "__E""ND__ $?"\n')
        self._read_until(lambda b: END_RE.search(b) is not None)
        m = END_RE.search(self.buf)
        out = self.buf[:m.start()].replace(b"\r\n", b"\n")
        # If the terminal still echoes, drop the echo of our own line.
        out = b"".join(l for l in out.splitlines(keepends=True) if b'__E""ND__' not in l)
        return int(m.group(1)), out

    def close(self):
        try:
            self.sock.sendall(b"exit\n")
        finally:
            self.sock.close()


def decode_base64_listing(text):
    """Decode `base64 FILE` output, ignoring anything that is not base64 (stray escapes)."""
    lines = [l.strip() for l in text.decode(errors="replace").splitlines()]
    data = "".join(l for l in lines if re.fullmatch(r"[A-Za-z0-9+/=]+", l))
    return base64.b64decode(data, validate=True)


def pull(sh, remote, local):
    rc, out = sh.run(f"base64 '{remote}'")
    if rc:
        raise ShellError(f"base64 {remote} failed ({rc}): {out[-200:]!r}")
    data = decode_base64_listing(out)
    rc, out = sh.run(f"sha256sum '{remote}'")
    want = out.split()[0].decode() if rc == 0 and out.split() else None
    if want and want != hashlib.sha256(data).hexdigest():
        raise ShellError(f"pull {remote}: sha256 mismatch")
    Path(local).write_bytes(data)
    return len(data)


class _OneFile(http.server.BaseHTTPRequestHandler):
    path_to_serve = None

    def do_GET(self):
        data = Path(self.path_to_serve).read_bytes()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def push(sh, local, remote, local_ip="172.16.42.2"):
    handler = type("H", (_OneFile,), {"path_to_serve": str(local)})
    srv = http.server.ThreadingHTTPServer((local_ip, 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    try:
        port = srv.server_address[1]
        rc, out = sh.run(f"wget -q -O '{remote}' http://{local_ip}:{port}/f && sha256sum '{remote}'")
    finally:
        srv.shutdown(); srv.server_close()
    want = hashlib.sha256(Path(local).read_bytes()).hexdigest()
    if rc or not out.split() or out.split()[0].decode() != want:
        raise ShellError(f"push {local} -> {remote} failed ({rc}): {out[-200:]!r}")
    return want


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default="172.16.42.1")
    ap.add_argument("--port", type=int, default=23)
    ap.add_argument("--local-ip", default="172.16.42.2")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--dry-run", action="store_true")
    sub = ap.add_subparsers(dest="op", required=True)
    r = sub.add_parser("run"); r.add_argument("cmd")
    p = sub.add_parser("pull"); p.add_argument("remote"); p.add_argument("local")
    q = sub.add_parser("push"); q.add_argument("local"); q.add_argument("remote")
    a = ap.parse_args(argv)

    if a.dry_run:
        what = {"run": lambda: f"run: {a.cmd}",
                "pull": lambda: f"pull: {a.host}:{a.remote} -> {a.local}",
                "push": lambda: f"push: {a.local} -> {a.host}:{a.remote}"}[a.op]()
        print(f"[dry-run] {what}")
        return 0

    sh = Shell(a.host, a.port, a.timeout)
    try:
        if a.op == "run":
            rc, out = sh.run(a.cmd)
            sys.stdout.buffer.write(out)
            return rc
        if a.op == "pull":
            n = pull(sh, a.remote, a.local)
            print(f"pulled {a.remote} ({n} bytes) -> {a.local}")
        else:
            h = push(sh, a.local, a.remote, a.local_ip)
            print(f"pushed {a.local} -> {a.remote} (sha256 {h[:16]})")
        return 0
    finally:
        sh.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ShellError, OSError, binascii.Error) as e:
        print(f"usbsh: {e}", file=sys.stderr)
        sys.exit(1)
