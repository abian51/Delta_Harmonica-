from __future__ import annotations

import random

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


def add_timing_variation(actions: list[Action], max_ms: int, *, min_gap_ms: int = 1,
                         segment_end_ms: int | None = None,
                         rng: random.Random | None = None) -> list[Action]:
    """Shift whole notes by a small amount without changing their hold duration.

    Each note's modifiers, key-down and key-up move together. The first note
    stays anchored, and later notes only move into existing free space.
    """
    if not 0 <= max_ms <= 15:
        raise ValueError("时间微调上限必须在 0–15 毫秒之间")
    if min_gap_ms < 0:
        raise ValueError("安全间隔不能为负")
    if max_ms == 0 or len(actions) < 2:
        return list(actions)

    spans: list[tuple[int, int, int, int]] = []
    index = 0
    while index < len(actions):
        start_index = index
        while index < len(actions) and actions[index].kind == "mouse" and actions[index].down:
            index += 1
        if index >= len(actions) or actions[index].kind != "keyboard" or not actions[index].down:
            raise ValueError("时间轴中的音符按下动作不完整")
        down = actions[index]
        index += 1
        if (index >= len(actions) or actions[index].kind != "keyboard"
                or actions[index].down or actions[index].code != down.code):
            raise ValueError("时间轴中的音符松开动作不完整")
        up = actions[index]
        index += 1
        while (index < len(actions) and actions[index].kind == "mouse"
               and not actions[index].down and actions[index].time_ms == up.time_ms):
            index += 1
        spans.append((start_index, index, down.time_ms, up.time_ms))

    randomizer = rng if rng is not None else random.SystemRandom()
    result = list(actions)
    for note_index, (first, last, start, end) in enumerate(spans):
        if note_index == 0:
            continue
        available = max_ms
        if note_index + 1 < len(spans):
            next_start = spans[note_index + 1][2]
            available = min(available, max(0, next_start - end - min_gap_ms))
        if segment_end_ms is not None:
            available = min(available, max(0, segment_end_ms - end))
        shift = randomizer.randint(0, available)
        for action_index in range(first, last):
            action = actions[action_index]
            result[action_index] = Action(action.time_ms + shift, action.kind, action.code,
                                          action.down, action.label)
    return sorted(result, key=lambda action: action.time_ms)
