import json
from pathlib import Path

import pytest

from dhs.harmonica_mapping import MappingProfile
from dhs.melody import select_monophonic, transform
from dhs.models import Note
from dhs.timeline import add_timing_variation, build_actions, clip_actions


PROFILE = MappingProfile.load(Path(__file__).parents[1] / "profiles/harmonica.example.json")


def test_polyphony_requires_policy():
    notes = [Note(60, 0, 100), Note(64, 0, 100)]
    with pytest.raises(ValueError, match="Polyphonic"):
        select_monophonic(notes)
    assert select_monophonic(notes, "highest")[0].pitch == 64


def test_polyphony_does_not_merge_entire_overlap_chain():
    notes = [Note(60, 0, 100), Note(64, 50, 150), Note(67, 120, 200)]
    assert [(note.pitch, note.start_ms, note.end_ms) for note in select_monophonic(notes, "highest")] == [
        (60, 0, 50), (64, 50, 120), (67, 120, 200),
    ]
    assert [(note.pitch, note.start_ms, note.end_ms) for note in select_monophonic(notes, "lowest")] == [
        (60, 0, 100), (64, 100, 150), (67, 150, 200),
    ]


def test_polyphony_returns_to_held_note_after_higher_note_ends():
    notes = [Note(60, 0, 200), Note(72, 50, 100)]
    assert [(note.pitch, note.start_ms, note.end_ms) for note in select_monophonic(notes, "highest")] == [
        (60, 0, 50), (72, 50, 100), (60, 100, 200),
    ]


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


def test_delta_harmonica_octave_and_semitone_mouse_mapping():
    assert PROFILE.pitch_range == (48, 85)
    assert PROFILE.resolve(48)[1] == [("left", 1)]
    assert PROFILE.resolve(61)[1] == [("middle", 3)]
    assert PROFILE.resolve(75)[1] == [("right", 2), ("middle", 3)]
    assert PROFILE.fold_pitch(93) == 81
    assert PROFILE.fold_pitch(33) == 57


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


class _FixedRandom:
    def __init__(self, values):
        self.values = iter(values)

    def randint(self, low, high):
        return min(high, max(low, next(self.values)))


def test_timing_variation_moves_whole_notes_without_changing_hold():
    original = build_actions([Note(60, 0, 100), Note(61, 200, 300), Note(62, 500, 600)], PROFILE)
    varied = add_timing_variation(original, 15, min_gap_ms=5, rng=_FixedRandom([7, 13]))
    assert [(a.time_ms, a.kind, a.down) for a in varied] == [
        (0, "keyboard", True), (100, "keyboard", False),
        (207, "mouse", True), (207, "keyboard", True),
        (307, "keyboard", False), (307, "mouse", False),
        (513, "keyboard", True), (613, "keyboard", False),
    ]
    assert all(next_action.time_ms >= action.time_ms for action, next_action in zip(varied, varied[1:]))


def test_timing_variation_respects_short_gap_and_clip_end():
    original = build_actions([Note(60, 0, 100), Note(62, 105, 205)], PROFILE)
    varied = add_timing_variation(original, 15, min_gap_ms=5, segment_end_ms=205,
                                   rng=_FixedRandom([15]))
    assert varied == original


def test_timing_variation_rejects_out_of_range():
    with pytest.raises(ValueError, match="0–15"):
        add_timing_variation([], 16)
