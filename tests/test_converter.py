import json

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
