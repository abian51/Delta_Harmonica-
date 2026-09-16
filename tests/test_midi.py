from pathlib import Path

import mido
import pytest

from dhs.midi_import import MidiImportError, read_notes


def save(tmp_path: Path, messages, midi_type=0):
    path = tmp_path / "song.mid"
    midi = mido.MidiFile(type=midi_type, ticks_per_beat=480)
    track = mido.MidiTrack(); midi.tracks.append(track); track.extend(messages); midi.save(path)
    return path


def test_three_notes_and_rest(tmp_path):
    path = save(tmp_path, [
        mido.Message("note_on", note=60, velocity=80, time=0),
        mido.Message("note_off", note=60, velocity=0, time=480),
        mido.Message("note_on", note=62, velocity=80, time=480),
        mido.Message("note_on", note=62, velocity=0, time=480),
    ])
    notes = read_notes(path)
    assert [(n.start_ms, n.end_ms) for n in notes] == [(0, 500), (1000, 1500)]


def test_tempo_change(tmp_path):
    path = save(tmp_path, [mido.MetaMessage("set_tempo", tempo=1_000_000, time=0),
                           mido.Message("note_on", note=60, velocity=1, time=0),
                           mido.Message("note_off", note=60, time=480)])
    assert read_notes(path)[0].end_ms == 1000


def test_hanging_note_rejected(tmp_path):
    path = save(tmp_path, [mido.Message("note_on", note=60, velocity=1, time=0)])
    with pytest.raises(MidiImportError, match="without note_off"):
        read_notes(path)


def test_type_two_rejected(tmp_path):
    path = save(tmp_path, [], midi_type=2)
    with pytest.raises(MidiImportError, match="type 2"):
        read_notes(path)

