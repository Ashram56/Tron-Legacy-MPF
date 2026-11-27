"""The game-side DMD engine (tron/dmd_engine.py and the rom_deff*.py programs): draw lists and, with the ROM and Unicorn, the ROM's own frames."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "game"))
from tron import dmd_engine as E, rom_deff55, rom_deff57, rom_deff60, rom_engine  # noqa: E402


def test_blit_palette_and_key():
    p = E.Page()
    pal = E.pal_new()
    E.pal_set(pal, 1, 2, 15)
    p.blit(0x9db, 0, 0, pal, 0xff)                 # a letter, dim: lit dots at level 1, the transparent ones not written
    assert set(p.b) <= {0, 1}
    assert p.items == [{"i": 0x9db, "x": 0, "y": 0, "m": pal}]


def test_deff55_draw_list():
    flips = rom_deff55.draws([3, 1, 4, 2, 4, 1, 2])
    assert len(flips) == rom_deff55.FLIPS + 2       # 41 flips and the end
    items = flips[1][1]
    assert [i["i"] for i in items[:4]] == [0x9db, 0x9d8, 0x9dd, 0x9eb]
    assert items[-2:] == [{"t": "1 MORE TO", "f": 33, "x": 84, "y": 26, "a": 2}, {"t": "LIGHT EX. BALL", "f": 33, "x": 84, "y": 32, "a": 2}]


def test_payload_packs_distinct_frames():
    pay = rom_engine.payload(57, {"value": 12000})
    assert pay["loop"] and len(pay["seq"]) == 116 and len(pay["frames"]) == 58
    assert "12,000" in pay["items"][pay["frames"][0][1]]["t"]
    p60 = rom_engine.payload(60, {"value": 200000, "more": 0})
    assert p60["items"][p60["frames"][0][-1]]["t"] == "BALL ADDED"
    p83 = rom_engine.payload(83, {"more": 3, "mask": 2})
    assert len(p83["seq"]) == 0x3b2 and len(str(p83)) < 400000


ROM = os.environ.get("TRON_ROM")
unicorn = pytest.importorskip("unicorn") if ROM and os.path.exists(ROM) else None


@pytest.mark.skipif(unicorn is None, reason="needs the ROM (TRON_ROM) and unicorn")
@pytest.mark.parametrize("effect,args", [(55, [3, 1, 4, 2, 4, 1, 2]), (55, [0, 0, 4, 4, 12, 0, 3]), (60, [200000, 1]), (60, [12, 0]), (57, [1234])])
def test_engine_equals_the_rom_code(effect, args):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "conform"))
    import engine_check as C
    if effect == 57:
        ok, total, first = C.compare(57, None, lambda a: rom_deff57.frames(args[0], flips=60), ram={0x3ae00: args[0]})
    else:
        prog = {55: rom_deff55.frames, 60: rom_deff60.frames}[effect]
        ok, total, first = C.compare(effect, args, prog)
    assert (ok, first) == (total, None)


@pytest.mark.skipif(not os.environ.get("TRON_ROM"), reason="needs the ROM (TRON_ROM) and unicorn")
@pytest.mark.parametrize("score,ball,valid,replay", [(4780, 1, 0, ""), (927580, 2, 1, ""), (0, 1, 1, ""), (55130, 3, 0, "REPLAY AT 20,000,000")])
def test_deff19_matches_rom_code(score, ball, valid, replay):
    import subprocess
    r = subprocess.run(["python3", os.path.join(os.path.dirname(__file__), "..", "scripts", "conform", "check19.py"), str(score), str(ball), str(valid), "5000000"],
                       capture_output=True, text=True, env=dict(os.environ, REPLAY=replay))
    if "unicorn" in r.stderr.lower() and "Error" in r.stderr:
        pytest.skip("unicorn not available")
    parts = r.stdout.split("->")[1].split()
    assert parts[0] == parts[2], r.stdout
