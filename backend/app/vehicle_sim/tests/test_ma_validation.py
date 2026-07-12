import math

import pytest

from app.vehicle_sim.ma_validation import (
    calculate_distance_to_ma,
    effective_allowed_speed,
    validate_ma,
)


def _valid_ma(**overrides):
    values = {
        "position_m": 100.0,
        "ma_limit_m": 250.0,
        "target_distance_m": 150.0,
        "allowed_speed_kmh": 45.0,
        "permission": "restricted",
        "signal_state": "yellow",
        "updated_at": 100.0,
        "now": 101.0,
    }
    values.update(overrides)
    return validate_ma(**values)


def test_valid_ma_is_normalized_and_permits_traction():
    result = _valid_ma(permission=" ALLOW ", signal_state=" GREEN ")

    assert result.valid is True
    assert result.traction_permitted is True
    assert result.permission == "allow"
    assert result.signal_state == "green"
    assert result.distance_to_ma_m == 150.0
    assert result.distance_source == "conservative"
    assert result.age_sec == 1.0
    assert result.errors == ()


def test_missing_target_distance_is_derived_from_absolute_ma_limit():
    result = _valid_ma(target_distance_m=None, position_m=120.0, ma_limit_m=250.0)

    assert result.valid is True
    assert result.distance_to_ma_m == 130.0
    assert result.distance_source == "ma_limit"


def test_target_distance_can_be_used_when_absolute_limit_is_missing():
    result = _valid_ma(ma_limit_m=None, target_distance_m=75.0)

    assert result.valid is True
    assert result.ma_limit_m is None
    assert result.distance_to_ma_m == 75.0
    assert result.distance_source == "target_distance"


def test_both_missing_authority_fields_are_invalid():
    result = _valid_ma(ma_limit_m=None, target_distance_m=None)

    assert result.valid is False
    assert result.distance_to_ma_m is None
    assert result.reason == "missing_authority_distance"


def test_mismatched_distances_use_more_conservative_non_negative_value():
    result = _valid_ma(ma_limit_m=300.0, target_distance_m=80.0)

    assert result.valid is True
    assert result.distance_to_ma_m == 80.0
    assert result.distance_source == "conservative"
    assert result.warnings == ("distance_mismatch",)


def test_small_distance_difference_within_tolerance_has_no_warning():
    result = _valid_ma(
        ma_limit_m=250.8,
        target_distance_m=150.0,
        consistency_tolerance_m=1.0,
    )

    assert result.valid is True
    assert result.distance_to_ma_m == 150.0
    assert result.warnings == ()


@pytest.mark.parametrize("field", ["ma_limit_m", "target_distance_m"])
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, "100", True])
def test_non_finite_or_non_numeric_authority_fields_are_invalid(field, value):
    result = _valid_ma(**{field: value})

    assert result.valid is False
    error = "invalid_ma_limit" if field == "ma_limit_m" else "invalid_target_distance"
    assert error in result.errors


@pytest.mark.parametrize(
    ("overrides", "expected_error"),
    [
        ({"position_m": -0.1}, "negative_position"),
        ({"ma_limit_m": -0.1}, "negative_ma_limit"),
        ({"target_distance_m": -0.1}, "negative_target_distance"),
    ],
)
def test_semantically_negative_position_and_distance_fields_are_invalid(
    overrides, expected_error
):
    result = _valid_ma(**overrides)

    assert result.valid is False
    assert expected_error in result.errors


@pytest.mark.parametrize("value", [None, math.nan, math.inf, -math.inf, "45", True])
def test_missing_non_finite_or_non_numeric_allowed_speed_is_invalid(value):
    result = _valid_ma(allowed_speed_kmh=value)

    assert result.valid is False
    assert result.allowed_speed_kmh is None
    assert "invalid_allowed_speed" in result.errors


def test_negative_allowed_speed_is_invalid():
    result = _valid_ma(allowed_speed_kmh=-0.1)

    assert result.valid is False
    assert result.allowed_speed_kmh is None
    assert "negative_allowed_speed" in result.errors


@pytest.mark.parametrize(
    ("permission", "signal_state"),
    [("allow", "red"), ("restricted", "green"), ("stop", "yellow")],
)
def test_permission_and_signal_conflicts_are_invalid(permission, signal_state):
    result = _valid_ma(permission=permission, signal_state=signal_state)

    assert result.valid is False
    assert "permission_signal_conflict" in result.errors


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("permission", None, "invalid_permission"),
        ("permission", "unknown", "invalid_permission"),
        ("signal_state", None, "invalid_signal_state"),
        ("signal_state", "blue", "invalid_signal_state"),
    ],
)
def test_missing_or_unknown_permission_and_signal_are_invalid(
    field, value, expected_error
):
    result = _valid_ma(**{field: value})

    assert result.valid is False
    assert expected_error in result.errors


def test_stop_red_is_fail_safe_and_positive_speed_is_a_conflict():
    result = _valid_ma(
        permission="stop",
        signal_state="red",
        allowed_speed_kmh=20.0,
    )

    assert result.valid is False
    assert result.traction_permitted is False
    assert "movement_not_permitted" in result.errors
    assert "stop_speed_conflict" in result.errors


def test_stop_red_at_zero_speed_remains_unusable_for_traction():
    result = _valid_ma(
        permission="stop",
        signal_state="red",
        allowed_speed_kmh=0.0,
    )

    assert result.valid is False
    assert result.traction_permitted is False
    assert result.errors == ("movement_not_permitted",)


@pytest.mark.parametrize(
    ("permission", "signal_state"),
    [("allow", "green"), ("restricted", "yellow")],
)
def test_movement_permission_with_zero_speed_is_a_semantic_conflict(
    permission, signal_state
):
    result = _valid_ma(
        permission=permission,
        signal_state=signal_state,
        allowed_speed_kmh=0.0,
    )

    assert result.valid is False
    assert result.traction_permitted is False
    assert "movement_speed_conflict" in result.errors


def test_ma_older_than_timeout_is_expired_but_exact_boundary_is_valid():
    expired = _valid_ma(updated_at=100.0, now=101.600001, timeout_sec=1.6)
    boundary = _valid_ma(updated_at=100.0, now=101.6, timeout_sec=1.6)

    assert expired.valid is False
    assert "ma_expired" in expired.errors
    assert boundary.valid is True


def test_missing_or_future_timestamp_is_invalid():
    missing = _valid_ma(updated_at=None)
    future = _valid_ma(updated_at=102.0, now=101.0)

    assert missing.reason == "invalid_updated_at"
    assert "ma_timestamp_in_future" in future.errors


def test_future_timestamp_within_configured_clock_tolerance_is_valid():
    result = _valid_ma(
        updated_at=101.2,
        now=101.0,
        future_tolerance_sec=0.25,
    )

    assert result.valid is True
    assert result.age_sec == 0.0


def test_source_or_communication_failure_invalidates_ma():
    source_failure = _valid_ma(source_ok=False)
    comm_failure = _valid_ma(communication_ok=False)

    assert source_failure.valid is False
    assert source_failure.reason == "source_unavailable"
    assert comm_failure.valid is False
    assert comm_failure.reason == "communication_lost"


def test_reverse_direction_uses_decreasing_absolute_mileage():
    assert calculate_distance_to_ma(250.0, 100.0, direction_code=2) == 150.0
    assert calculate_distance_to_ma(250.0, 100.0, direction_code="backward") == 150.0
    assert calculate_distance_to_ma(250.0, 100.0, direction_code=" REVERSE ") == 150.0

    result = _valid_ma(
        position_m=250.0,
        ma_limit_m=100.0,
        target_distance_m=None,
        direction_code=2,
    )

    assert result.valid is True
    assert result.distance_to_ma_m == 150.0


def test_authority_behind_train_is_invalid_and_clamped_to_zero():
    result = _valid_ma(
        position_m=250.0,
        ma_limit_m=100.0,
        target_distance_m=None,
        direction_code=1,
    )

    assert result.valid is False
    assert result.distance_to_ma_m == 0.0
    assert "authority_behind_train" in result.errors
    assert "authority_exhausted_with_movement_permission" in result.errors


def test_authority_endpoint_boundary_does_not_create_forward_authority():
    assert calculate_distance_to_ma(100.0, 100.0, direction_code=1) == 0.0

    result = _valid_ma(
        position_m=100.0,
        ma_limit_m=100.0,
        target_distance_m=0.0,
    )

    assert result.valid is False
    assert result.distance_to_ma_m == 0.0
    assert result.traction_permitted is False
    assert "authority_exhausted_with_movement_permission" in result.errors


@pytest.mark.parametrize("direction", [0, "neutral", 3, None, True, [], {}])
def test_neutral_or_unknown_direction_is_invalid(direction):
    result = _valid_ma(direction_code=direction)

    assert result.valid is False
    assert "invalid_direction" in result.errors


def test_effective_allowed_speed_uses_the_lower_valid_limit():
    assert effective_allowed_speed(55.0) == 55.0
    assert effective_allowed_speed(55.0, 40.0) == 40.0


@pytest.mark.parametrize("value", [-1.0, math.nan, math.inf, "40", True])
def test_effective_allowed_speed_rejects_invalid_limits(value):
    with pytest.raises(ValueError):
        effective_allowed_speed(value)


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("timeout_sec", -1.0),
        ("consistency_tolerance_m", -1.0),
        ("future_tolerance_sec", -1.0),
        ("now", math.nan),
    ],
)
def test_invalid_validator_configuration_raises_value_error(parameter, value):
    with pytest.raises(ValueError):
        _valid_ma(**{parameter: value})
