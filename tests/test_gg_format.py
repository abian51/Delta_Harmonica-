import json

from dhs.gg_native_adapter import actions_to_gg_events
from dhs.gg_samples import decode_events, encode_events
from dhs.models import Action


def test_sample_round_trip():
    sample = [{"eventNum": 0, "type": 2, "page": 1, "code": 29, "extraData": 1, "timestamp": 0}]
    assert decode_events(encode_events(sample)) == sample


def test_synthetic_z_delay_release():
    events = actions_to_gg_events([Action(0, "keyboard", 29, True, "Z"), Action(100, "keyboard", 29, False, "Z")])
    assert [e["type"] for e in events] == [2, 4, 2]
    assert events[1]["extraData"] == 100
    assert [e["eventNum"] for e in events] == [1, 2, 3]
    assert events[1] == {"eventNum": 2, "type": 4, "page": 1, "code": 29,
                         "extraData": 100, "timestamp": 100}


def test_mouse_modifier_shape():
    events = actions_to_gg_events([Action(0, "mouse", 1, True, "left"), Action(0, "keyboard", 29, True, "Z"),
                                   Action(80, "keyboard", 29, False, "Z"), Action(80, "mouse", 1, False, "left")])
    assert any(e["type"] == 0 and e["extraData"] == 1 for e in events)
    assert all(e["extraData"] >= 0 for e in events if e["type"] == 4)


def test_middle_mouse_delay_uses_observed_bitmask_code():
    events = actions_to_gg_events([Action(0, "mouse", 3, True, "middle"),
                                   Action(140, "mouse", 3, False, "middle")], timestamp_origin=1000)
    delay = events[1]
    assert delay["type"] == 4 and delay["code"] == 4
    assert delay["timestamp"] == 1140
