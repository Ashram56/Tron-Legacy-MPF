"""Trace logger: writes rule events in the JSON-lines format of the asset repo's reference traces.

See assets/rules/tools/trace/README.md ("Trace format"). Times are seconds of machine clock; the
harness writes a "ready" event when the scenario starts, and trace_compare.py aligns on it.
"""
import json
import os


class Trace:

    def __init__(self, machine, path=None):
        self.machine = machine
        self.path = path or os.environ.get("TRON_TRACE")
        self._file = open(self.path, "w", encoding="utf-8") if self.path else None
        self.events = []        # kept in memory for tests

    def log(self, ev, **fields):
        rec = {"t": round(self.machine.clock.get_time(), 4), "ev": ev}
        rec.update(fields)
        self.events.append(rec)
        if self._file:
            self._file.write(json.dumps(rec) + "\n")
            self._file.flush()

    def of(self, ev):
        return [e for e in self.events if e["ev"] == ev]

    def close(self):
        if self._file:
            self._file.close()
            self._file = None
