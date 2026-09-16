from __future__ import annotations

from .models import Note


def select_monophonic(notes: list[Note], policy: str = "reject") -> list[Note]:
    if policy not in {"reject", "highest", "lowest"}:
        raise ValueError("policy must be reject, highest, or lowest")
    ordered = sorted(notes, key=lambda n: (n.start_ms, n.pitch, n.end_ms))
    groups: list[list[Note]] = []
    for note in ordered:
        overlapping = [g for g in groups if any(note.start_ms < n.end_ms and note.end_ms > n.start_ms for n in g)]
        if not overlapping:
            groups.append([note])
        else:
            overlapping[0].append(note)
    if policy == "reject" and any(len(g) > 1 for g in groups):
        raise ValueError("Polyphonic overlap detected; choose highest or lowest explicitly")
    chooser = max if policy == "highest" else min
    return [chooser(g, key=lambda n: n.pitch) if len(g) > 1 else g[0] for g in groups]


def transform(notes: list[Note], transpose: int = 0, speed: float = 1.0, min_hold_ms: int = 35) -> list[Note]:
    if speed <= 0:
        raise ValueError("speed must be positive")
    result = []
    for n in notes:
        start = n.start_ms / speed
        end = max(n.end_ms / speed, start + min_hold_ms)
        result.append(Note(n.pitch + transpose, start, end, n.track, n.velocity))
    return result

