from __future__ import annotations

import csv
import json
from pathlib import Path

from .gg_engine_api import actions_to_api_events
from .gg_native_adapter import STATUS, actions_to_gg_events
from .harmonica_mapping import MappingProfile
from .melody import select_monophonic, transform
from .midi_import import read_notes
from .timeline import build_actions, clip_actions


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = PROJECT_ROOT / "profiles" / "harmonica.example.json"


def prepare_midi(
    midi_path: str | Path,
    *,
    profile_path: str | Path = DEFAULT_PROFILE,
    tracks: set[int] | None = None,
    polyphony: str = "reject",
    transpose: int = 0,
    speed: float = 1.0,
    min_hold_ms: int = 35,
    safe_gap_ms: int = 5,
) -> tuple[MappingProfile, list, list]:
    profile = MappingProfile.load(profile_path)
    source_notes = read_notes(midi_path, tracks)
    notes = transform(select_monophonic(source_notes, polyphony), transpose, speed, min_hold_ms)
    actions = build_actions(notes, profile, safe_gap_ms)
    return profile, notes, actions


def convert_midi(
    midi_path: str | Path,
    output_dir: str | Path,
    *,
    profile_path: str | Path = DEFAULT_PROFILE,
    tracks: set[int] | None = None,
    polyphony: str = "reject",
    transpose: int = 0,
    speed: float = 1.0,
    min_hold_ms: int = 35,
    safe_gap_ms: int = 5,
    clip_start_source_ms: float = 0,
    clip_end_source_ms: float | None = None,
) -> dict:
    _, notes, actions = prepare_midi(
        midi_path, profile_path=profile_path, tracks=tracks, polyphony=polyphony,
        transpose=transpose, speed=speed, min_hold_ms=min_hold_ms, safe_gap_ms=safe_gap_ms,
    )
    if clip_start_source_ms or clip_end_source_ms is not None:
        start_ms = round(clip_start_source_ms / speed)
        end_ms = (round(clip_end_source_ms / speed) if clip_end_source_ms is not None
                  else max((action.time_ms for action in actions), default=0) + 1)
        actions = clip_actions(actions, start_ms, end_ms)
        if not any(action.kind == "keyboard" and action.down for action in actions):
            raise ValueError("选中的片段没有可导出的音符，请调整截取范围")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "timeline.json").write_text(
        json.dumps([a.to_dict() for a in actions], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (out / "events.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time_ms", "kind", "code", "down", "label"])
        writer.writeheader()
        writer.writerows(a.to_dict() for a in actions)
    (out / "gg_events.unverified.json").write_text(
        json.dumps(actions_to_gg_events(actions), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "gg_events.api.json").write_text(
        json.dumps(actions_to_api_events(actions), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    warnings = ["gg_events.api.json 只能由本项目通过本机 GG Engine 接口提交，不是双击导入文件。"]
    report = {
        "status": "CONVERTER_READY",
        "gg_native_status": STATUS,
        "source": str(Path(midi_path).resolve()),
        "tracks": sorted(tracks) if tracks is not None else "all",
        "notes": (sum(action.kind == "keyboard" and action.down for action in actions)
                  if clip_start_source_ms or clip_end_source_ms is not None else len(notes)),
        "actions": len(actions),
        "duration_ms": actions[-1].time_ms if actions else 0,
        "clip_start_source_ms": clip_start_source_ms,
        "clip_end_source_ms": clip_end_source_ms,
        "output_dir": str(out.resolve()),
        "timeline_file": str((out / "timeline.json").resolve()),
        "gg_api_events_file": str((out / "gg_events.api.json").resolve()),
        "warnings": warnings,
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
