#!/usr/bin/env python3
"""Serve one file over HTTP, streamed (a multi-GB image is never read into memory).

usage: serve_file.py FILE BIND_IP [--port N]

Prints "PORT <n>" on stdout once listening, then serves GET /f until killed.
Progress of each transfer goes to stderr (every 64 MiB). Only /f is served.
"""
import argparse, http.server, os, sys, time

CHUNK = 4 << 20
REPORT = 64 << 20


class Handler(http.server.BaseHTTPRequestHandler):
    path_to_serve = None

    def do_GET(self):
        if self.path != "/f":
            self.send_error(404)
            return
        size = os.path.getsize(self.path_to_serve)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.end_headers()
        sent, next_report, t0 = 0, REPORT, time.monotonic()
        with open(self.path_to_serve, "rb") as f:
            while True:
                buf = f.read(CHUNK)
                if not buf:
                    break
                self.wfile.write(buf)
                sent += len(buf)
                if sent >= next_report or sent == size:
                    rate = sent / max(time.monotonic() - t0, 1e-6) / 1e6
                    print(f"serve_file: {sent >> 20}/{size >> 20} MiB ({rate:.1f} MB/s)",
                          file=sys.stderr, flush=True)
                    next_report += REPORT
        print(f"serve_file: sent {sent} bytes", file=sys.stderr, flush=True)

    def log_message(self, *a):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file")
    ap.add_argument("bind")
    ap.add_argument("--port", type=int, default=0)
    a = ap.parse_args(argv)
    if not os.path.isfile(a.file):
        sys.exit(f"serve_file: not a file: {a.file}")
    handler = type("H", (Handler,), {"path_to_serve": a.file})
    srv = http.server.ThreadingHTTPServer((a.bind, a.port), handler)
    print(f"PORT {srv.server_address[1]}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
