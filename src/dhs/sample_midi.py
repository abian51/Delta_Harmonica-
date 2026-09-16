from __future__ import annotations

from pathlib import Path

import mido


def create_three_note_sample(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    midi = mido.MidiFile(type=0, ticks_per_beat=480)
    track = mido.MidiTrack(); midi.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="Desktop acceptance C-D-E", time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=500_000, time=0))
    for pitch in (60, 62, 64):
        track.append(mido.Message("note_on", note=pitch, velocity=80, time=120 if pitch != 60 else 0))
        track.append(mido.Message("note_off", note=pitch, velocity=0, time=240))
    track.append(mido.MetaMessage("end_of_track", time=0))
    midi.save(target)
    return target

