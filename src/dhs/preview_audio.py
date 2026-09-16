from __future__ import annotations

import math
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

from .models import Action, Note


@dataclass(frozen=True)
class PreviewTone:
    pitch: int
    start_ms: int
    end_ms: int


def tones_from_timeline(notes: list[Note], actions: list[Action]) -> list[PreviewTone]:
    """Align pitch with the actual keyboard events after safe-gap adjustment."""
    active: dict[int, int] = {}
    intervals: list[tuple[int, int]] = []
    for action in actions:
        if action.kind != "keyboard":
            continue
        if action.down:
            if action.code in active:
                raise ValueError("时间轴中有重复按下的键")
            active[action.code] = action.time_ms
        else:
            if action.code not in active:
                raise ValueError("时间轴中有未配对的松键动作")
            intervals.append((active.pop(action.code), action.time_ms))
    if active or len(intervals) != len(notes):
        raise ValueError("旋律音符与键盘时间轴不一致")
    intervals.sort()
    ordered_notes = sorted(notes, key=lambda note: (note.start_ms, note.pitch))
    return [PreviewTone(note.pitch, start, end) for note, (start, end) in zip(ordered_notes, intervals)]


def scale_preview(actions: list[Action], tones: list[PreviewTone], ratio: float
                  ) -> tuple[list[Action], list[PreviewTone]]:
    if ratio <= 0:
        raise ValueError("试听倍速必须大于零")
    scaled_actions = [Action(round(action.time_ms / ratio), action.kind, action.code,
                             action.down, action.label) for action in actions]
    scaled_tones = [PreviewTone(tone.pitch, round(tone.start_ms / ratio),
                                max(round(tone.start_ms / ratio) + 1, round(tone.end_ms / ratio)))
                    for tone in tones]
    return scaled_actions, scaled_tones


def clip_tones(tones: list[PreviewTone], start_ms: int, end_ms: int) -> list[PreviewTone]:
    if start_ms < 0 or end_ms <= start_ms:
        raise ValueError("截取终点必须晚于起点，且起点不能为负")
    return [PreviewTone(tone.pitch, max(tone.start_ms, start_ms) - start_ms,
                        min(tone.end_ms, end_ms) - start_ms)
            for tone in tones if tone.start_ms < end_ms and tone.end_ms > start_ms]


def synthesize_preview(tones: list[PreviewTone], output_path: str | Path,
                       sample_rate: int = 22050, duration_ms: int | None = None) -> Path:
    """Write an offline, monophonic harmonica-like guide tone as a WAV file."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if sample_rate < 8000:
        raise ValueError("采样率过低")
    audio_duration_ms = max(max((tone.end_ms for tone in tones), default=0), duration_ms or 0) + 250
    if audio_duration_ms > 10 * 60 * 1000:
        raise ValueError("试听预览最多支持 10 分钟；导出宏不受此限制")
    sample_count = max(1, math.ceil(audio_duration_ms * sample_rate / 1000))
    samples = array("h", [0]) * sample_count
    for tone in tones:
        if not 0 <= tone.pitch <= 127 or tone.end_ms <= tone.start_ms:
            raise ValueError("无效的试听音符")
        frequency = 440.0 * 2 ** ((tone.pitch - 69) / 12)
        first = max(0, round(tone.start_ms * sample_rate / 1000))
        last = min(sample_count, round(tone.end_ms * sample_rate / 1000))
        for index in range(first, last):
            local = index - first
            t = local / sample_rate
            attack = min(1.0, local / max(1, round(0.015 * sample_rate)))
            release = min(1.0, (last - index) / max(1, round(0.025 * sample_rate)))
            envelope = max(0.0, min(attack, release))
            phase = 2 * math.pi * frequency * t
            value = (math.sin(phase) + 0.38 * math.sin(2 * phase)
                     + 0.16 * math.sin(3 * phase)) / 1.54
            samples[index] = max(-32768, min(32767, samples[index] + round(17000 * envelope * value)))
    with wave.open(str(output), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(samples.tobytes())
    return output
