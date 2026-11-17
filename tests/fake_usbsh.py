#!/usr/bin/env python3
"""Stand-in for tools/usbsh.py in the write-userdata tests: no tablet.

State in $FAKE_DIR/config.json:
  resolve   output of the ": wu-resolve" command (list of strings, one per call;
            the last one repeats)
  tools     output of ": wu-tools"
  dev       path of the file that plays the block device
  fail      "write" (dd fails), "short" (dd reports fewer bytes), "corrupt" (one byte
            flipped after the write) or ""
Every command is appended to $FAKE_DIR/calls.log; ": wu-write" fetches the image from the
URL in the command (the real HTTP server of the script) into "dev".
"""
import hashlib, json, os, re, sys, urllib.request
from pathlib import Path

d = Path(os.environ["FAKE_DIR"])
cfg = json.loads((d / "config.json").read_text())
args = sys.argv[1:]
while args and args[0].startswith("--"):
    args = args[2:]
op, cmd = args[0], args[1]
assert op == "run", args
with open(d / "calls.log", "a") as f:
    f.write(cmd.replace("\n", " ") + "\n")

state = d / "state.json"
st = json.loads(state.read_text()) if state.exists() else {"resolve_calls": 0}

if cmd.startswith(": wu-resolve"):
    outs = cfg["resolve"]
    print(outs[min(st["resolve_calls"], len(outs) - 1)])
    st["resolve_calls"] += 1
elif cmd.startswith(": wu-tools"):
    print(cfg.get("tools", "tools=checked"))
elif cmd.startswith(": wu-write"):
    url = re.search(r"http://[0-9.]+:\d+/f", cmd).group(0)
    target = re.search(r"of=/dev/(\w+)", cmd).group(1)
    assert target == cfg["devname"], target
    data = urllib.request.urlopen(url, timeout=30).read()
    fail = cfg.get("fail", "")
    dev = Path(cfg["dev"])
    if fail == "write":
        st["rc"], st["written"] = 1, 0
    else:
        buf = bytearray(dev.read_bytes())
        buf[:len(data)] = data
        if fail == "corrupt":
            buf[len(data) // 2] ^= 0xFF
        dev.write_bytes(bytes(buf))
        st["rc"] = 0
        st["written"] = len(data) - 4096 if fail == "short" else len(data)
elif cmd.startswith(": wu-poll"):
    print(f"rc={st['rc']}")
    print(f"written={st['written']}")
elif cmd.startswith(": wu-readback"):
    n = int(re.search(r"count=(\d+)", cmd).group(1))
    target = re.search(r"if=/dev/(\w+)", cmd).group(1)
    assert target == cfg["devname"], target
    print(hashlib.sha256(Path(cfg["dev"]).read_bytes()[:n]).hexdigest() + "  -")
else:
    print(f"fake_usbsh: unexpected command {cmd!r}", file=sys.stderr)
    sys.exit(99)
state.write_text(json.dumps(st))
