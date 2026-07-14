import time

import pytest

from app.vehicle_sim.atp import AtpConfig, evaluate_atp
from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.models import DriverInput, TrainState
from app.vehicle_sim.train_manager import TrainManager


def _train_and_router():
    manager = TrainManager(initial_count=1)
    return manager.get_train("TRAIN-001"), MessageRouter(manager)


def _manual(**overrides):
    values = {
        "vehicle_id": "TRAIN-001",
        "line_id": "LINE-1",
        "source": "test",
        "control_mode": "manual",
        "traction_level": 0,
        "brake_level": 0,
        "direction": "forward",
        "emergency_button": False,
    }
    values.update(overrides)
    return DriverInput(**values)


def _atp_at_age(age_s: float):
    state = TrainState(
        vehicle_id="TRAIN-001",
        line_id="LINE-1",
        position=0.0,
        speed_ms=0.0,
        acceleration=0.0,
        mode="manual",
        is_running=False,
        emergency_brake=False,
    )
    return evaluate_atp(
        state=state,
        speed_limit=60.0,
        ma_limit=None,
        power_fault=False,
        comm_ok=True,
        last_message_at=100.0,
        now=100.0 + age_s,
        config=AtpConfig(
            comm_warning_timeout_sec=0.3,
            comm_timeout_sec=0.5,
        ),
    )


def test_comm_age_allows_normal_100ms_driver_frame_reuse():
    assert _atp_at_age(0.10).supervision_state == "normal"
    assert _atp_at_age(0.10).emergency_brake is False


def test_comm_age_warns_before_emergency_timeout():
    warning = _atp_at_age(0.31)
    assert warning.emergency_brake is False
    assert warning.supervision_state == "warning"
    assert warning.reason == "communication_delayed"


def test_comm_age_triggers_emergency_after_configured_timeout():
    emergency = _atp_at_age(0.51)
    assert emergency.emergency_brake is True
    assert emergency.reason == "communication_lost"


def test_train_uses_demo_tolerant_comm_timeouts_from_settings():
    train, _ = _train_and_router()

    assert train.comm_warning_timeout_sec == pytest.approx(1.5)
    assert train.comm_timeout_sec == pytest.approx(5.0)


def test_router_comm_state_updates_connection_and_timestamp_for_atp():
    train, router = _train_and_router()
    timestamp = time.time()
    router.handle(
        {
            "type": "comm_state",
            "source": "driver_tcp",
            "driver_console_connected": True,
            "zmq_connected": True,
            "last_message_at": timestamp,
        }
    )

    assert train.comm_ok is True
    assert train.last_comm_message_at == timestamp
    train.step_manual(_manual(traction_level=1), 0.02)
    for _ in range(5):
        train.step_tick(0.02)
    assert train.state.emergency_brake is False


@pytest.mark.parametrize(
    ("input_field", "event_attribute"),
    [
        ("ato_start_btn", "ato_start_requested"),
        ("forced_release", "forced_release_requested"),
        ("forced_pump", "forced_pump_requested"),
        ("horn", "horn_requested"),
        ("mode_up_confirm", "mode_up_confirmed"),
        ("mode_dn_confirm", "mode_down_confirmed"),
        ("confirm_flag", "confirm_requested"),
        ("auto_rev_flag", "auto_reverse_requested"),
        ("trac_aux_reset", "traction_aux_reset_requested"),
        ("vigilance", "vigilance_active"),
    ],
)
def test_transient_inputs_trigger_only_on_rising_edge(input_field, event_attribute):
    train, _ = _train_and_router()

    train.step_manual(_manual(**{input_field: True}), 0.02)
    assert getattr(train, event_attribute) is True
    train.step_tick(0.02)
    assert getattr(train, event_attribute) is False

    train.step_manual(_manual(**{input_field: True}), 0.02)
    assert getattr(train, event_attribute) is False
    train.step_manual(_manual(**{input_field: False}), 0.02)
    train.step_manual(_manual(**{input_field: True}), 0.02)
    assert getattr(train, event_attribute) is True


def test_door_button_held_high_does_not_reopen_after_first_event():
    train, _ = _train_and_router()
    train.state.position = 100.0
    train.step_manual(_manual(open_left_door=True), 0.02)
    train.step_tick(0.02)
    assert train.state.left_door_open is True

    train.door_state.close()
    train._sync_door_state()
    train.step_manual(_manual(open_left_door=True), 0.02)
    train.step_tick(0.02)
    assert train.state.doors_all_closed is True


def test_state_inputs_remain_level_triggered():
    train, _ = _train_and_router()
    train.step_manual(
        _manual(
            key_switch=False,
            direction="neutral",
            emergency_button=True,
            wash_mode_switch=True,
            ato_active=True,
            door_mode="right",
        ),
        0.02,
    )

    assert train.key_switch_active is False
    assert train.state.direction_code == 0
    assert train.manual_emergency_requested is True
    assert train.wash_mode_switch_active is True
    assert train.hardware_ato_active is True
    assert train.door_state.mode == "right"


def test_duplicate_frame_sequence_is_processed_only_once():
    train, _ = _train_and_router()
    train.step_manual(
        _manual(frame_seq=10, traction_level=4, traction_percent=100.0), 0.02
    )
    train.step_manual(
        _manual(frame_seq=10, brake_level=7, brake_percent=100.0), 0.02
    )

    assert train.requested_traction_level == 4
    assert train.requested_brake_level == 0
