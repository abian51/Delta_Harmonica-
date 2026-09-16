from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import mido

from .models import Note


class MidiImportError(ValueError):
    pass


def inspect_midi(path: str | Path) -> list[dict]:
    midi = _load(path)
    return [
        {
            "index": index,
            "name": track.name or f"Track {index}",
            "notes": sum(1 for msg in track if msg.type == "note_on" and msg.velocity > 0),
        }
        for index, track in enumerate(midi.tracks)
    ]


def read_notes(path: str | Path, tracks: set[int] | None = None) -> list[Note]:
    midi = _load(path)
    if midi.type == 2:
        raise MidiImportError("MIDI type 2 contains independent timelines and is not supported")
    tempo_events = _tempo_map(midi)
    output: list[Note] = []
    for track_index, track in enumerate(midi.tracks):
        if tracks is not None and track_index not in tracks:
            continue
        tick = 0
        active: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
        for msg in track:
            tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                active[(msg.channel, msg.note)].append((tick, msg.velocity))
            elif msg.type in {"note_off", "note_on"}:
                stack = active[(msg.channel, msg.note)]
                if stack:
                    start_tick, velocity = stack.pop(0)
                    output.append(Note(msg.note, _tick_to_ms(start_tick, tempo_events, midi.ticks_per_beat),
                                       _tick_to_ms(tick, tempo_events, midi.ticks_per_beat), track_index, velocity))
        if any(active.values()):
            raise MidiImportError(f"Track {track_index} contains notes without note_off")
    return sorted(output, key=lambda n: (n.start_ms, n.pitch, n.track, n.end_ms))


def _load(path: str | Path) -> mido.MidiFile:
    path = Path(path)
    if path.suffix.lower() not in {".mid", ".midi"}:
        raise MidiImportError("Only .mid and .midi files are accepted")
    try:
        return mido.MidiFile(path)
    except (OSError, EOFError, ValueError) as exc:
        raise MidiImportError(f"Invalid MIDI: {exc}") from exc


def _tempo_map(midi: mido.MidiFile) -> list[tuple[int, int]]:
    events: list[tuple[int, int, int]] = []
    for track_index, track in enumerate(midi.tracks):
        tick = 0
        for msg in track:
            tick += msg.time
            if msg.type == "set_tempo":
                events.append((tick, track_index, msg.tempo))
    result = [(0, 500_000)]
    for tick, _, tempo in sorted(events, key=lambda x: (x[0], x[1])):
        if result[-1][0] == tick:
            result[-1] = (tick, tempo)
        else:
            result.append((tick, tempo))
    return result


def _tick_to_ms(target: int, tempos: list[tuple[int, int]], ticks_per_beat: int) -> float:
    elapsed_us = 0.0
    last_tick, tempo = tempos[0]
    for tick, new_tempo in tempos[1:]:
        if tick >= target:
            break
        elapsed_us += (tick - last_tick) * tempo / ticks_per_beat
        last_tick, tempo = tick, new_tempo
    elapsed_us += (target - last_tick) * tempo / ticks_per_beat
    return elapsed_us / 1000.0

