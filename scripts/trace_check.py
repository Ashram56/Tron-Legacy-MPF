#!/usr/bin/env python3
"""Compare a rebuild trace with the ROM reference trace for one scenario.

Wraps assets/rules/tools/trace/trace_compare.py. Before comparing it drops events that are not rules
behaviour: OS bookkeeping audits (time played, 59-64), and sounds played from inside a display effect
(in_deff != 0; those belong to the effect's media show, checked separately).

Usage: scripts/trace_check.py <scenario> [--events score,deff_start,...] [--tol 0.25]
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REF = os.path.join(ROOT, "assets", "rules", "traces")
CAND = os.path.join(ROOT, "captures", "traces")
COMPARE = os.path.join(ROOT, "assets", "rules", "tools", "trace", "trace_compare.py")
DEFAULT = "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark"
OS_AUDITS = {59, 60, 61, 62, 63, 64}


def keep(e):
    if e.get("ev") == "audit" and e.get("id") in OS_AUDITS:
        return False
    if e.get("ev") == "sound" and e.get("in_deff", 0) != 0:
        return False
    return True


def filtered(path, tmp):
    """Copy of the trace without non-rules events and without anything before "ready"."""
    out = os.path.join(tmp, os.path.basename(path))
    evs = [json.loads(line) for line in open(path) if line.strip()]
    t0 = next((e["t"] for e in evs if e.get("ev") == "ready"), None)
    with open(out, "w") as g:
        for e in evs:
            if (t0 is None or e["t"] >= t0) and keep(e):
                g.write(json.dumps(e) + "\n")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--events", default=DEFAULT)
    ap.add_argument("--tol", default="0.25")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        ref = filtered(os.path.join(REF, a.scenario + ".jsonl"), os.path.join(tmp, "r") if os.makedirs(
            os.path.join(tmp, "r")) is None else tmp)
        os.makedirs(os.path.join(tmp, "c"))
        cand = filtered(os.path.join(CAND, a.scenario + ".jsonl"), os.path.join(tmp, "c"))
        return subprocess.run([sys.executable, COMPARE, ref, cand, "--tol", a.tol, "--events", a.events]).returncode


if __name__ == "__main__":
    sys.exit(main())
