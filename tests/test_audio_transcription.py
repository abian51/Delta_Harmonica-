import math
import struct
import wave

import pytest
from mido import MidiFile

from dhs.audio_transcription import pitches_to_notes, transcribe_audio, write_midi
from dhs.midi_import import read_notes


def test_pitches_to_notes_filters_short_runs():
    notes = pitches_to_notes([60, 60, 60, None, 61, None, 62, 62, 62], frame_ms=40, min_note_ms=80)
    assert [(note.pitch, note.start_ms, note.end_ms) for note in notes] == [
        (60, 0, 120), (62, 240, 360)
    ]


def test_write_midi(tmp_path):
    notes = pitches_to_notes([60, 60, 60, None, 64, 64, 64], frame_ms=100, min_note_ms=80)
    output = write_midi(notes, tmp_path / "audio.mid")
    midi = MidiFile(output)
    messages = [message for message in midi.tracks[0] if message.type in {"note_on", "note_off"}]
    assert [message.note for message in messages] == [60, 60, 64, 64]


def test_transcribe_sine_wave_end_to_end(tmp_path):
    pytest.importorskip("librosa")
    soundfile = pytest.importorskip("soundfile")
    sample_rate = 22050
    source = tmp_path / "solo.wav"
    with wave.open(str(source), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        samples = [round(12000 * math.sin(2 * math.pi * 261.6256 * n / sample_rate))
                   for n in range(sample_rate)]
        handle.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    output = tmp_path / "solo.mid"
    report = transcribe_audio(source, output)
    assert report["notes"] >= 1
    assert any(note.pitch == 60 for note in read_notes(output))
    if "MP3" in soundfile.available_formats():
        mp3 = tmp_path / "solo.mp3"
        soundfile.write(mp3, [sample / 32768 for sample in samples], sample_rate, format="MP3")
        mp3_output = tmp_path / "solo_from_mp3.mid"
        mp3_report = transcribe_audio(mp3, mp3_output)
        assert mp3_report["notes"] >= 1
        assert any(note.pitch == 60 for note in read_notes(mp3_output))
