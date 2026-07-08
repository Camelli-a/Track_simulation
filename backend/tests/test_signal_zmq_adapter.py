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
    assert fake_bus.subscriptions[0][0] == "train_state"
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


def test_publish_outputs_normal_when_train_state_not_stale():
    fake_bus = FakeBus()
    adapter = SignalZmqAdapter(bus=fake_bus, publish_on_update=False)
    adapter.train_states_by_id["TRAIN-001"] = _train_state()
    adapter.train_last_update_at["TRAIN-001"] = 99.0

    adapter.publish_signal_outputs(now=100.0)

    assert [topic for topic, _ in fake_bus.published] == ["signal_state", "ma_state"]
    ma_limit = _published_data(fake_bus, "ma_state")[0]["ma_limits"][0]
    assert ma_limit["communication_lost"] is False
    assert ma_limit["stale_duration"] == 0.0
    assert not _published_data(fake_bus, "alarm_event")


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
    alarm_data = _published_data(fake_bus, "alarm_event")[0]

    assert "type" not in signal_data
    assert "timestamp" not in signal_data
    assert "type" not in ma_data
    assert "timestamp" not in ma_data
    assert "type" not in alarm_data
    assert "occurred_at" in alarm_data
