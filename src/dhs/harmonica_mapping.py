from __future__ import annotations

import json
from pathlib import Path


class MappingProfile:
    def __init__(self, data: dict):
        self.data = data
        self.base = int(data["base_midi_note"])
        self.keys = data["natural_keys"]
        self.codes = data["key_codes"]

    @property
    def pitch_range(self) -> tuple[int, int]:
        # The game's down/up controls shift the eight-key row by one octave.
        return self.base - 12, self.base + 25

    def fold_pitch(self, pitch: int) -> int:
        """Move only an unplayable note by whole octaves into the playable range."""
        low, high = self.pitch_range
        while pitch < low:
            pitch += 12
        while pitch > high:
            pitch -= 12
        return pitch

    @classmethod
    def load(cls, path: str | Path) -> "MappingProfile":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def resolve(self, pitch: int) -> tuple[int, list[tuple[str, int]], str]:
        if not self.pitch_range[0] <= pitch <= self.pitch_range[1]:
            raise ValueError(f"MIDI note {pitch} is outside the configured range")
        naturals = (0, 2, 4, 5, 7, 9, 11, 12)
        candidates = []
        for shift, shift_name in ((0, None), (-1, "octave_down_modifier"), (1, "octave_up_modifier")):
            for index, offset in enumerate(naturals):
                for sharp in (0, 1):
                    if pitch != self.base + shift * 12 + offset + sharp:
                        continue
                    key = self.keys[index]
                    modifiers = []
                    if shift_name:
                        mod = self.data[shift_name]
                        modifiers.append((mod["button"], int(mod["code"])))
                    if sharp:
                        mod = self.data["accidental_modifier"]
                        modifiers.append((mod["button"], int(mod["code"])))
                    candidates.append((len(modifiers), bool(shift), sharp, index,
                                       int(self.codes[key]), modifiers, key))
        if not candidates:
            raise ValueError(f"MIDI note {pitch} is outside the configured range")
        _, _, _, _, code, modifiers, key = min(candidates)
        return code, modifiers, key
