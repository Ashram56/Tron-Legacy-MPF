#!/usr/bin/env python3
"""Compare Godot's classic DMD dump with PinMAME's for one scenario, deff window by deff window.

    dmd_conform.py REF.dmd REF.jsonl GODOT.dmd GODOT.jsonl [--step 0.025] [--shift 2]

REF: tron_ref (TRON_DMDLOG=...); GODOT: run with TRON_TRACE_WALL=1 and --dmd-dump (game/tools/dmd_dump.gd).
Windows start at paired deff_start events (same id, in order); frames are sampled every STEP seconds; a sample matches
when the shade arrays are equal within +-SHIFT samples. Prints per deff id: samples, % exact, mean % dots, worst sample.
"""
import argparse, collections, json, struct
import numpy as np


def load_dmd(p):
    b = open(p, "rb").read(); i = 0; ts = []; fr = []
    while i + 20 <= len(b):
        t, w, h, d = struct.unpack_from("<d3i", b, i); i += 20
        fr.append(np.frombuffer(b, np.uint8, w * h, i)); ts.append(t); i += w * h
    return np.array(ts), fr


def starts(p, key):
    out = []
    for l in open(p):
        e = json.loads(l)
        if e["ev"] == "deff_start" and key in e:
            out.append((e["id"], e[key]))
    return out


def pair(a, b):
    """Greedy pairing of two id sequences by longest common subsequence."""
    n, m = len(a), len(b); L = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            L[i][j] = L[i + 1][j + 1] + 1 if a[i][0] == b[j][0] else max(L[i + 1][j], L[i][j + 1])
    i = j = 0; out = []
    while i < n and j < m:
        if a[i][0] == b[j][0]: out.append((i, j)); i += 1; j += 1
        elif L[i + 1][j] >= L[i][j + 1]: i += 1
        else: j += 1
    return out


def at(ts, fr, t):
    k = np.searchsorted(ts, t, side="right") - 1
    return fr[k] if k >= 0 else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ref_dmd"); ap.add_argument("ref_trace"); ap.add_argument("god_dmd")
    ap.add_argument("god_trace"); ap.add_argument("--step", type=float, default=0.025); ap.add_argument("--shift", type=int, default=2)
    ap.add_argument("--csv")
    a = ap.parse_args()
    rt, rf = load_dmd(a.ref_dmd); gt, gf = load_dmd(a.god_dmd)
    rs = starts(a.ref_trace, "t"); gs = starts(a.god_trace, "wall")
    pr = pair(rs, gs)
    stats = collections.defaultdict(lambda: [0, 0, 0.0, 100.0, 0]); rows = []; cov = collections.defaultdict(lambda: [0, 0, 0.0])
    for n, (i, j) in enumerate(pr):
        ident = rs[i][0]
        end_r = rs[pr[n + 1][0]][1] if n + 1 < len(pr) else rs[i][1] + 5
        end_g = gs[pr[n + 1][1]][1] if n + 1 < len(pr) else gs[j][1] + 5
        dur = min(end_r - rs[i][1], end_g - gs[j][1], 30.0)
        k = int(dur / a.step)
        R = [at(rt, rf, rs[i][1] + s * a.step) for s in range(k)]
        G = [at(gt, gf, gs[j][1] + s * a.step) for s in range(k + a.shift)]
        for s in range(k):
            if R[s] is None: continue
            best = 0; ex = False
            for d in range(-a.shift, a.shift + 1):
                if 0 <= s + d < len(G) and G[s + d] is not None:
                    sc = float((R[s] == G[s + d]).mean()); best = max(best, sc); ex |= sc == 1.0
            st = stats[ident]; st[0] += 1; st[1] += ex; st[2] += best; st[3] = min(st[3], best * 100)
            if not ex: st[4] += 1; rows.append((ident, round(rs[i][1] + s * a.step, 3), round(best * 100, 2)))
    print("deff  samples  exact%   mean%dots  worst%")
    tot = [0, 0]
    for ident in sorted(stats):
        n, ex, sc, worst, _ = stats[ident]; tot[0] += n; tot[1] += ex
        print("%4d  %7d  %6.1f  %9.2f  %6.1f" % (ident, n, 100 * ex / n, 100 * sc / n, worst))
    print("\nFrame coverage (a frame of PinMAME's window also shown by Godot within -0.2..+0.6 s of the window):")
    print("deff  ref_frames  found%  best_dots_of_missing%")
    ct = [0, 0]
    for n, (i, j) in enumerate(pr):
        ident = rs[i][0]
        end_r = rs[pr[n + 1][0]][1] if n + 1 < len(pr) else rs[i][1] + 5
        end_g = gs[pr[n + 1][1]][1] if n + 1 < len(pr) else gs[j][1] + 5
        ks = [k for k in range(len(rt)) if rs[i][1] <= rt[k] < end_r]
        gk = [k for k in range(len(gt)) if gs[j][1] - 0.2 <= gt[k] < end_g + 0.6]
        gset = {gf[k].tobytes() for k in gk}
        uniq = {rf[k].tobytes(): rf[k] for k in ks}
        found = sum(u in gset for u in uniq)
        miss = [max(float((r == gf[k]).mean()) for k in gk) for u, r in uniq.items() if u not in gset and gk]
        cov[ident][0] += len(uniq); cov[ident][1] += found; cov[ident][2] += sum(miss)
        ct[0] += len(uniq); ct[1] += found
    for ident in sorted(cov):
        u, f, m = cov[ident]
        print("%4d  %10d  %6.1f  %6.1f" % (ident, u, 100 * f / max(u, 1), 100 * m / (u - f) if u > f else 100))
    print("frames found overall: %d / %d (%.1f%%)" % (ct[1], ct[0], 100 * ct[1] / max(ct[0], 1)))
    print("paired deff starts: %d of ref %d / godot %d; samples exact %.2f%%" % (len(pr), len(rs), len(gs), 100 * tot[1] / max(tot[0], 1)))
    if a.csv:
        open(a.csv, "w").write("deff,ref_t,best_dots_pct\n" + "".join("%d,%s,%s\n" % r for r in rows))


if __name__ == "__main__":
    main()
