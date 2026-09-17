from __future__ import annotations

from .models import Note


def select_monophonic(notes: list[Note], policy: str = "reject") -> list[Note]:
    if policy not in {"reject", "highest", "lowest"}:
        raise ValueError("policy must be reject, highest, or lowest")
    if not notes:
        return []
    ordered = sorted(notes, key=lambda n: (n.start_ms, n.pitch, n.end_ms))
    boundaries = sorted({time for note in ordered for time in (note.start_ms, note.end_ms)})
    result: list[Note] = []
    for start, end in zip(boundaries, boundaries[1:]):
        active = [note for note in ordered if note.start_ms <= start and note.end_ms >= end]
        if not active:
            continue
        if policy == "reject" and len(active) > 1:
            raise ValueError("Polyphonic overlap detected; choose highest or lowest explicitly")
        chosen = (max(active, key=lambda note: note.pitch) if policy == "highest"
                  else min(active, key=lambda note: note.pitch))
        if (result and result[-1].end_ms == start and result[-1].pitch == chosen.pitch
                and result[-1].track == chosen.track):
            previous = result[-1]
            result[-1] = Note(previous.pitch, previous.start_ms, end, previous.track, previous.velocity)
        else:
            result.append(Note(chosen.pitch, start, end, chosen.track, chosen.velocity))
    return result


def transform(notes: list[Note], transpose: int = 0, speed: float = 1.0, min_hold_ms: int = 35) -> list[Note]:
    if speed <= 0:
        raise ValueError("speed must be positive")
    result = []
    for n in notes:
        start = n.start_ms / speed
        end = max(n.end_ms / speed, start + min_hold_ms)
        result.append(Note(n.pitch + transpose, start, end, n.track, n.velocity))
    return result
