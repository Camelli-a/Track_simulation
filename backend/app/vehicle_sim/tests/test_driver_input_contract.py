import pytest
from pydantic import ValidationError

from app.data_flow.data_mapper import normalize_driver_input
from app.data_flow.schemas import DriverInput as DriverInputSchema
from app.vehicle_sim.adapters.driver_plc_mapping import decode_driver_control
from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.models import AtoCommand, DriverInput, MaLimit
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


def _apply_valid_ma(train, ma_limit=500.0, allowed_speed=30.0):
    train.apply_ma_state(
        MaLimit(
            vehicle_id=train.state.vehicle_id,
            ma_limit=ma_limit,
            target_speed=allowed_speed,
            reason="test",
            allowed_speed_kmh=allowed_speed,
            eb_trigger_speed_kmh=allowed_speed + 8.0,
            target_distance_m=max(0.0, ma_limit - train.state.position),
            permission="allow",
            signal_state="green",
        )
    )


def test_driver_handle_uses_percent_as_canonical_control():
    traction = decode_driver_control(
        {"main_handle_raw": 1, "traction_percent": 62.5, "traction_level": 4}
    )
    braking = decode_driver_control(
        {"main_handle_raw": 2, "brake_percent": 50.0, "brake_level": 7}
    )

    assert traction.traction_percent == 62.5
    assert traction.traction_level == 3
    assert braking.brake_percent == 50.0
    assert braking.brake_level == 4


def test_fast_brake_is_maximum_service_brake_not_emergency():
    control = decode_driver_control({"main_handle_raw": 4})

    assert control.brake_level == 7
    assert control.brake_percent == 100.0
    assert control.handle_mode == "fast_brake"


def test_brake_percent_wins_over_simultaneous_traction():
    control = decode_driver_control(
        {"traction_percent": 80.0, "brake_percent": 20.0}
    )

    assert control.traction_level == 0
    assert control.traction_percent == 0.0
    assert control.brake_percent == 20.0


def test_router_applies_manual_brake_level_seven_as_full_service_brake():
    train, router = _train_and_router()
    router.handle(
        {
            "type": "driver_input",
            "vehicle_id": "TRAIN-001",
            "direction": "forward",
            "brake_level": 7,
        }
    )
    train.step_tick(0.1)

    assert train.current_brake_level == 7
    assert train.current_brake_percent == pytest.approx(100.0)
    assert not train.state.emergency_brake


def test_key_off_and_neutral_direction_block_traction():
    train, _ = _train_and_router()
    train.step_manual(
        _manual(traction_level=4, traction_percent=100.0, key_switch=False), 0.1
    )
    train.step_tick(0.1)
    assert train.current_traction_percent == 0.0

    train.key_switch_active = True
    train.step_manual(
        _manual(traction_level=4, traction_percent=100.0, direction="neutral"), 0.1
    )
    train.step_tick(0.1)
    assert train.current_traction_percent == 0.0


def test_reverse_direction_moves_toward_decreasing_absolute_mileage():
    train, _ = _train_and_router()
    train.state.position = 100.0
    train.step_manual(
        _manual(traction_level=4, traction_percent=100.0, direction="reverse"), 0.1
    )
    train.step_tick(0.1)

    assert train.state.direction_code == -1
    assert train.state.position < 100.0


def test_plc_ato_fields_are_requests_and_readback_not_mode_authority():
    train, _ = _train_and_router()
    train.step_manual(
        _manual(ato_start_btn=True, ato_capable=True, ato_active=True), 0.1
    )

    assert train.ato_start_requested is True
    assert train.ato_capable is True
    assert train.hardware_ato_active is True
    assert train.driving_mode == "SM"
    assert train.control_source == "manual"
    assert train.ato_start_accepted is False
    assert "ma_invalid" in train.ato_start_reject_reason


def test_ato_start_button_enters_am_when_preconditions_are_ready():
    train, _ = _train_and_router()
    _apply_valid_ma(train)

    train.step_manual(
        _manual(
            ato_start_btn=True,
            ato_capable=True,
            ato_active=False,
            door_closed_light=True,
            key_switch=True,
            parking_release=True,
        ),
        0.1,
    )

    assert train.ato_start_requested is True
    assert train.ato_start_accepted is True
    assert train.ato_start_reject_reason is None
    assert train.driving_mode == "AM"
    assert train.control_source == "ato"


def test_am_latches_until_explicit_mode_down_confirm():
    train, _ = _train_and_router()
    _apply_valid_ma(train)
    train.step_manual(_manual(ato_start_btn=True), 0.1)

    train.step_manual(_manual(ato_start_btn=False, control_mode="manual"), 0.1)

    assert train.driving_mode == "AM"
    assert train.control_source == "ato"

    train.step_manual(_manual(mode_dn_confirm=True), 0.1)

    assert train.driving_mode == "SM"
    assert train.control_source == "manual"


def test_ato_levels_remain_zero_to_four():
    train, _ = _train_and_router()
    train.step_ato(
        AtoCommand(
            vehicle_id="TRAIN-001",
            line_id="LINE-1",
            control_mode="ato",
            target_speed=0.0,
            target_position=None,
            traction_level=9,
            brake_level=7,
            reason="test",
        ),
        0.1,
    )

    assert train.requested_traction_level == 0
    assert train.requested_brake_level == 4
    assert train.requested_brake_percent == 100.0


def test_diagnostic_lights_do_not_become_control_or_comm_state():
    train, _ = _train_and_router()
    train.comm_ok = True
    train.step_manual(
        _manual(brake_bad_light=True, network_fault_light=True), 0.1
    )

    assert train.hardware_brake_bad_light is True
    assert train.hardware_network_fault_light is True
    assert train.comm_ok is True
    assert train.state.brake_bad_light is False
    assert train.requested_brake_percent == 0.0


def test_parking_release_requires_stopped_non_emergency_state():
    train, _ = _train_and_router()
    train.step_manual(_manual(parking_apply=True), 0.1)
    assert train.parking_brake_applied is True

    train.state.speed_ms = 1.0
    train.step_manual(_manual(parking_release=True), 0.1)
    assert train.parking_brake_applied is True

    train.state.speed_ms = 0.0
    train.step_manual(_manual(parking_release=False), 0.1)
    train.step_manual(_manual(parking_release=True), 0.1)
    assert train.parking_brake_applied is False


def test_emergency_button_and_forced_release_are_not_conflated():
    train, _ = _train_and_router()
    train.step_manual(_manual(emergency_button=True), 0.1)
    train.step_tick(0.1)
    assert train.state.emergency_brake is True
    assert train.emergency_source == "emergency_button"

    train.step_manual(_manual(forced_release=True), 0.1)
    train.step_tick(0.1)
    assert train.state.emergency_brake is True


def test_data_flow_schema_and_mapper_cover_new_contract():
    normalized = normalize_driver_input(
        {
            "vehicleId": "TRAIN-001",
            "brakeLevel": 7,
            "directionCode": 2,
            "vigilance": True,
            "networkFaultLight": True,
        }
    )
    assert normalized["brake_level"] == 7
    assert normalized["direction_code"] == 2
    assert normalized["vigilance"] is True
    assert normalized["network_fault_light"] is True

    DriverInputSchema(
        vehicle_id="TRAIN-001",
        brake_level=7,
        direction="reverse",
        direction_code=2,
        updated_at=0.0,
    )
    with pytest.raises(ValidationError):
        DriverInputSchema(
            vehicle_id="TRAIN-001", brake_level=8, updated_at=0.0
        )
