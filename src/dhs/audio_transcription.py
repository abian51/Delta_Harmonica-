from __future__ import annotations

import math
from pathlib import Path

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo, second2tick

from .models import Note


def pitches_to_notes(pitches: list[int | None], frame_ms: float, min_note_ms: int = 80) -> list[Note]:
    """Turn a monophonic frame sequence into notes; kept dependency-free for testing."""
    notes: list[Note] = []
    active_pitch: int | None = None
    start_frame = 0
    for index, pitch in enumerate([*pitches, None]):
        if pitch == active_pitch:
            continue
        if active_pitch is not None:
            start_ms = start_frame * frame_ms
            end_ms = index * frame_ms
            if end_ms - start_ms >= min_note_ms:
                notes.append(Note(active_pitch, start_ms, end_ms))
        active_pitch = pitch
        start_frame = index
    return notes


def _median_smooth(pitches: list[int | None], radius: int = 2) -> list[int | None]:
    result: list[int | None] = []
    for index, pitch in enumerate(pitches):
        if pitch is None:
            result.append(None)
            continue
        values = sorted(value for value in pitches[max(0, index - radius):index + radius + 1]
                        if value is not None)
        result.append(values[len(values) // 2] if values else None)
    return result


def write_midi(notes: list[Note], output_path: str | Path, bpm: int = 120) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    midi = MidiFile(ticks_per_beat=480)
    track = MidiTrack(); midi.tracks.append(track)
    tempo = bpm2tempo(bpm)
    track.append(MetaMessage("set_tempo", tempo=tempo, time=0))
    events = []
    for note in notes:
        events.append((note.start_ms, 1, note.pitch, note.velocity))
        events.append((note.end_ms, 0, note.pitch, 0))
    last_ms = 0.0
    for time_ms, is_on, pitch, velocity in sorted(events, key=lambda item: (item[0], item[1])):
        delta_ticks = round(second2tick((time_ms - last_ms) / 1000, midi.ticks_per_beat, tempo))
        track.append(Message("note_on" if is_on else "note_off", note=pitch,
                             velocity=velocity, time=max(0, delta_ticks)))
        last_ms = time_ms
    track.append(MetaMessage("end_of_track", time=0))
    midi.save(output)
    return output


def transcribe_audio(audio_path: str | Path, output_path: str | Path, *,
                     fmin_note: int = 48, fmax_note: int = 84,
                     min_note_ms: int = 80, confidence: float = 0.65) -> dict:
    if not 0 <= fmin_note < fmax_note <= 127:
        raise ValueError("音高范围必须满足 0 ≤ 最低音 < 最高音 ≤ 127")
    if min_note_ms < 1 or not 0 <= confidence <= 1:
        raise ValueError("最短音符时长或置信度无效")
    try:
        import librosa
    except ImportError as exc:
        raise RuntimeError("缺少音频识别组件，请安装项目的 audio 可选依赖") from exc

    source = Path(audio_path)
    y, sample_rate = librosa.load(source, sr=22050, mono=True)
    if len(y) == 0:
        raise ValueError("音频文件为空")
    hop_length = 256
    f0, voiced, probabilities = librosa.pyin(
        y, fmin=librosa.midi_to_hz(fmin_note), fmax=librosa.midi_to_hz(fmax_note),
        sr=sample_rate, hop_length=hop_length,
    )
    pitches: list[int | None] = []
    for frequency, is_voiced, probability in zip(f0, voiced, probabilities):
        if not is_voiced or probability is None or probability < confidence or not math.isfinite(frequency):
            pitches.append(None)
        else:
            pitches.append(int(round(float(librosa.hz_to_midi(frequency)))))
    pitches = _median_smooth(pitches)
    frame_ms = hop_length / sample_rate * 1000
    notes = pitches_to_notes(pitches, frame_ms, min_note_ms)
    if not notes:
        raise ValueError("没有识别到清晰的单旋律音符；请尝试人声或单件乐器较突出的音频")
    output = write_midi(notes, output_path)
    return {"source": str(source.resolve()), "output": str(output.resolve()), "notes": len(notes),
            "duration_ms": round(len(y) / sample_rate * 1000),
            "warning": "自动识别适合单旋律；混音歌曲可能需要人工校正 MIDI。"}
