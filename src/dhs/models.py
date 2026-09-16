from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Note:
    pitch: int
    start_ms: float
    end_ms: float
    track: int = 0
    velocity: int = 64

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Action:
    time_ms: int
    kind: str
    code: int
    down: bool
    label: str

    def to_dict(self) -> dict:
        return asdict(self)

