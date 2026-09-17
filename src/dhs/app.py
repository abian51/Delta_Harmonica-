from __future__ import annotations

import argparse
import json
from pathlib import Path

from .converter import DEFAULT_PROFILE, convert_midi
from .audio_transcription import transcribe_audio
from .gg_engine_api import create_macro, list_macros
from .macro_export import EXPORT_FORMATS, actions_from_file, export_macro
from .midi_import import inspect_midi


def convert(args: argparse.Namespace) -> int:
    report = convert_midi(args.midi, args.output, profile_path=args.profile,
                          tracks=set(args.track) if args.track else None, polyphony=args.polyphony,
                          transpose=args.transpose, speed=args.speed, min_hold_ms=args.min_hold,
                          safe_gap_ms=args.safe_gap, out_of_range=args.out_of_range,
                          clip_start_source_ms=args.clip_start,
                          clip_end_source_ms=args.clip_end,
                          timing_variation_ms=args.timing_variation)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def gg_list(_args: argparse.Namespace) -> int:
    macros = list_macros()
    print(json.dumps([{"id": item.get("id"), "name": item.get("name")} for item in macros],
                     ensure_ascii=False, indent=2))
    return 0


def gg_create(args: argparse.Namespace) -> int:
    events = json.loads(Path(args.events).read_text(encoding="utf-8"))
    macro_id = create_macro(args.name, events)
    print(json.dumps({"macro_id": macro_id, "name": args.name}, ensure_ascii=False, indent=2))
    return 0


def transcribe(args: argparse.Namespace) -> int:
    report = transcribe_audio(args.audio, args.output, fmin_note=args.fmin, fmax_note=args.fmax,
                              min_note_ms=args.min_note, confidence=args.confidence)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def export_device(args: argparse.Namespace) -> int:
    report = export_macro(actions_from_file(args.timeline), args.name, args.format, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delta Harmonica Studio")
    sub = parser.add_subparsers(dest="command")
    scan = sub.add_parser("inspect", help="List MIDI tracks")
    scan.add_argument("midi")
    conv = sub.add_parser("convert", help="Create reviewable timeline files")
    conv.add_argument("midi"); conv.add_argument("--output", default="output")
    conv.add_argument("--profile", default=str(DEFAULT_PROFILE))
    conv.add_argument("--track", type=int, action="append")
    conv.add_argument("--polyphony", choices=["reject", "highest", "lowest"], default="reject")
    conv.add_argument("--out-of-range", choices=["reject", "octave_fold"], default="reject")
    conv.add_argument("--transpose", type=int, default=0); conv.add_argument("--speed", type=float, default=1.0)
    conv.add_argument("--min-hold", type=int, default=35); conv.add_argument("--safe-gap", type=int, default=5)
    conv.add_argument("--clip-start", type=int, default=0, help="Start of source MIDI segment in ms")
    conv.add_argument("--clip-end", type=int, help="End of source MIDI segment in ms")
    conv.add_argument("--timing-variation", type=int, default=0,
                      help="Optional random per-note timing variation, 0-15 ms (default: 0)")
    gg_scan = sub.add_parser("gg-list", help="List macros through the local GG Engine API")
    gg_create_parser = sub.add_parser("gg-create", help="Create a macro through the local GG Engine API")
    gg_create_parser.add_argument("events"); gg_create_parser.add_argument("--name", required=True)
    audio = sub.add_parser("transcribe", help="Transcribe monophonic audio to MIDI")
    audio.add_argument("audio"); audio.add_argument("--output", required=True)
    audio.add_argument("--fmin", type=int, default=48); audio.add_argument("--fmax", type=int, default=84)
    audio.add_argument("--min-note", type=int, default=80); audio.add_argument("--confidence", type=float, default=0.65)
    device = sub.add_parser("export-macro", help="Export a timeline for a device or macro tool")
    device.add_argument("timeline"); device.add_argument("--format", choices=EXPORT_FORMATS, required=True)
    device.add_argument("--output", required=True); device.add_argument("--name", default="DHS_Macro")
    args = parser.parse_args(argv)
    if args.command == "inspect":
        print(json.dumps(inspect_midi(args.midi), ensure_ascii=False, indent=2)); return 0
    if args.command == "convert": return convert(args)
    if args.command == "gg-list": return gg_list(args)
    if args.command == "gg-create": return gg_create(args)
    if args.command == "transcribe": return transcribe(args)
    if args.command == "export-macro": return export_device(args)
    if argv is None:
        from .gui import run_gui
        run_gui(); return 0
    parser.print_help(); return 0
