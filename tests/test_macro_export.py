import json
import xml.etree.ElementTree as ET

import pytest

from dhs.macro_export import export_macro
from dhs.models import Action


@pytest.fixture
def actions():
    return [
        Action(0, "mouse", 1, True, "left"),
        Action(0, "keyboard", 29, True, "Z"),
        Action(120, "keyboard", 29, False, "Z"),
        Action(120, "mouse", 1, False, "left"),
    ]


def test_generic_json(actions, tmp_path):
    output = tmp_path / "macro.json"
    report = export_macro(actions, "Demo", "generic_json", output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert report["actions"] == 4
    assert payload["schema"] == "delta-harmonica-macro/v1"
    assert payload["actions"][1]["code"] == 29


def test_autohotkey_v2(actions, tmp_path):
    output = tmp_path / "macro.ahk"
    export_macro(actions, "Demo", "autohotkey_v2", output)
    script = output.read_text(encoding="utf-8-sig")
    assert "#Requires AutoHotkey v2.0" in script
    assert 'SendEvent "{z down}"' in script
    assert 'Click "Left Up"' in script


def test_punctuation_key_export(tmp_path):
    actions = [Action(0, "keyboard", 54, True, ",")]
    ahk = tmp_path / "comma.ahk"
    lua = tmp_path / "comma.lua"
    export_macro(actions, "Demo", "autohotkey_v2", ahk)
    export_macro(actions, "Demo", "logitech_lua", lua)
    assert "{sc033 down}" in ahk.read_text(encoding="utf-8-sig")
    assert 'PressKey(",")' in lua.read_text(encoding="utf-8")


def test_logitech_lua(actions, tmp_path):
    output = tmp_path / "macro.lua"
    export_macro(actions, "Demo", "logitech_lua", output)
    script = output.read_text(encoding="utf-8")
    assert "function OnEvent(event, arg)" in script
    assert 'PressKey("z")' in script
    assert "Sleep(120)" in script


def test_logitech_mouse_button_order(tmp_path):
    actions = [Action(0, "mouse", 2, True, "right"), Action(10, "mouse", 3, True, "middle")]
    output = tmp_path / "mouse.lua"
    export_macro(actions, "Demo", "logitech_lua", output)
    script = output.read_text(encoding="utf-8")
    assert "PressMouseButton(3)" in script  # G HUB: 3 is right
    assert "PressMouseButton(2)" in script  # G HUB: 2 is middle


def test_razer_synapse3_xml(actions, tmp_path):
    output = tmp_path / "macro.xml"
    export_macro(actions, "Demo", "razer_synapse3_xml", output)
    root = ET.parse(output).getroot()
    assert root.findtext("Name") == "Demo"
    events = root.findall("./MacroEvents/MacroEvent")
    assert len(events) == 4
    assert events[1].findtext("./KeyEvent/Makecode") == "44"
    assert events[2].findtext("./KeyEvent/State") == "1"
