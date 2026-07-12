import time

import pytest

from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.models import AtoCommand, DriverInput, MaLimit
from app.vehicle_sim.train_manager import TrainManager


def _train():
    return TrainManager(initial_count=1).get_train("TRAIN-001")


def _manual(traction=0, brake=0, emergency=False):
    return DriverInput(
        vehicle_id="TRAIN-001",
        line_id="LINE-1",
        source="test",
        control_mode="manual",
        traction_level=traction,
        brake_level=brake,
        direction="forward",
        emergency_button=emergency,
    )


def _ato(traction=0, brake=0):
    return AtoCommand(
        vehicle_id="TRAIN-001",
        line_id="LINE-1",
        control_mode="ato",
        target_speed=40.0,
        target_position=1000.0,
        traction_level=traction,
        brake_level=brake,
        reason="test",
    )


def _valid_ma(updated_at=None, target_distance_m=500.0):
    return MaLimit(
        vehicle_id="TRAIN-001",
        ma_limit=500.0,
        target_speed=40.0,
        reason="test",
        allowed_speed_kmh=50.0,
        target_distance_m=target_distance_m,
        permission="allow",
        signal_state="green",
        updated_at=time.time() if updated_at is None else updated_at,
    )


def test_step_manual_only_caches_and_does_not_move_train():
    train = _train()
    initial_position = train.state.position

    train.step_manual(_manual(traction=4), dt=0.1)

    assert train.state.position == initial_position
    assert train.state.speed_ms == 0.0
    assert train.requested_traction_level == 4
    assert train.current_traction_level == 0


def test_step_ato_only_caches_and_does_not_move_train():
    train = _train()

    train.step_ato(_ato(traction=4), dt=0.1)

    assert train.state.position == 0.0
    assert train.state.speed_ms == 0.0
    assert train.requested_traction_level == 4
    assert train.current_traction_level == 0
    assert train.driving_mode == "AM"


def test_one_step_tick_performs_exactly_one_dynamics_update(monkeypatch):
    train = _train()
    train.step_manual(_manual(traction=4), dt=0.1)
    calls = 0
    original = train._step

    def counted_step(traction_level, brake_level, dt):
        nonlocal calls
        calls += 1
        return original(traction_level, brake_level, dt)

    monkeypatch.setattr(train, "_step", counted_step)
    train.step_tick(0.1)

    assert calls == 1
    assert train.state.speed_ms > 0.0
    assert train.current_traction_level == 4


def test_n_ticks_perform_n_dynamics_updates(monkeypatch):
    train = _train()
    train.step_manual(_manual(traction=2), dt=0.02)
    calls = 0
    original = train._step

    def counted_step(traction_level, brake_level, dt):
        nonlocal calls
        calls += 1
        return original(traction_level, brake_level, dt)

    monkeypatch.setattr(train, "_step", counted_step)
    for _ in range(25):
        train.step_tick(0.02)

    assert calls == 25


def test_manual_emergency_is_applied_at_tick_boundary():
    train = _train()
    train.state.speed_ms = 5.0

    train.step_manual(_manual(traction=4, emergency=True), dt=0.1)
    assert train.state.emergency_brake is False

    train.step_tick(0.1)
    assert train.state.emergency_brake is True
    assert train.state.mode == "emergency"
    assert train.current_traction_level == 0
    assert train.current_brake_level == 4
    assert train.control_source == "emergency_button"

    train.step_manual(_manual(traction=4, emergency=False), dt=0.1)
    train.step_tick(0.1)
    assert train.current_traction_level == 0
    assert train.current_brake_level == 4
    assert train.control_source == "emergency_button"


def test_train_ma_helpers_validate_derive_distance_and_merge_track_limit():
    train = _train()
    train.state.position = 100.0
    train.apply_ma_state(_valid_ma(target_distance_m=None))
    now = train.ma_updated_at + 0.5

    assert train.has_valid_ma(now) is True
    assert train.get_distance_to_ma_m(now) == 400.0
    assert train.get_effective_speed_limit_kmh(now) == pytest.approx(
        min(50.0, train.track.get_speed_limit(100.0))
    )


def test_expired_ma_is_invalid_and_blocks_am_traction():
    train = _train()
    train.apply_ma_state(_valid_ma(updated_at=time.time() - 2.0))
    train.step_ato(_ato(traction=4), dt=0.1)

    assert train.has_valid_ma() is False
    assert train.get_distance_to_ma_m() is None
    assert train.get_effective_speed_limit_kmh() == 0.0

    train.step_tick(0.1)
    assert train.current_traction_level == 0
    assert train.state.speed_ms == 0.0


def test_router_caches_commands_and_preserves_explicit_ma_timestamp_zero():
    manager = TrainManager(initial_count=1)
    train = manager.get_train("TRAIN-001")
    router = MessageRouter(manager)

    router.handle(
        {
            "type": "driver_input",
            "vehicle_id": "TRAIN-001",
            "traction_level": 3,
            "brake_level": 0,
        }
    )
    assert train.state.position == 0.0
    assert train.requested_traction_level == 3

    router.handle(
        {
            "type": "ma_state",
            "timestamp": 0.0,
            "vehicle_id": "TRAIN-001",
            "ma_limit": 500.0,
            "distance_to_ma": 500.0,
            "speed_limit": 45.0,
            "permission": "allow",
            "signal_state": "green",
        }
    )
    assert train.ma_updated_at == 0.0
