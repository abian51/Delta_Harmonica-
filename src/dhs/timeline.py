from __future__ import annotations

from .harmonica_mapping import MappingProfile
from .models import Action, Note


def build_actions(notes: list[Note], profile: MappingProfile, safe_gap_ms: int = 5) -> list[Action]:
    actions: list[Action] = []
    last_end = 0
    for note in sorted(notes, key=lambda n: (n.start_ms, n.pitch)):
        start = max(round(note.start_ms), last_end + safe_gap_ms if actions else round(note.start_ms))
        end = max(start + 1, round(note.end_ms))
        code, modifiers, label = profile.resolve(note.pitch)
        for mod_label, mod_code in modifiers:
            actions.append(Action(start, "mouse", mod_code, True, mod_label))
        actions.append(Action(start, "keyboard", code, True, label))
        actions.append(Action(end, "keyboard", code, False, label))
        for mod_label, mod_code in reversed(modifiers):
            actions.append(Action(end, "mouse", mod_code, False, mod_label))
        last_end = end
    # Python's stable sort preserves the deliberate modifier-down -> key-down and
    # key-up -> modifier-up ordering for events at the same millisecond.
    return sorted(actions, key=lambda a: a.time_ms)


def clip_actions(actions: list[Action], start_ms: int, end_ms: int) -> list[Action]:
    """Extract a timeline interval, preserving held keys at both boundaries."""
    if start_ms < 0 or end_ms <= start_ms:
        raise ValueError("截取终点必须晚于起点，且起点不能为负")
    active: dict[tuple[str, int], Action] = {}
    for action in actions:
        if action.time_ms >= start_ms:
            break
        key = (action.kind, action.code)
        if action.down:
            active[key] = action
        else:
            active.pop(key, None)

    result: list[Action] = []
    # Modifiers must be pressed before keyboard keys at the new boundary.
    for action in sorted(active.values(), key=lambda item: item.kind != "mouse"):
        result.append(Action(0, action.kind, action.code, True, action.label))

    for action in actions:
        if action.time_ms < start_ms:
            continue
        if action.time_ms >= end_ms:
            break
        shifted = Action(action.time_ms - start_ms, action.kind, action.code, action.down, action.label)
        result.append(shifted)
        key = (action.kind, action.code)
        if action.down:
            active[key] = action
        else:
            active.pop(key, None)

    duration = end_ms - start_ms
    # Release keyboard keys before the modifiers they depended on.
    for action in sorted(active.values(), key=lambda item: item.kind == "mouse"):
        result.append(Action(duration, action.kind, action.code, False, action.label))
    return result
