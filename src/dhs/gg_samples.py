from __future__ import annotations

import json


def decode_events(raw: str) -> list[dict]:
    events = json.loads(raw)
    if not isinstance(events, list):
        raise ValueError("GG events must be a JSON array")
    required = {"eventNum", "type", "page", "code", "extraData", "timestamp"}
    for event in events:
        if not required.issubset(event):
            raise ValueError("GG event is missing required fields")
    return events


def encode_events(events: list[dict]) -> str:
    return json.dumps(events, ensure_ascii=False, separators=(",", ":"))

