import json

import pytest

from dhs.gg_engine_api import GGEngineError, actions_to_api_events, create_macro, list_macros
from dhs.models import Action


def test_api_events_use_current_editor_shape():
    events = actions_to_api_events(
        [
            Action(0, "mouse", 3, True, "middle"),
            Action(25, "keyboard", 29, True, "Z"),
            Action(60, "keyboard", 29, False, "Z"),
            Action(60, "mouse", 3, False, "middle"),
        ]
    )
    assert "eventNum" not in events[0]
    assert events[0] == {"type": 0, "page": 0, "code": 3, "extraData": 1, "timestamp": 0}
    assert events[1] == {"type": 4, "page": 0, "code": 0, "extraData": 25, "timestamp": 0}
    assert events[-1]["extraData"] == 0


def test_create_macro_validates_then_posts_serialized_events():
    calls = []

    def request(method, path, payload=None):
        calls.append((method, path, payload))
        if path == "macro/validate":
            return {"macroValidation": {"nameValidations": []}}
        return {"macro_id": "new-id"}

    events = [{"type": 2, "page": 1, "code": 29, "extraData": 1, "timestamp": 0}]
    assert create_macro("DHS_TEST", events, request=request) == "new-id"
    assert calls[0] == ("POST", "macro/validate", {"id": 0, "name": "DHS_TEST"})
    payload = calls[1][2]
    assert json.loads(payload["events"]) == events
    assert json.loads(payload["recordingOptions"])["delayState"] == 0


def test_create_macro_rejects_name_validation_error():
    def request(method, path, payload=None):
        return {"macroValidation": {"nameValidations": ["NAME_IN_USE"]}}

    with pytest.raises(GGEngineError, match="NAME_IN_USE"):
        create_macro("duplicate", [{"type": 2}], request=request)


def test_list_macros_checks_response_shape():
    assert list_macros(request=lambda *_: {"macros": [{"id": "one"}]}) == [{"id": "one"}]
    with pytest.raises(GGEngineError):
        list_macros(request=lambda *_: {})
