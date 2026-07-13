from app.communication.driver_desk_test_rig import DriverDeskBridgeService
from app.communication.plc_feedback_aggregator import PlcFeedbackAggregator


def test_driver_desk_bridge_snapshot_reports_bus_activity():
    service = DriverDeskBridgeService()

    service._on_driver_input(
        "driver_input",
        {"vehicle_id": "TRAIN-001", "source": "driver_tcp"},
    )
    service._on_comm_state(
        "comm_state",
        {
            "source": "driver_tcp",
            "driver_console_connected": True,
            "zmq_connected": True,
        },
    )
    service._on_feedback_state(
        "train_state",
        {"vehicle_id": "TRAIN-001"},
    )

    snapshot = service.snapshot()
    diagnostics = snapshot["bus_diagnostics"]

    assert diagnostics["driver_input_count"] == 1
    assert diagnostics["comm_state_count"] == 1
    assert diagnostics["train_state_count"] == 1
    assert diagnostics["last_driver_input_vehicle_id"] == "TRAIN-001"
    assert diagnostics["last_driver_input_source"] == "driver_tcp"
    assert diagnostics["last_feedback_vehicle_id"] == "TRAIN-001"
    assert diagnostics["driver_console_connected"] is True
    assert diagnostics["zmq_connected"] is True


def test_plc_feedback_aggregator_snapshot_tracks_flush_counts():
    sent_payloads = []

    aggregator = PlcFeedbackAggregator(lambda **kwargs: sent_payloads.append(kwargs))
    aggregator.set_active_vehicle_id("TRAIN-001")
    aggregator.on_message(
        "comm_state",
        {
            "driver_console_connected": True,
            "zmq_connected": True,
            "last_message_at": 1.0,
        },
    )
    aggregator.on_message(
        "train_state",
        {
            "vehicle_id": "TRAIN-001",
            "speed": 10.0,
        },
    )

    assert aggregator.flush_once(now=2.0) == 1

    snapshot = aggregator.snapshot()
    assert len(sent_payloads) == 1
    assert snapshot["active_vehicle_id"] == "TRAIN-001"
    assert snapshot["last_send_count"] == 1
    assert snapshot["total_send_count"] == 1
    assert snapshot["last_flush_at"] == 2.0
