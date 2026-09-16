import json
from pathlib import Path

import pytest

from dhs.harmonica_mapping import MappingProfile
from dhs.melody import select_monophonic, transform
from dhs.models import Note
from dhs.timeline import build_actions, clip_actions


PROFILE = MappingProfile.load(Path(__file__).parents[1] / "profiles/harmonica.example.json")


def test_polyphony_requires_policy():
    notes = [Note(60, 0, 100), Note(64, 0, 100)]
    with pytest.raises(ValueError, match="Polyphonic"):
        select_monophonic(notes)
    assert select_monophonic(notes, "highest")[0].pitch == 64


def test_modifier_wraps_key_and_all_released():
    actions = build_actions([Note(61, 0, 100)], PROFILE)
    assert [(a.kind, a.down) for a in actions] == [
        ("mouse", True), ("keyboard", True), ("keyboard", False), ("mouse", False)
    ]
    assert sum(1 if a.down else -1 for a in actions) == 0


def test_speed_and_minimum_hold():
    note = transform([Note(60, 100, 110)], speed=2, min_hold_ms=35)[0]
    assert note.start_ms == 50 and note.end_ms == 85


def test_out_of_range_is_explicit():
    with pytest.raises(ValueError, match="outside"):
        build_actions([Note(20, 0, 100)], PROFILE)


def test_clip_inside_held_note_releases_key_and_modifier():
    original = build_actions([Note(61, 0, 1000)], PROFILE)
    clipped = clip_actions(original, 250, 750)
    assert [(item.time_ms, item.kind, item.down) for item in clipped] == [
        (0, "mouse", True), (0, "keyboard", True),
        (500, "keyboard", False), (500, "mouse", False),
    ]
    assert sum(1 if item.down else -1 for item in clipped) == 0


def test_clip_rebases_later_note():
    original = build_actions([Note(60, 0, 100), Note(62, 200, 300)], PROFILE)
    clipped = clip_actions(original, 150, 250)
    assert [(item.time_ms, item.label, item.down) for item in clipped] == [
        (50, "X", True), (100, "X", False),
    ]
