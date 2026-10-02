#!/usr/bin/env python3
"""Steady lamp states from a trace's `lamp` events (ROM reference or rebuild).

The ROM's lamp output is the game image (lamp on / off, plus a flash mask that blanks flashing lamps
every other 9-tick phase), overridden by the lamp-matrix effects (leffs) and lamp layers. Exact toggle
times differ between the ROM and the rebuild (flash phase, leff frame timing), so lamps are compared
as *steady states* over a short window ending at a sample time:

  "1"  on for the whole window          "0"  off for the whole window
  "F"  flashing: >= 2 changes, every gap 0.10-0.20 s (the ROM flash rate, 146 ms per phase)
  "f"  fast/other blinking (a feature's own blink task, a leff frame loop, ...): anything else
       that changed inside the window; compared only as "changing" ("f" equals "F")
  "~"  changed once inside the window (in transition): not compared
  Up to two isolated pulses shorter than BLIP (one-frame glitches when a layer is handed over) do not
  count as changes.

Comparison (compare(), used by scripts/trace_check.py when "lamp" is in --events): the lamps are
sampled at every `mark` (the scenario's own checkpoints, the n-th mark of each trace) and every
SAMPLE_EVERY seconds. A lamp is left out of a sample while a lamp-matrix effect (leff) that draws it
runs in either trace inside the window: leff-period output comes from the leff's captured show and is
checked through the leff_start comparison. Lamps 101+ (other outputs) are not compared.

Usage: scripts/lamp_state.py <trace.jsonl> <t> [t ...]   (t relative to "ready")
       scripts/lamp_state.py --compare <ref.jsonl> <cand.jsonl>
"""
import bisect
import csv
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SAMPLE_EVERY = 1.0

LAMPS = range(1, 81)          # 101+ are other outputs (not the lamp matrix)
WINDOW = 0.75                 # s: >= 2 flash periods (2 x 0.29 s)
FLASH = (0.10, 0.20)          # s between two changes of a flashing lamp
BLIP = 0.03                   # s: shorter isolated pulses are ignored


def load(path):
    """-> (events, t0, {lamp: ([times], [states])}) with times relative to "ready"."""
    evs = [json.loads(line) for line in open(path) if line.strip()]
    t0 = next((e["t"] for e in evs if e.get("ev") == "ready"), 0.0)
    lamps = {}
    for e in evs:
        if e.get("ev") == "lamp" and e["lamp"] in LAMPS:
            ts, ss = lamps.setdefault(e["lamp"], ([], []))
            t = e["t"] - t0
            if ss and ss[-1] == e["state"]:
                continue
            ts.append(t)
            ss.append(e["state"])
    return evs, t0, lamps


def state(lamps, lamp, t, window=WINDOW):
    ts, ss = lamps.get(lamp, ((), ()))
    i = bisect.bisect_right(ts, t)
    cur = ss[i - 1] if i else 0
    j = bisect.bisect_right(ts, t - window)
    changes = ts[j:i]
    if not changes:
        return str(cur)
    if len(changes) <= 4:
        # isolated blips (a layer or leff hand-over leaves a lamp off for one frame): steady, not blinking
        k = j
        blips = all(ss[x] != cur and x + 1 < len(ts) and ts[x + 1] - ts[x] < BLIP
                    for x in range(k, i) if ss[x] != cur)
        if blips and ss[i - 1] == cur and (i - j) % 2 == 0:
            return str(cur)
    gaps = [b - a for a, b in zip(changes, changes[1:])]
    if len(changes) >= 3 and all(FLASH[0] <= g <= FLASH[1] for g in gaps):
        return "F"
    if len(changes) == 1:
        return "~"           # changed once inside the window: in transition, not compared
    return "f"


def snapshot(lamps, t, window=WINDOW):
    return {n: state(lamps, n, t, window) for n in LAMPS}


def same(a, b):
    if "~" in (a, b):
        return True
    if a in "Ff" and b in "Ff":
        return True
    return a == b


def fmt(snap):
    out = []
    for k in ("1", "F", "f", "~"):
        ls = [n for n, s in snap.items() if s == k]
        if ls:
            out.append("%s:%s" % (k, ",".join(map(str, ls))))
    return " ".join(out)


def leff_table():
    """leff id -> (lamp numbers it draws, seconds it runs or None = until stopped)."""
    names = {}
    lights = os.path.join(ROOT, "game", "config", "rom", "lights.yaml")
    cur = None
    for line in open(lights):
        line = line.rstrip()
        if line.startswith("  l_") and line.endswith(":"):
            cur = line.strip()[:-1]
        elif cur and line.strip().startswith("number:"):
            num = line.split(":")[1].split("#")[0].strip()
            if num.isdigit():
                names[cur] = int(num)
    table = {}
    with open(os.path.join(ROOT, "assets", "mpf_package", "lamp_effects.csv")) as f:
        for row in csv.DictReader(f):
            lamps = {names[n] for n in row["lamps"].split() if n in names}
            if row["tokens"]:
                lamps.add("token")
            length = float(row["length_ms"]) / 1000 if row["loops"] == "0" and row["length_ms"] else None
            table[int(row["leff"])] = (lamps, length)
    return table


def leff_spans(evs, t0, table):
    """[(start, end, lamps)] of the leffs started in a trace (end None = still running at the end)."""
    spans, open_ = [], {}
    for e in evs:
        ev = e.get("ev")
        t = e["t"] - t0
        if ev == "leff_start":
            lamps, length = table.get(e["id"], (set(), None))
            if not lamps:
                continue
            span = [t, t + length if length else None, lamps]
            spans.append(span)
            open_[e["id"]] = span
        elif ev == "audit" and e.get("id") == 17:
            # game start (audit 17): the ROM kills every task, leff tasks included, without a leff_stop
            for span in open_.values():
                if span[1] is None or span[1] > t:
                    span[1] = t
            open_.clear()
        elif ev == "leff_stop" and e["id"] in open_:
            span = open_.pop(e["id"])
            if span[1] is None or span[1] > t:
                span[1] = t
    return spans


def busy(spans, t, window):
    """Lamps drawn by a leff during (t - window, t]; "token" = a token effect (lamp unknown: all)."""
    out = set()
    for start, end, lamps in spans:
        if start <= t and (end is None or end > t - window):
            out |= lamps
    return out


def compare(ref_path, cand_path, verbose=True):
    """-> (good samples, total samples, [(t, lamp, ref, cand)]) and prints the differences per lamp."""
    table = leff_table()
    r_evs, r_t0, r_lm = load(ref_path)
    c_evs, c_t0, c_lm = load(cand_path)
    r_spans, c_spans = leff_spans(r_evs, r_t0, table), leff_spans(c_evs, c_t0, table)
    r_marks = [e["t"] - r_t0 for e in r_evs if e.get("ev") == "mark"]
    c_marks = [e["t"] - c_t0 for e in c_evs if e.get("ev") == "mark"]
    r_end = max(e["t"] for e in r_evs) - r_t0
    c_end = max(e["t"] for e in c_evs) - c_t0
    samples = [(rt, ct) for rt, ct in zip(r_marks, c_marks) if rt > 0]
    t = SAMPLE_EVERY
    while t <= min(r_end, c_end):
        samples.append((t, t))
        t += SAMPLE_EVERY
    samples.sort()
    diffs, good = [], 0
    for rt, ct in samples:
        skip = busy(r_spans, rt, WINDOW) | busy(c_spans, ct, WINDOW)
        if "token" in skip:
            skip |= set(LAMPS)
        bad = False
        for n in LAMPS:
            if n in skip:
                continue
            a, b = state(r_lm, n, rt), state(c_lm, n, ct)
            if not same(a, b):
                diffs.append((rt, n, a, b))
                bad = True
        good += not bad
    if verbose:
        per = {}
        for t, n, a, b in diffs:
            per.setdefault(n, []).append((t, a, b))
        for n in sorted(per, key=lambda k: -len(per[k])):
            items = per[n]
            print("  lamp %2d: %3d samples, first %.2f ref %s cand %s" % (n, len(items), items[0][0], items[0][1],
                                                                         items[0][2]))
    return good, len(samples), diffs


if __name__ == "__main__":
    if sys.argv[1] == "--compare":
        g, n, _ = compare(sys.argv[2], sys.argv[3])
        print("lamp %d/%d samples match" % (g, n))
        sys.exit(0)
    _, _, lm = load(sys.argv[1])
    for a in sys.argv[2:]:
        print("%7.2f %s" % (float(a), fmt(snapshot(lm, float(a)))))
