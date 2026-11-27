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


def test_deff139_and_95_draw_lists():
    from tron import rom_deff95, rom_deff139
    p = rom_engine.payload(139, {"value": 250000})
    assert len(p["seq"]) == rom_deff139.FLIPS + 1 and p["items"][p["frames"][0][-1]]["t"] == "250,000"
    q = rom_engine.payload(95, {"timer": 25, "value": 10000})
    assert q["loop"] and len(q["seq"]) == rom_deff95.PICTURES
    assert any(it.get("t") == "ALL TARGETS=10,000" for it in q["items"]) and any(it.get("r") == [0x29, 0x1a, 0x7f, 0x1f] for it in q["items"])


@pytest.mark.skipif(not ROM, reason="needs the ROM (TRON_ROM) and unicorn")
@pytest.mark.parametrize("value", [250000, 2350000])
def test_deff139_matches_rom_code(value):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "conform"))
    import engine_check as C
    from tron import rom_deff139
    ok, total, _ = C.compare(139, [value], lambda a: rom_deff139.frames(value))
    assert ok == total


@pytest.mark.skipif(not ROM, reason="needs the ROM (TRON_ROM) and unicorn")
def test_deff95_matches_rom_code():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "conform"))
    import engine_check as C
    from tron import rom_deff95
    ok, total, _ = C.compare(95, None, lambda a: rom_deff95.frames(7, 150000, 5, flips=60), ram={0x3b8f0: 7, 0x3b8ec: 150000, 0x3b92c: 5})
    assert ok == total


def test_deff2_volume_draw_list():
    from tron import rom_deff2
    p = rom_engine.payload(2, {"volume": 40})
    assert len(p["seq"]) == rom_deff2.FLIPS + 1 and not p["loop"]
    items = p["items"]
    assert {"i": 0xce, "x": 0, "y": 0x13} in items and {"i": 0xcf, "x": 40 * 2 - 0x7e, "y": 0x10} in items
    assert any(it.get("t") == "VOLUME 40" for it in items)
    assert any(it.get("t") == "VOLUME 41" for it in rom_engine.payload(2, {"volume": 41})["items"])


@pytest.mark.skipif(unicorn is None, reason="needs the ROM (TRON_ROM) and unicorn")
@pytest.mark.parametrize("volume", [0, 40, 63])
def test_deff2_equals_the_rom_code(volume):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "conform"))
    import engine_check as C
    from tron import rom_deff2
    C.X0 = 0
    ora = C.oracle(2, None, {0x2110250: volume, 0x2110251: (~volume) & 0xff})
    mine = rom_deff2.frames(volume)
    # flip 0 shows the page the allocator left (all 0xff), not a picture; every other flip is the ROM's
    assert [k for k, (t, f) in enumerate(ora) if k and C.body(f) != C.body(mine[min(k, len(mine) - 1)][1])] == []


def test_deff94_draw_list_has_the_squeeze():
    from tron import rom_deff94
    p = rom_engine.payload(94, {"value": 10000})
    assert not p["loop"] and p["ticks"] == 1
    assert len(p["seq"]) == rom_deff94.FLIPS * rom_deff94.TICKS + 10 * rom_deff94.SQUEEZE_TICKS + rom_deff94.HOLD_FLIPS * rom_deff94.HOLD_TICKS + 1
    assert sum(1 for it in p["items"] if "p" in it) >= 5                    # the copied rows of the new-page stages
    assert any(it.get("t") == "10,000 POINTS" for it in p["items"])


@pytest.mark.skipif(unicorn is None, reason="needs the ROM (TRON_ROM) and unicorn")
def test_deff94_equals_the_rom_code():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "conform"))
    import engine_check as C
    from tron import rom_deff94
    ok, total, first = C.compare(94, [10000], lambda a: rom_deff94.frames(10000))
    assert (ok, first) == (total, None)
