#!/usr/bin/env python3
"""Flasher and shaker activity from a trace's `coil` events (ROM reference or rebuild), and their comparison.

The ROM reference logs the driver outputs as libpinmame reports them: a flasher that a lamp effect drives
with a PWM pattern (dimmed / breathing) shows up as a train of short on/off pulses, a plain coil_pulse
as one longer pulse, and the reported on time includes the output's smoothing. The rebuild pulses the
flashers with the captured show's pulse times. Pulse counts and on times therefore differ while what a
player sees (a flash, at that moment) is the same, so the coils are compared as *bursts*:

  burst   a run of on pulses where each pulse starts less than GAP after the previous one ended
          (a PWM train or back-to-back pulses = one flash)

Comparison (compare(), used by scripts/trace_check.py when "coil" is in --events): per compared coil the
bursts of both traces are matched one to one in time order, a candidate burst matching a reference burst
when their starts are within TOL seconds. The result is the matched bursts over the bursts of the trace
with more of them, summed over the coils. Burst lengths are not compared (see above).

Compared coils: the flashers (17-21, 25-29, 31, 32) and the shaker motor (8), which the rules drive.
The other solenoids (trough, VUK and eject kickers, flippers, slings, pops, motors, relays) follow the
ball and the physics of the run, which the rebuild's trace does not log; they are not compared.

Usage: scripts/coil_state.py --compare <ref.jsonl> <cand.jsonl>
       scripts/coil_state.py <trace.jsonl>           (bursts per coil)
"""
import json
import sys

COILS = (8, 17, 18, 19, 20, 21, 25, 26, 27, 28, 29, 31, 32)
GAP = 0.08                    # s: a pulse starting this soon after the previous one ended continues the burst
TOL = 0.25                    # s: burst start tolerance (as the event comparison's default --tol)


def load(path):
    """-> {coil: [(t, on)]} with times relative to "ready" (events before it are left out)."""
    t0, out = None, {}
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("ev") == "ready":
            t0 = e["t"]
        elif t0 is not None and e.get("ev") == "coil" and e.get("coil") in COILS:
            out.setdefault(e["coil"], []).append((e["t"] - t0, 1 if e.get("on") else 0))
    return out


def bursts(events, gap=GAP):
    """[(start, end)] of the bursts of one coil's on/off events."""
    out, start, last_off = [], None, None
    for t, on in events:
        if on and start is None:
            if out and last_off is not None and t - last_off < gap:
                start = out.pop()[0]          # continues the previous burst
            else:
                start = t
        elif not on and start is not None:
            out.append((start, t))
            start, last_off = None, t
    if start is not None:
        out.append((start, start))
    return out


def match(ref, cand, tol=TOL):
    """One-to-one matching of burst starts in time order -> (matched, [unmatched ref], [unmatched cand])."""
    used = [False] * len(cand)
    matched, lost = 0, []
    j0 = 0
    for rs, _ in ref:
        while j0 < len(cand) and cand[j0][0] < rs - tol:
            j0 += 1
        for j in range(j0, len(cand)):
            if cand[j][0] > rs + tol:
                lost.append(rs)
                break
            if not used[j]:
                used[j] = True
                matched += 1
                break
        else:
            lost.append(rs)
    extra = [c[0] for c, u in zip(cand, used) if not u]
    return matched, lost, extra


def compare(ref_path, cand_path, verbose=True):
    """-> (matched bursts, compared bursts, {coil: (ref bursts, cand bursts, lost, extra)})."""
    r, c = load(ref_path), load(cand_path)
    good = total = 0
    per = {}
    for coil in COILS:
        rb, cb = bursts(r.get(coil, [])), bursts(c.get(coil, []))
        if not rb and not cb:
            continue
        m, lost, extra = match(rb, cb)
        good += m
        total += max(len(rb), len(cb))
        if lost or extra:
            per[coil] = (len(rb), len(cb), lost, extra)
    if verbose:
        for coil, (nr, nc, lost, extra) in sorted(per.items()):
            print("  coil %2d: ref %3d cand %3d bursts; missing at %s; extra at %s" % (
                coil, nr, nc, ",".join("%.2f" % t for t in lost[:4]) or "-",
                ",".join("%.2f" % t for t in extra[:4]) or "-"))
    return good, total, per


if __name__ == "__main__":
    if sys.argv[1] == "--compare":
        g, n, _ = compare(sys.argv[2], sys.argv[3])
        print("coil %d/%d bursts match" % (g, n))
        sys.exit(0)
    for coil, evs in sorted(load(sys.argv[1]).items()):
        b = bursts(evs)
        print("coil %2d: %3d bursts %s" % (coil, len(b), " ".join("%.2f" % s for s, _ in b[:12])))
