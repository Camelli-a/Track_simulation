import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.signal_zmq_adapter import SignalZmqAdapter  # noqa: E402


class FakeBus:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.subscriptions = []
        self.published = []

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def subscribe(self, topic, handler):
        self.subscriptions.append((topic, handler))

    def publish(self, topic, data):
        self.published.append((topic, data))


class FakeClock:
    def __init__(self, now):
        self.now = now

    def time(self):
        return self.now


def _train_state():
    return {
        "vehicle_id": "TRAIN-001",
        "position": 300.0,
        "speed": 40.0,
        "route_id": "R_MAIN",
    }


def _published_data(fake_bus, topic):
    return [data for published_topic, data in fake_bus.published if published_topic == topic]


def test_start_subscribes_train_state_and_starts_publish_thread():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_interval_seconds=0.01)

    adapter.start()

    assert fake_bus.started is True
    assert [topic for topic, _ in fake_bus.subscriptions] == [
        "train_state",
        "route_request",
    ]
    assert adapter.publish_thread is not None
    assert adapter.publish_thread.is_alive()

    adapter.stop()

    assert fake_bus.stopped is True
    assert not adapter.publish_thread.is_alive()


def test_on_train_state_records_last_update_at():
    fake_bus = FakeBus()
    clock = FakeClock(100.0)
    adapter = SignalZmqAdapter(
        bus=fake_bus,
        publish_on_update=False,
        time_func=clock.time,
    )

    adapter.on_train_state("train_state", _train_state())

    assert adapter.train_last_update_at["TRAIN-001"] == 100.0
    assert adapter.train_states_by_id["TRAIN-001"] == _train_state()


def test_train_state_preserves_fault_speed_limit_and_emergency_brake():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=True)

    adapter.on_train_state(
        "train_state",
        {
            "vehicle_id": "TRAIN-001",
            "position": 620.0,
            "speed": 20.0,
            "route_id": "R_MAIN",
            "fault_speed_limit": "30",
            "emergency_brake": 1,
        },
    )

    cached_state = adapter.train_states_by_id["TRAIN-001"]
    assert cached_state["fault_speed_limit"] == 30.0
    assert cached_state["emergency_brake"] is True

    ma_limit = _published_data(fake_bus, "ma_state")[0]["ma_limits"][0]
    assert ma_limit["fault_speed_limit"] == 30.0
    assert ma_limit["permission"] == "stop"
    assert ma_limit["signal_state"] == "red"
    assert ma_limit["speed_limit"] == 0.0
    assert ma_limit["speed_limit_reason"] == "emergency_brake"


def test_publish_outputs_normal_when_train_state_not_stale():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=False)
    adapter.train_states_by_id["TRAIN-001"] = _train_state()
    adapter.train_last_update_at["TRAIN-001"] = 99.0

    adapter.publish_signal_outputs(now=100.0)

    assert [topic for topic, _ in fake_bus.published] == [
        "signal_state",
        "ma_state",
        "ato_command",
    ]
    ma_limit = _published_data(fake_bus, "ma_state")[0]["ma_limits"][0]
    assert ma_limit["communication_lost"] is False
    assert ma_limit["stale_duration"] == 0.0
    assert not _published_data(fake_bus, "alarm_event")
    assert _published_data(fake_bus, "ato_command")[0]["commands"]


def test_stale_train_state_forces_stop_permission():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=False)
    adapter.train_states_by_id["TRAIN-001"] = _train_state()
    adapter.train_last_update_at["TRAIN-001"] = 98.0

    adapter.publish_signal_outputs(now=100.0)

    ma_limit = _published_data(fake_bus, "ma_state")[0]["ma_limits"][0]
    assert ma_limit["communication_lost"] is True
    assert ma_limit["stale_duration"] == 2.0
    assert ma_limit["permission"] == "stop"
    assert ma_limit["signal_state"] == "red"
    assert ma_limit["speed_limit"] == 0.0
    assert ma_limit["target_speed"] == 0.0
    assert ma_limit["reason"] == "train_state_timeout"

    signal = _published_data(fake_bus, "signal_state")[0]["signals"][0]
    assert signal["state"] == "red"
    assert signal["signal_state"] == "red"
    assert signal["permission"] == "stop"


def test_stale_train_state_publishes_alarm_once():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=False)
    adapter.train_states_by_id["TRAIN-001"] = _train_state()
    adapter.train_last_update_at["TRAIN-001"] = 98.0

    adapter.publish_signal_outputs(now=100.0)
    adapter.publish_signal_outputs(now=100.25)

    alarms = _published_data(fake_bus, "alarm_event")
    assert len(alarms) == 1
    alarm = alarms[0]
    assert alarm["alarm_id"] == "SIGNAL-TRAIN-001-TIMEOUT"
    assert alarm["source"] == "SIGNAL"
    assert alarm["level"] == "critical"
    assert alarm["category"] == "communication"
    assert alarm["vehicle_id"] == "TRAIN-001"
    assert alarm["details"]["timeout_seconds"] == 1.6
    assert "type" not in alarm


def test_train_state_update_clears_timeout_alarm_key():
    fake_bus = FakeBus()
    clock = FakeClock(100.0)
    adapter = SignalZmqAdapter(
        bus=fake_bus,
        publish_on_update=False,
        time_func=clock.time,
    )
    adapter.train_states_by_id["TRAIN-001"] = _train_state()
    adapter.train_last_update_at["TRAIN-001"] = 98.0
    adapter.publish_signal_outputs(now=100.0)

    assert "train_state_timeout:TRAIN-001" in adapter.active_alarm_keys

    clock.now = 101.0
    adapter.on_train_state("train_state", _train_state())

    assert "train_state_timeout:TRAIN-001" not in adapter.active_alarm_keys
    assert adapter.train_last_update_at["TRAIN-001"] == 101.0


def test_message_data_has_no_double_wrapping_fields():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=False)
    adapter.train_states_by_id["TRAIN-001"] = _train_state()
    adapter.train_last_update_at["TRAIN-001"] = 98.0

    adapter.publish_signal_outputs(now=100.0)

    signal_data = _published_data(fake_bus, "signal_state")[0]
    ma_data = _published_data(fake_bus, "ma_state")[0]
    ato_data = _published_data(fake_bus, "ato_command")[0]
    alarm_data = _published_data(fake_bus, "alarm_event")[0]

    assert "type" not in signal_data
    assert "timestamp" not in signal_data
    assert "type" not in ma_data
    assert "timestamp" not in ma_data
    assert "type" not in ato_data
    assert "timestamp" not in ato_data
    assert "commands" in ato_data
    assert "type" not in alarm_data
    assert "occurred_at" in alarm_data


def test_on_route_request_open_adds_request():
    fake_bus = FakeBus()
    clock = FakeClock(100.0)
    adapter = SignalZmqAdapter(
        bus=fake_bus,
        publish_on_update=False,
        time_func=clock.time,
    )

    adapter.on_route_request(
        "route_request",
        {
            "vehicle_id": "TRAIN-003",
            "route_id": "R_BRANCH",
        },
    )

    assert len(adapter.route_requests) == 1
    request = adapter.route_requests[0]
    assert request["request_id"] == "REQ-TRAIN-003-R_BRANCH"
    assert request["vehicle_id"] == "TRAIN-003"
    assert request["route_id"] == "R_BRANCH"
    assert request["request_type"] == "open"
    assert request["priority"] == 0
    assert request["last_update_at"] == 100.0


def test_on_route_request_open_updates_duplicate_request():
    fake_bus = FakeBus()
    clock = FakeClock(100.0)
    adapter = SignalZmqAdapter(
        bus=fake_bus,
        publish_on_update=False,
        time_func=clock.time,
    )

    adapter.on_route_request(
        "route_request",
        {
            "request_id": "REQ-001",
            "vehicle_id": "TRAIN-003",
            "route_id": "R_BRANCH",
            "priority": 0,
        },
    )
    clock.now = 101.0
    adapter.on_route_request(
        "route_request",
        {
            "request_id": "REQ-002",
            "vehicle_id": "TRAIN-003",
            "route_id": "R_BRANCH",
            "priority": 5,
        },
    )

    assert len(adapter.route_requests) == 1
    assert adapter.route_requests[0]["request_id"] == "REQ-002"
    assert adapter.route_requests[0]["priority"] == 5
    assert adapter.route_requests[0]["last_update_at"] == 101.0


def test_on_route_request_cancel_specific_route():
    adapter = SignalZmqAdapter(bus=FakeBus(), publish_on_update=False)
    adapter.route_requests = [
        {"vehicle_id": "TRAIN-003", "route_id": "R_MAIN"},
        {"vehicle_id": "TRAIN-003", "route_id": "R_BRANCH"},
        {"vehicle_id": "TRAIN-004", "route_id": "R_BRANCH"},
    ]

    adapter.on_route_request(
        "route_request",
        {
            "vehicle_id": "TRAIN-003",
            "route_id": "R_BRANCH",
            "request_type": "cancel",
        },
    )

    assert adapter.route_requests == [
        {"vehicle_id": "TRAIN-003", "route_id": "R_MAIN"},
        {"vehicle_id": "TRAIN-004", "route_id": "R_BRANCH"},
    ]


def test_on_route_request_cancel_vehicle_all_routes():
    adapter = SignalZmqAdapter(bus=FakeBus(), publish_on_update=False)
    adapter.route_requests = [
        {"vehicle_id": "TRAIN-003", "route_id": "R_MAIN"},
        {"vehicle_id": "TRAIN-003", "route_id": "R_BRANCH"},
        {"vehicle_id": "TRAIN-004", "route_id": "R_BRANCH"},
    ]

    adapter.on_route_request(
        "route_request",
        {
            "vehicle_id": "TRAIN-003",
            "request_type": "cancel",
        },
    )

    assert adapter.route_requests == [
        {"vehicle_id": "TRAIN-004", "route_id": "R_BRANCH"},
    ]


def test_on_route_request_clear_all():
    adapter = SignalZmqAdapter(bus=FakeBus(), publish_on_update=False)
    adapter.route_requests = [
        {"vehicle_id": "TRAIN-003", "route_id": "R_MAIN"},
        {"vehicle_id": "TRAIN-004", "route_id": "R_BRANCH"},
    ]

    adapter.on_route_request("route_request", {"request_type": "clear"})

    assert adapter.route_requests == []


def test_on_route_request_invalid_missing_route_id_publishes_alarm():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=False)

    adapter.on_route_request(
        "route_request",
        {
            "vehicle_id": "TRAIN-003",
            "request_type": "open",
        },
    )

    assert adapter.route_requests == []
    alarm = _published_data(fake_bus, "alarm_event")[0]
    assert alarm["level"] == "warning"
    assert alarm["category"] == "route_request"
    assert alarm["details"]["reason"] == "missing_route_id"
    assert "type" not in alarm


def test_on_route_request_invalid_unsupported_type_publishes_alarm():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=False)

    adapter.on_route_request(
        "route_request",
        {
            "vehicle_id": "TRAIN-003",
            "route_id": "R_BRANCH",
            "request_type": "bad_type",
        },
    )

    assert adapter.route_requests == []
    alarm = _published_data(fake_bus, "alarm_event")[0]
    assert alarm["details"]["reason"] == "unsupported_request_type"
    assert alarm["details"]["request_type"] == "bad_type"


def test_route_request_triggers_immediate_publish_when_enabled():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=True)
    adapter.train_states_by_id["TRAIN-003"] = {
        "vehicle_id": "TRAIN-003",
        "position": 2435.0,
        "speed": 25.0,
        "route_id": "R_MAIN",
    }
    adapter.train_last_update_at["TRAIN-003"] = 100.0

    adapter.on_route_request(
        "route_request",
        {
            "vehicle_id": "TRAIN-003",
            "route_id": "R_BRANCH",
        },
    )

    assert "signal_state" in [topic for topic, _ in fake_bus.published]
    assert "ma_state" in [topic for topic, _ in fake_bus.published]
    assert "ato_command" in [topic for topic, _ in fake_bus.published]


def test_route_request_participates_in_snapshot_route_results():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=True)
    adapter.train_states_by_id["TRAIN-003"] = {
        "vehicle_id": "TRAIN-003",
        "position": 2435.0,
        "speed": 25.0,
        "route_id": "R_MAIN",
    }
    adapter.train_last_update_at["TRAIN-003"] = 100.0

    adapter.on_route_request(
        "route_request",
        {
            "vehicle_id": "TRAIN-003",
            "route_id": "R_BRANCH",
        },
    )

    route_results = _published_data(fake_bus, "signal_state")[-1]["route_results"]
    assert route_results[0]["vehicle_id"] == "TRAIN-003"
    assert route_results[0]["route_id"] == "R_BRANCH"
    assert route_results[0]["reason"] == "switch_locked_conflict"


def test_adapter_signal_state_includes_route_states():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=True)
    adapter.train_states_by_id["TRAIN-001"] = {
        "vehicle_id": "TRAIN-001",
        "position": 300.0,
        "speed": 25.0,
        "route_id": "R_MAIN",
    }
    adapter.train_last_update_at["TRAIN-001"] = 100.0

    adapter.on_route_request(
        "route_request",
        {
            "vehicle_id": "TRAIN-001",
            "route_id": "R_MAIN",
        },
    )

    signal_state = _published_data(fake_bus, "signal_state")[-1]
    assert "route_states" in signal_state
    assert signal_state["route_states"][0]["route_id"] == "R_MAIN"
    assert signal_state["route_states"][0]["state"] in {"locked", "active"}


def test_adapter_signal_state_switches_include_state_fields():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=True)
    adapter.train_states_by_id["TRAIN-001"] = {
        "vehicle_id": "TRAIN-001",
        "position": 300.0,
        "speed": 25.0,
        "route_id": "R_MAIN",
    }
    adapter.train_last_update_at["TRAIN-001"] = 100.0

    adapter.on_route_request(
        "route_request",
        {
            "vehicle_id": "TRAIN-001",
            "route_id": "R_MAIN",
        },
    )

    signal_state = _published_data(fake_bus, "signal_state")[-1]
    switch = signal_state["switches"][0]
    for field_name in (
        "state",
        "target_position",
        "moving",
        "fault",
        "four_open",
    ):
        assert field_name in switch


def test_route_request_does_not_break_timeout_fail_safe():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=False)
    adapter.train_states_by_id["TRAIN-003"] = {
        "vehicle_id": "TRAIN-003",
        "position": 2435.0,
        "speed": 25.0,
        "route_id": "R_MAIN",
    }
    adapter.train_last_update_at["TRAIN-003"] = 98.0
    adapter.route_requests = [
        {
            "vehicle_id": "TRAIN-003",
            "route_id": "R_BRANCH",
            "request_type": "open",
        }
    ]

    adapter.publish_signal_outputs(now=100.0)

    ma_limit = _published_data(fake_bus, "ma_state")[0]["ma_limits"][0]
    route_results = _published_data(fake_bus, "signal_state")[0]["route_results"]
    assert ma_limit["permission"] == "stop"
    assert ma_limit["reason"] == "train_state_timeout"
    assert route_results[0]["reason"] == "switch_locked_conflict"


def test_message_data_has_no_double_wrapping_after_route_request():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=True)
    adapter.train_states_by_id["TRAIN-003"] = {
        "vehicle_id": "TRAIN-003",
        "position": 2435.0,
        "speed": 25.0,
        "route_id": "R_MAIN",
    }
    adapter.train_last_update_at["TRAIN-003"] = 100.0

    adapter.on_route_request(
        "route_request",
        {
            "vehicle_id": "TRAIN-003",
            "route_id": "R_BRANCH",
        },
    )
    adapter.on_route_request(
        "route_request",
        {
            "vehicle_id": "TRAIN-003",
            "request_type": "open",
        },
    )

    signal_data = _published_data(fake_bus, "signal_state")[0]
    ma_data = _published_data(fake_bus, "ma_state")[0]
    ato_data = _published_data(fake_bus, "ato_command")[0]
    alarm_data = _published_data(fake_bus, "alarm_event")[0]

    assert "type" not in signal_data
    assert "timestamp" not in signal_data
    assert "type" not in ma_data
    assert "timestamp" not in ma_data
    assert "type" not in ato_data
    assert "timestamp" not in ato_data
    assert "type" not in alarm_data
    assert "occurred_at" in alarm_data


def test_adapter_publishes_ato_command():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=True)

    adapter.on_train_state(
        "train_state",
        {
            "vehicle_id": "TRAIN-001",
            "position": 300.0,
            "speed": 40.0,
            "route_id": "R_MAIN",
        },
    )

    ato_data = _published_data(fake_bus, "ato_command")[0]
    assert "commands" in ato_data
    assert ato_data["commands"][0]["vehicle_id"] == "TRAIN-001"
    assert ato_data["commands"][0]["target_speed"] <= ato_data["commands"][0]["safe_speed_limit"]


def test_ato_command_has_no_double_wrapping():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=True)

    adapter.on_train_state(
        "train_state",
        {
            "vehicle_id": "TRAIN-001",
            "position": 300.0,
            "speed": 40.0,
            "route_id": "R_MAIN",
        },
    )

    ato_data = _published_data(fake_bus, "ato_command")[0]
    assert "type" not in ato_data
    assert "timestamp" not in ato_data


def test_timeout_fail_safe_makes_ato_degraded():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=False)
    adapter.train_states_by_id["TRAIN-001"] = _train_state()
    adapter.train_last_update_at["TRAIN-001"] = 98.0

    adapter.publish_signal_outputs(now=100.0)

    command = _published_data(fake_bus, "ato_command")[0]["commands"][0]
    assert command["ato_state"] == "degraded"
    assert command["target_speed"] == 0.0
    assert command["brake_level"] == 5


def test_ato_command_strategy_fields_have_no_double_wrapping():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=True)

    adapter.on_train_state(
        "train_state",
        {
            "vehicle_id": "TRAIN-001",
            "position": 900.0,
            "speed": 20.0,
            "route_id": "R_MAIN",
        },
    )

    ato_data = _published_data(fake_bus, "ato_command")[0]
    command = ato_data["commands"][0]
    assert "type" not in ato_data
    assert "timestamp" not in ato_data
    assert "selected_strategy" in command
    for strategy_score in command["strategy_scores"]:
        assert "type" not in strategy_score
        assert "timestamp" not in strategy_score
