#!/usr/bin/env python3
"""Run every reference scenario (or the ones named) and print one line per scenario and event kind.

Usage: .venv/bin/python scripts/scenario_report.py [name ...]
"""
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TRACES = os.path.join(ROOT, "assets", "rules", "traces")


def main(names):
    names = names or sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(TRACES, "*.txt")))
    for name in names:
        run = subprocess.run([sys.executable, "-m", "tests.scenario", name], cwd=ROOT,
                             capture_output=True, text=True)
        if run.returncode:
            err = (run.stderr.strip().splitlines() or ["?"])[-1]
            print("{:42s} RUN FAILED: {}".format(name, err[:120]))
            continue
        cmp = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "trace_check.py"), name],
                             cwd=ROOT, capture_output=True, text=True).stdout
        cells = []
        for line in cmp.splitlines():
            m = re.match(r"(\w+)\s+OK\s+(\d+)", line)
            if m:
                cells.append("{}=ok".format(m.group(1)[:5]))
                continue
            m = re.match(r"(\w+)\s+DIFF (\d+)/(\d+) samples", line)     # lamp: matching samples / samples
            if m:
                cells.append("{}={}/{}".format(m.group(1)[:5], m.group(2), m.group(3)))
                continue
            m = re.match(r"(\w+)\s+DIFF at event #(\d+) \(reference has (\d+)", line)
            if m:
                cells.append("{}={}/{}".format(m.group(1)[:5], m.group(2), m.group(3)))
        print("{:42s} {}".format(name, " ".join(cells)))


if __name__ == "__main__":
    main(sys.argv[1:])
