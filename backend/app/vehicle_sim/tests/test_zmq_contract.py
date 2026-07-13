import time

import pytest

from app.communication.message_bus import decode_bus_frame, encode_bus_frame
from app.communication.plc_feedback_aggregator import PlcFeedbackAggregator
from app.vehicle_sim.zmq_bus import DEFAULT_TOPICS, normalize_message


def test_wrapped_zmq_message_is_unwrapped_at_vehicle_boundary():
    normalized = normalize_message(
        {
            "topic": "driver_input",
            "timestamp": 123.0,
            "data": {
                "vehicle_id": "TRAIN-001",
                "type": "malicious_override",
                "traction_percent": 50.0,
            },
        }
    )

    assert normalized["type"] == "driver_input"
    assert normalized["timestamp"] == 123.0
    assert normalized["vehicle_id"] == "TRAIN-001"


def test_vehicle_subscriber_uses_onboard_ato_state_topic_not_fallback():
    assert "set_train_state" in DEFAULT_TOPICS
    assert "enable_fallback_ato" not in DEFAULT_TOPICS


def test_message_bus_uses_single_prefixed_json_frame():
    frame = encode_bus_frame(
        "driver_input", {"vehicle_id": "TRAIN-001"}, timestamp=123.0
    )
    assert frame.startswith('driver_input {"topic": "driver_input"')

    topic, envelope = decode_bus_frame(frame)
    assert topic == "driver_input"
    assert envelope == {
        "topic": "driver_input",
        "timestamp": 123.0,
        "data": {"vehicle_id": "TRAIN-001"},
    }


def test_message_bus_rejects_prefix_and_json_topic_mismatch():
    with pytest.raises(ValueError, match="does not match"):
        decode_bus_frame(
            'driver_input {"topic":"train_state","timestamp":1,"data":{}}'
        )


def test_plc_aggregator_sends_one_complete_cached_snapshot():
    calls = []
    aggregator = PlcFeedbackAggregator(lambda **kwargs: calls.append(kwargs))
    now = time.time()
    aggregator.on_message(
        "train_state",
        {
            "vehicle_id": "TRAIN-001",
            "vehicle_speed_kmh": 29.7,
            "high_voltage_on": True,
            "brake_bad_light": False,
            "door_open_light": False,
            "door_closed_light": True,
            "ato_capable": True,
            "ato_active": False,
        },
    )
    aggregator.on_message(
        "ato_state",
        {
            "vehicle_id": "TRAIN-001",
            "ato_active": True,
            "auto_reverse_cap": True,
            "auto_reverse_active": False,
        },
    )
    aggregator.on_message(
        "comm_state",
        {
            "driver_console_connected": True,
            "zmq_connected": True,
            "last_message_at": now,
        },
    )

    assert aggregator.flush_once(now=now) == 1
    assert calls == [
        {
            "vehicle_speed_kmh": 29.7,
            "high_voltage_on": True,
            "brake_bad_light": False,
            "door_open_light": False,
            "door_closed_light": True,
            "network_fault": False,
            "ato_capable": True,
            "wash_mode_status": False,
            "ato_active": True,
            "auto_reverse_cap": True,
            "auto_reverse_active": False,
        }
    ]


def test_partial_updates_do_not_reset_previous_plc_fields():
    calls = []
    aggregator = PlcFeedbackAggregator(lambda **kwargs: calls.append(kwargs))
    now = time.time()
    aggregator.on_message(
        "train_state",
        {
            "vehicle_id": "TRAIN-001",
            "vehicle_speed_kmh": 30.0,
            "high_voltage_on": True,
            "door_closed_light": True,
        },
    )
    aggregator.on_message(
        "train_state", {"vehicle_id": "TRAIN-001", "vehicle_speed_kmh": 31.0}
    )
    aggregator.on_message(
        "comm_state",
        {
            "driver_console_connected": True,
            "zmq_connected": True,
            "last_message_at": now,
        },
    )
    aggregator.flush_once(now=now)

    assert calls[0]["vehicle_speed_kmh"] == 31.0
    assert calls[0]["high_voltage_on"] is True
    assert calls[0]["door_closed_light"] is True


def test_network_fault_is_owned_by_aggregator_and_checks_staleness():
    aggregator = PlcFeedbackAggregator(lambda **kwargs: None, comm_timeout_sec=0.5)
    aggregator.on_message(
        "train_state", {"vehicle_id": "TRAIN-001", "vehicle_speed_kmh": 0.0}
    )
    aggregator.on_message(
        "comm_state",
        {
            "driver_console_connected": True,
            "zmq_connected": True,
            "last_message_at": 100.0,
        },
    )

    assert aggregator.build_snapshot("TRAIN-001", now=100.4)["network_fault"] is False
    assert aggregator.build_snapshot("TRAIN-001", now=100.6)["network_fault"] is True
