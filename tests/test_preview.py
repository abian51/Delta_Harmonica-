import wave

import json

from dhs.converter import convert_midi, prepare_midi
from dhs.preview_audio import clip_tones, scale_preview, synthesize_preview, tones_from_timeline
from dhs.sample_midi import create_three_note_sample
from dhs.timeline import clip_actions


def test_preview_uses_same_timeline_as_export(tmp_path):
    midi = create_three_note_sample(tmp_path / "sample.mid")
    _, notes, actions = prepare_midi(midi, speed=1.5, safe_gap_ms=12)
    tones = tones_from_timeline(notes, actions)
    key_down_times = [action.time_ms for action in actions if action.kind == "keyboard" and action.down]
    assert len(tones) == 3
    assert [tone.start_ms for tone in tones] == key_down_times
    assert [tone.pitch for tone in tones] == [60, 62, 64]


def test_preview_speed_scales_audio_and_visuals_together(tmp_path):
    midi = create_three_note_sample(tmp_path / "sample.mid")
    _, notes, actions = prepare_midi(midi)
    tones = tones_from_timeline(notes, actions)
    faster_actions, faster_tones = scale_preview(actions, tones, 2.0)
    assert faster_actions[-1].time_ms == round(actions[-1].time_ms / 2)
    assert faster_tones[-1].end_ms == round(tones[-1].end_ms / 2)


def test_synthesized_preview_has_sound(tmp_path):
    midi = create_three_note_sample(tmp_path / "sample.mid")
    _, notes, actions = prepare_midi(midi)
    output = synthesize_preview(tones_from_timeline(notes, actions), tmp_path / "preview.wav")
    with wave.open(str(output), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getframerate() == 22050
        samples = handle.readframes(handle.getnframes())
    assert any(samples)


def test_preview_selection_matches_exported_macro_timeline(tmp_path):
    midi = create_three_note_sample(tmp_path / "sample.mid")
    _, notes, full_actions = prepare_midi(midi, speed=2.0)
    preview_actions = clip_actions(full_actions, 200, 400)
    preview_tones = clip_tones(tones_from_timeline(notes, full_actions), 200, 400)
    report = convert_midi(midi, tmp_path / "output", speed=2.0,
                          clip_start_source_ms=400, clip_end_source_ms=800)
    exported = json.loads((tmp_path / "output" / "timeline.json").read_text(encoding="utf-8"))
    assert exported == [action.to_dict() for action in preview_actions]
    assert report["notes"] == len(preview_tones) == 2
    assert preview_tones[0].start_ms == 0
    assert preview_tones[-1].end_ms == 200
