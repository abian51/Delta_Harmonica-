from __future__ import annotations

import json
from pathlib import Path


class MappingProfile:
    def __init__(self, data: dict):
        self.data = data
        self.base = int(data["base_midi_note"])
        self.keys = data["natural_keys"]
        self.codes = data["key_codes"]

    @classmethod
    def load(cls, path: str | Path) -> "MappingProfile":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def resolve(self, pitch: int) -> tuple[int, list[tuple[str, int]], str]:
        delta = pitch - self.base
        octave, degree = divmod(delta, 12)
        naturals = [0, 2, 4, 5, 7, 9, 11]
        accidental = degree not in naturals
        natural_degree = max((x for x in naturals if x <= degree), default=0)
        index = octave * 7 + naturals.index(natural_degree)
        if not 0 <= index < len(self.keys):
            raise ValueError(f"MIDI note {pitch} is outside the configured range")
        key = self.keys[index]
        modifiers = []
        if accidental:
            mod = self.data["accidental_modifier"]
            modifiers.append((mod["button"], int(mod["code"])))
        return int(self.codes[key]), modifiers, key

