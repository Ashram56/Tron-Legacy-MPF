#!/usr/bin/env python3
"""Fix GMC 1.0.0's BCP reader in game/addons/mpf-gmc (downloaded, not in git), idempotently.

GMC's poll thread parses whatever bytes the socket holds as whole lines. MPF's "settings" message at connect
is large (every adjustment with its value labels), so a read can end inside it: GMC then parses half a
message, `JSON.parse_string` returns null, `json.error` raises a script error and the BCP thread stops.
Nothing MPF sends after that is handled: no sounds, no music, no callouts (slides queued before may show).
The patch keeps the unfinished end of a read and prepends it to the next one. Upstream (mpf-gmc main, 2026-10)
has the same code. setup.py, run.py and the Docker entrypoint call patch(); it does nothing once applied.

    python scripts/gmc_patch.py        # patch now; prints what it did
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toolchain as tc  # noqa: E402

MARK = "# tron patch: partial BCP lines"

EDITS = [
    ("scripts/bcp_server.gd",
     "var _client: StreamPeerTCP\n",
     "var _client: StreamPeerTCP\n" + MARK + " (scripts/gmc_patch.py): the unfinished end of the last read\n"
     "var _rx_partial := \"\"\n"),
    ("scripts/bcp_server.gd",
     "\t\t_client = _server.take_connection()\n",
     "\t\t_client = _server.take_connection()\n\t\t_rx_partial = \"\"\n"),
    ("scripts/bcp_server.gd",
     "\t\tvar messages := _client.get_string(bytes).split(\"\\n\")\n",
     "\t\t" + MARK + ": parse complete lines only, keep the rest for the next read\n"
     "\t\tvar data := _rx_partial + _client.get_string(bytes)\n"
     "\t\tvar cut := data.rfind(\"\\n\")\n"
     "\t\t_rx_partial = data.substr(cut + 1)\n"
     "\t\tvar messages := PackedStringArray()\n"
     "\t\tif cut >= 0:\n"
     "\t\t\tmessages = data.substr(0, cut).split(\"\\n\")\n"),
    ("scripts/bcp_parse.gd",               # a bad message is logged instead of stopping the BCP thread
     "\t\t\tresult.error = \"Error %s parsing trigger: %s\" % [json.error, message]\n",
     "\t\t\tresult.error = \"Error parsing trigger: %s\" % message   " + MARK + "\n"),
]


def patch(gmc_dir=None, quiet=False):
    """Apply the edits; returns "patched", "in place", "missing" (no GMC yet) or raises on an unknown GMC."""
    gmc_dir = gmc_dir or tc.GMC_DIR
    if not os.path.exists(os.path.join(gmc_dir, "plugin.cfg")):
        return "missing"
    texts = {}
    for rel, _old, _new in EDITS:
        if rel not in texts:
            with open(os.path.join(gmc_dir, *rel.split("/")), encoding="utf-8", newline="") as f:
                texts[rel] = f.read()
    if all(MARK in t for t in texts.values()):
        return "in place"
    for rel, old, new in EDITS:
        text = texts[rel]
        if MARK in text and new in text:
            continue
        crlf = "\r\n" in text
        o, n = (old.replace("\n", "\r\n"), new.replace("\n", "\r\n")) if crlf else (old, new)
        if text.count(o) != 1:
            raise SystemExit("GMC {}: unexpected {} (not GMC {}?); remove game/addons/mpf-gmc and re-run setup.py"
                             .format(gmc_dir, rel, tc.GMC_VERSION))
        texts[rel] = text.replace(o, n)
    for rel, text in texts.items():
        with open(os.path.join(gmc_dir, *rel.split("/")), "w", encoding="utf-8", newline="") as f:
            f.write(text)
    if not quiet:
        print("   GMC BCP reader patched (scripts/gmc_patch.py)", flush=True)
    return "patched"


if __name__ == "__main__":
    print(patch(quiet=True))
