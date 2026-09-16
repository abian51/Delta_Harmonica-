from __future__ import annotations

import json
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from .models import Action


EXPORT_FORMATS = {
    "generic_json": {"label": "通用 JSON", "extension": ".json"},
    "autohotkey_v2": {"label": "牧马人/其他外设（AutoHotkey v2）", "extension": ".ahk"},
    "logitech_lua": {"label": "罗技 G HUB（Lua）", "extension": ".lua"},
    "razer_synapse3_xml": {"label": "雷蛇 Synapse 3（XML）", "extension": ".xml"},
}

_HID_KEY_NAMES = {
    **{code: chr(ord("a") + code - 4) for code in range(4, 30)},
    **{code: str(code - 29) for code in range(30, 39)},
    39: "0", 40: "enter", 41: "escape", 42: "backspace", 43: "tab", 44: "space",
    45: "-", 46: "=", 47: "[", 48: "]", 49: "\\", 51: ";", 52: "'",
    53: "`", 54: ",", 55: ".", 56: "/", 57: "capslock",
    **{code: f"f{code - 57}" for code in range(58, 70)},
    73: "insert", 74: "home", 75: "pageup", 76: "delete", 77: "end", 78: "pagedown",
    79: "right", 80: "left", 81: "down", 82: "up",
    224: "lctrl", 225: "lshift", 226: "lalt", 227: "lgui",
    228: "rctrl", 229: "rshift", 230: "ralt", 231: "rgui",
}

# USB HID keyboard usages -> Windows scan code set 1, as expected by Synapse 3 XML.
_HID_TO_SCAN = {
    4: 30, 5: 48, 6: 46, 7: 32, 8: 18, 9: 33, 10: 34, 11: 35, 12: 23,
    13: 36, 14: 37, 15: 38, 16: 50, 17: 49, 18: 24, 19: 25, 20: 16,
    21: 19, 22: 31, 23: 20, 24: 22, 25: 47, 26: 17, 27: 45, 28: 21, 29: 44,
    30: 2, 31: 3, 32: 4, 33: 5, 34: 6, 35: 7, 36: 8, 37: 9, 38: 10, 39: 11,
    40: 28, 41: 1, 42: 14, 43: 15, 44: 57, 45: 12, 46: 13, 47: 26,
    48: 27, 49: 43, 51: 39, 52: 40, 53: 41, 54: 51, 55: 52, 56: 53,
    57: 58, 58: 59, 59: 60, 60: 61, 61: 62, 62: 63, 63: 64, 64: 65,
    65: 66, 66: 67, 67: 68, 68: 87, 69: 88,
    73: 82, 74: 71, 75: 73, 76: 83, 77: 79, 78: 81, 79: 77, 80: 75, 81: 80, 82: 72,
    224: 29, 225: 42, 226: 56, 227: 91, 228: 29, 229: 54, 230: 56, 231: 92,
}
_EXTENDED_HID = {73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 227, 228, 230, 231}
_MOUSE_NAMES = {1: "Left", 2: "Right", 3: "Middle"}
_LOGITECH_MOUSE_BUTTONS = {1: 1, 2: 3, 3: 2}


def actions_from_file(path: str | Path) -> list[Action]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("时间轴文件必须是动作数组")
    actions = []
    for item in raw:
        actions.append(Action(time_ms=int(item["time_ms"]), kind=str(item["kind"]),
                              code=int(item["code"]), down=bool(item["down"]),
                              label=str(item.get("label", ""))))
    return sorted(actions, key=lambda action: action.time_ms)


def export_macro(actions: list[Action], name: str, format_id: str, output_path: str | Path) -> dict:
    if format_id not in EXPORT_FORMATS:
        raise ValueError(f"不支持的导出格式：{format_id}")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if format_id == "generic_json":
        _write_json(actions, name, output)
    elif format_id == "autohotkey_v2":
        output.write_text(_autohotkey_v2(actions, name), encoding="utf-8-sig")
    elif format_id == "logitech_lua":
        output.write_text(_logitech_lua(actions, name), encoding="utf-8")
    else:
        _write_razer_synapse3(actions, name, output)
    return {"format": format_id, "label": EXPORT_FORMATS[format_id]["label"],
            "file": str(output.resolve()), "actions": len(actions)}


def _write_json(actions: list[Action], name: str, output: Path) -> None:
    payload = {"schema": "delta-harmonica-macro/v1", "name": name, "time_unit": "ms",
               "actions": [action.to_dict() for action in actions]}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _key_name(action: Action) -> str:
    try:
        return _HID_KEY_NAMES[action.code]
    except KeyError as exc:
        raise ValueError(f"键盘 HID 键码 {action.code} 暂不支持导出") from exc


def _ahk_key_name(action: Action) -> str:
    name = _key_name(action)
    if len(name) == 1 and not name.isalnum():
        return f"sc{_HID_TO_SCAN[action.code]:03X}"
    return name


def _autohotkey_v2(actions: list[Action], name: str) -> str:
    safe_name = name.replace("\r", " ").replace("\n", " ")
    lines = ["#Requires AutoHotkey v2.0", "#SingleInstance Force", "SendMode \"Event\"", "",
             f"; Delta Harmonica Studio: {safe_name}", "; 按 F8 播放；再次按 F8 不会中断正在播放的宏。",
             "F8::{"]
    last = 0
    for action in actions:
        delay = max(0, action.time_ms - last)
        if delay:
            lines.append(f"    Sleep {delay}")
        if action.kind == "keyboard":
            state = "down" if action.down else "up"
            lines.append(f'    SendEvent "{{{_ahk_key_name(action)} {state}}}"')
        elif action.kind == "mouse":
            button = _MOUSE_NAMES.get(action.code)
            if not button:
                raise ValueError(f"鼠标键码 {action.code} 暂不支持导出")
            state = "Down" if action.down else "Up"
            lines.append(f'    Click "{button} {state}"')
        else:
            raise ValueError(f"未知动作类型：{action.kind}")
        last = action.time_ms
    lines.extend(["}", ""])
    return "\n".join(lines)


def _logitech_lua(actions: list[Action], name: str) -> str:
    safe_name = name.replace("\r", " ").replace("\n", " ")
    lines = [f"-- Delta Harmonica Studio: {safe_name}",
             "-- 粘贴到 G HUB 的脚本编辑器；按鼠标 G6（编号 6）播放。",
             "local TRIGGER_BUTTON = 6", "", "function OnEvent(event, arg)",
             "  if event == \"PROFILE_ACTIVATED\" then EnablePrimaryMouseButtonEvents(true) end",
             "  if event ~= \"MOUSE_BUTTON_PRESSED\" or arg ~= TRIGGER_BUTTON then return end"]
    last = 0
    for action in actions:
        delay = max(0, action.time_ms - last)
        if delay:
            lines.append(f"  Sleep({delay})")
        if action.kind == "keyboard":
            func = "PressKey" if action.down else "ReleaseKey"
            lines.append(f"  {func}({json.dumps(_key_name(action))})")
        elif action.kind == "mouse":
            if action.code not in _MOUSE_NAMES:
                raise ValueError(f"鼠标键码 {action.code} 暂不支持导出")
            func = "PressMouseButton" if action.down else "ReleaseMouseButton"
            lines.append(f"  {func}({_LOGITECH_MOUSE_BUTTONS[action.code]})")
        else:
            raise ValueError(f"未知动作类型：{action.kind}")
        last = action.time_ms
    lines.extend(["end", ""])
    return "\n".join(lines)


def _write_razer_synapse3(actions: list[Action], name: str, output: Path) -> None:
    root = ET.Element("Macro", {"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                                "xmlns:xsd": "http://www.w3.org/2001/XMLSchema"})
    ET.SubElement(root, "Name").text = name
    ET.SubElement(root, "Guid").text = str(uuid.uuid4())
    events = ET.SubElement(root, "MacroEvents")
    last = 0
    for action in actions:
        event = ET.SubElement(events, "MacroEvent")
        delay = max(0, action.time_ms - last)
        ET.SubElement(event, "Type").text = "1" if action.kind == "keyboard" else "2"
        if delay:
            ET.SubElement(event, "Delay").text = str(delay)
        if action.kind == "keyboard":
            if action.code not in _HID_TO_SCAN:
                raise ValueError(f"键盘 HID 键码 {action.code} 暂不支持雷蛇导出")
            key = ET.SubElement(event, "KeyEvent")
            ET.SubElement(key, "Makecode").text = str(_HID_TO_SCAN[action.code])
            if not action.down:
                ET.SubElement(key, "State").text = "1"
            if action.code in _EXTENDED_HID:
                ET.SubElement(key, "IsExtended").text = "true"
        elif action.kind == "mouse":
            if action.code not in _MOUSE_NAMES:
                raise ValueError(f"鼠标键码 {action.code} 暂不支持雷蛇导出")
            mouse = ET.SubElement(event, "MouseEvent")
            ET.SubElement(mouse, "MouseButton").text = str(action.code)
            ET.SubElement(mouse, "State").text = "0" if action.down else "1"
        else:
            raise ValueError(f"未知动作类型：{action.kind}")
        last = action.time_ms
    ET.SubElement(root, "IsFolder").text = "false"
    ET.SubElement(root, "FolderGuid").text = "00000000-0000-0000-0000-000000000000"
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
