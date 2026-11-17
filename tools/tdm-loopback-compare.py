#!/usr/bin/env python3
"""Compare the TDM loopback capture with the played noise: lag, exact-match ratio, error stats."""
import sys, wave
import numpy as np
def rd(p):
    w = wave.open(p); d = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2')
    return d.reshape(-1, w.getnchannels()).astype(np.int64), w.getframerate()
ref, _ = rd(sys.argv[1]); cap, _ = rd(sys.argv[2])
for ch in range(min(ref.shape[1], cap.shape[1])):
    r = ref[:, ch]; c = cap[:, ch]
    if not np.any(c):
        print(f"ch{ch}: capture all zero"); continue
    seg = r[48000:48000 + 4800]
    best = None
    for lag_ch in range(2):
        cc = cap[:, lag_ch]
        corr = np.correlate(cc.astype(float), seg.astype(float), mode='valid')
        k = int(np.argmax(np.abs(corr)))
        if best is None or abs(corr[k]) > best[0]:
            best = (abs(corr[k]), lag_ch, k - 48000, np.sign(corr[k]))
    _, src, lag, sgn = best
    cc = cap[:, src]
    n = min(len(r), len(cc) - lag) if lag >= 0 else 0
    a = r[2000:n - 2000]; b = cc[lag + 2000:lag + n - 2000]
    d = b - a
    exact = np.mean(d == 0)
    print(f"played ch{ch} -> captured slot {src}, lag {lag} frames, sign {int(sgn)}, "
          f"exact {exact*100:.4f} %, max|err| {np.max(np.abs(d))}, rms err {np.sqrt(np.mean(d.astype(float)**2)):.2f}, "
          f"frames {len(d)}")
    bad = np.nonzero(d)[0]
    if len(bad):
        x = np.bitwise_xor(a[bad] & 0xffff, b[bad] & 0xffff)
        bits = [int(np.sum((x >> k) & 1)) for k in range(16)]
        print("  differing bit counts b0..b15:", bits)
