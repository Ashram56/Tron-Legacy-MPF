"""scripts/vpx_extract.py reads VPX item records (drag points, string guards) and scripts/vpx_map.py finds the
switch, lamp and flasher numbers in a table script. The real run on the VPW Tron table is in
docs/agents/vpx_extraction.md ("Checking a run")."""
import csv
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import vpx_extract  # noqa: E402
import vpx_map  # noqa: E402


def rec(tag, payload=b""):
    return struct.pack("<i", 4 + len(payload)) + tag.encode() + payload


def floats(*v):
    return struct.pack("<{}f".format(len(v)), *v)


def wname(s):
    b = s.encode("utf-16-le")
    return struct.pack("<i", len(b)) + b


def test_item_position_ignores_drag_points():
    data = (struct.pack("<i", 7) + rec("VCEN", floats(10, 20)) + rec("NAME", wname("l45"))
            + rec("DPNT") + rec("VCEN", floats(99, 99)) + rec("ENDB") + rec("TMIN", struct.pack("<i", 45))
            + rec("ENDB"))
    item = vpx_extract.read_item(data)
    assert (item["type"], item["name"], item["x"], item["y"]) == ("Light", "l45", 10, 20)
    assert item["timer_interval"] == 45 and item["drag_points"] == 1


def test_wall_without_centre_uses_its_drag_points():
    data = (struct.pack("<i", 0) + rec("NAME", wname("sw01")) + rec("DPNT") + rec("VCEN", floats(0, 0))
            + rec("ENDB") + rec("DPNT") + rec("VCEN", floats(4, 2)) + rec("ENDB") + rec("ENDB"))
    item = vpx_extract.read_item(data)
    assert (item["x"], item["y"]) == (2, 1)


def test_ansi_strings_with_binary_or_bad_length_are_empty():
    assert vpx_extract.astr(struct.pack("<i", 3) + b"abc") == "abc"
    assert vpx_extract.astr(struct.pack("<i", 3) + b"a\x01c") == ""
    assert vpx_extract.astr(struct.pack("<i", 300) + b"abc") == ""


def test_code_record_carries_the_script():
    data = rec("LEFT", floats(0)) + struct.pack("<i", 4) + b"CODE" + struct.pack("<i", 5) + b"Hello" + rec("ENDB")
    tags = [(t, p) for t, p, _ in vpx_extract.records(data)]
    assert tags[1] == ("CODE", b"Hello") and tags[2][0] == "ENDB"


SCRIPT = r"""
Sub sw12_Hit:Controller.Switch(12) = 1:End Sub
Sub sw13_Hit
    vpmTimer.PulseSw 13 ' a comment with Controller.Switch(99) = 1
End Sub
'Sub sw14_Hit:Controller.Switch(14) = 1:End Sub
Sub Init
    Set bsTrough = New cvpmBallStack
    bsTrough.InitSw 0, 21, 20, 19, 18, 0, 0, 0
    bsTrough.InitKick BallRelease, 90, 8
    Set bsRHole = New cvpmBallStack
    With bsRHole
        .InitSw 0, 11, 0, 0, 0, 0, 0, 0
        .InitKick sw11, 200, 24
    End With
    DTBank4.InitDrop Array(sw04,sw03), Array(4,3)
End Sub
Lampz.MassAssign(45) = l45a
Lampz.MassAssign(45) = l45
ModLampz.MassAssign(17) = f17
"""


def test_map_reads_the_script_patterns(tmp_path):
    names = ["sw12", "sw13", "sw14", "BallRelease", "sw11", "sw04", "sw03", "l45a", "l45", "f17", "motorbank"]
    items = [{"type": "Light" if n.startswith("l") else "Flasher" if n.startswith("f") else "Trigger",
              "name": n, "x": 1.0, "y": 2.0, "nx": 0.5, "ny": 0.5} for n in names]
    (tmp_path / "items.json").write_text(json.dumps({"items": items}))
    (tmp_path / "script.vbs").write_bytes(SCRIPT.encode("cp1252"))
    cfg = tmp_path / "switches.yaml"
    cfg.write_text("#config_version=6\nswitches:\n  s_vuk:\n    number: 11   # VUK\n")
    vpx_map.main([str(tmp_path), "--names", str(cfg), "--mech", "52:motorbank"])
    sw = {int(r["number"]): r for r in csv.DictReader(open(tmp_path / "switches.csv"))}
    assert sorted(sw) == [3, 4, 11, 12, 13, 18, 19, 20, 21, 52]
    assert sw[11]["mpf_name"] == "s_vuk" and sw[12]["mpf_name"] == "s_12_sw12"
    assert sw[21]["vpx"] == "BallRelease" and float(sw[21]["ny"]) > float(sw[18]["ny"])
    li = {(r["kind"], int(r["number"])): r for r in csv.DictReader(open(tmp_path / "lights.csv"))}
    assert li[("lamp", 45)]["vpx"] == "l45" and li[("lamp", 45)]["note"] == "also: l45a"
    assert li[("flasher", 17)]["vpx"] == "f17"
    monitor = (tmp_path / "monitor.yaml").read_text()
    assert "\nswitch:\n" in monitor and "\nlight:\n" in monitor and "\ncoil:\n" in monitor


def test_collection_stream_lists_its_members():
    data = rec("NAME", wname("AllLamps")) + rec("ITEM", wname("li1")) + rec("ITEM", wname("li2")) + rec("ENDB")
    assert vpx_extract.read_collection(data) == ("AllLamps", ["li1", "li2"])


SCRIPT_VPW = r"""
Sub Init
    Set bsTrough = New cvpmTrough
    With bsTrough
        .InitSwitches Array(21, 20, 19, 18)
        .InitExit BallRelease, 70, 15
    End With
    Set bsSaucer = New cvpmBallStack
    bsSaucer.InitSaucer sw3, 3, 170, 10
    vpmMapLights AllLamps
End Sub
Sub sw2_Hit() : STHit 2 : End Sub
Set ST37 = (new StandupTarget)(sw37, sw37p, 37, 0)
SolModCallback(17) = "vpmFlasher f17,"
SolModCallback(26) = "SolModFlasherPWM126"
Sub SolModFlasherPWM126(level)
    ModFlashFlasher 1,level
End Sub
"""


def test_map_reads_vpw_trough_targets_and_flupper_domes(tmp_path):
    items = [{"type": t, "name": n, "x": 1.0, "y": 2.0, "nx": 0.5, "ny": 0.5, "timer_interval": ti}
             for n, t, ti in (("BallRelease", "Kicker", 0), ("sw3", "Kicker", 0), ("sw2", "HitTarget", 0),
                              ("sw37", "HitTarget", 0), ("f17", "Light", 100), ("Flasherlight1", "Light", 100),
                              ("li5", "Light", 5), ("gi1", "Light", 100))]
    (tmp_path / "items.json").write_text(json.dumps({"items": items, "collections": {"AllLamps": ["li5"]}}))
    (tmp_path / "script.vbs").write_bytes(SCRIPT_VPW.encode("cp1252"))
    vpx_map.main([str(tmp_path)])
    sw = {int(r["number"]): r for r in csv.DictReader(open(tmp_path / "switches.csv"))}
    assert sorted(sw) == [2, 3, 18, 19, 20, 21, 37]
    assert sw[18]["vpx"] == "BallRelease" and sw[3]["vpx"] == "sw3" and sw[37]["vpx"] == "sw37"
    li = {(r["kind"], int(r["number"])): r["vpx"] for r in csv.DictReader(open(tmp_path / "lights.csv"))}
    assert li == {("lamp", 5): "li5", ("flasher", 17): "f17", ("flasher", 26): "Flasherlight1"}
