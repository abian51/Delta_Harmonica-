from __future__ import annotations

from .models import Action


STATUS = "GG_CREATED"


def actions_to_gg_events(actions: list[Action], timestamp_origin: int = 0) -> list[dict]:
    """Encode the observed GG 119 sample shape; native acceptance remains unverified.

    The recorded sample uses a large monotonic-clock origin. Generated review data
    deliberately uses zero unless a caller supplies an origin; GG acceptance of that
    origin is one of the remaining M2 questions.
    """
    result: list[dict] = []
    previous = 0
    event_num = 1
    for action in sorted(actions, key=lambda a: a.time_ms):
        delay = action.time_ms - previous
        if delay < 0:
            raise ValueError("negative delay")
        if delay:
            delay_code = {1: 1, 2: 2, 3: 4}.get(action.code, action.code) if action.kind == "mouse" else action.code
            result.append({"eventNum": event_num, "type": 4, "page": 1, "code": delay_code,
                           "extraData": delay, "timestamp": timestamp_origin + action.time_ms})
            event_num += 1
        result.append({"eventNum": event_num, "type": 2 if action.kind == "keyboard" else 0,
                       "page": 1, "code": action.code, "extraData": 1 if action.down else 0,
                       "timestamp": timestamp_origin + action.time_ms})
        event_num += 1
        previous = action.time_ms
    return result
