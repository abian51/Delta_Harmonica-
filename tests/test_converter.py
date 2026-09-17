import json

import mido
import pytest

from dhs.converter import convert_midi
from dhs.macro_export import EXPORT_FORMATS, actions_from_file, export_macro
from dhs.sample_midi import create_three_note_sample


def test_end_to_end_three_note_export(tmp_path):
    midi = create_three_note_sample(tmp_path / "sample.mid")
    output = tmp_path / "output"
    report = convert_midi(midi, output)
    assert report["status"] == "CONVERTER_READY"
    assert report["gg_native_status"] == "GG_CREATED"
    assert report["notes"] == 3
    assert {p.name for p in output.iterdir()} == {
        "timeline.json", "events.csv", "gg_events.unverified.json", "gg_events.api.json", "report.json"
    }
    api_events = json.loads((output / "gg_events.api.json").read_text(encoding="utf-8"))
    assert all("eventNum" not in event for event in api_events)
    actions = json.loads((output / "timeline.json").read_text(encoding="utf-8"))
    assert actions[0]["down"] is True and actions[-1]["down"] is False


def test_three_note_sample_exports_all_device_formats(tmp_path):
    midi = create_three_note_sample(tmp_path / "sample.mid")
    report = convert_midi(midi, tmp_path / "converted")
    actions = actions_from_file(report["timeline_file"])
    for format_id, details in EXPORT_FORMATS.items():
        output = tmp_path / f"sample{details['extension']}"
        result = export_macro(actions, "DHS_Sample", format_id, output)
        assert output.is_file() and output.stat().st_size > 0
        assert result["actions"] == len(actions)


def test_clipped_conversion_feeds_gg_and_vendor_exports(tmp_path):
    midi = create_three_note_sample(tmp_path / "sample.mid")
    report = convert_midi(midi, tmp_path / "slice", clip_start_source_ms=400,
                          clip_end_source_ms=800)
    actions = actions_from_file(report["timeline_file"])
    assert report["notes"] == 2
    assert actions[0].time_ms == 0
    assert actions[-1].time_ms == 400
    assert sum(action.down for action in actions) == sum(not action.down for action in actions)
    api_events = json.loads((tmp_path / "slice" / "gg_events.api.json").read_text(encoding="utf-8"))
    assert len([event for event in api_events if event["type"] != 4]) == len(actions)
    exported = tmp_path / "slice.lua"
    assert export_macro(actions, "Slice", "logitech_lua", exported)["actions"] == len(actions)


def test_timing_variation_setting_reaches_all_output_files(tmp_path):
    midi = create_three_note_sample(tmp_path / "sample.mid")
    report = convert_midi(midi, tmp_path / "varied", timing_variation_ms=15)
    actions = actions_from_file(report["timeline_file"])
    assert report["timing_variation_ms"] == 15
    assert report["actions"] == len(actions)
    assert all(actions[index].time_ms <= actions[index + 1].time_ms for index in range(len(actions) - 1))
    api_events = json.loads((tmp_path / "varied" / "gg_events.api.json").read_text(encoding="utf-8"))
    assert len([event for event in api_events if event["type"] != 4]) == len(actions)


def test_explicit_octave_folding_matches_exported_actions(tmp_path):
    midi = mido.MidiFile()
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.Message("note_on", note=93, velocity=80, time=0))
    track.append(mido.Message("note_off", note=93, velocity=0, time=480))
    source = tmp_path / "high.mid"
    midi.save(source)
    with pytest.raises(ValueError, match="outside"):
        convert_midi(source, tmp_path / "rejected")
    report = convert_midi(source, tmp_path / "folded", out_of_range="octave_fold")
    assert report["notes"] == 1
    assert report["out_of_range"] == "octave_fold"
    actions = actions_from_file(report["timeline_file"])
    assert actions[0].kind == "mouse" and actions[0].code == 2  # 81 = A5, right/up +12
