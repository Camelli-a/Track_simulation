import math

import pytest

from app.vehicle_sim.stop_targets import (
    StopTarget,
    StopTargetProvider,
    find_next_stop_target,
    normalize_direction,
)


def _target(
    target_id: str,
    position_m: float,
    *,
    line_id: str = "LINE-1",
    route_id: str = "R_MAIN",
    direction: str = "forward",
) -> StopTarget:
    return StopTarget(
        target_id=target_id,
        line_id=line_id,
        route_id=route_id,
        direction=direction,
        position_m=position_m,
    )


def test_from_legacy_dict_uses_injected_line_and_preserves_metadata():
    target = StopTarget.from_dict(
        {
            "target_id": "STOP-01",
            "route_id": "R_MAIN",
            "direction": "up",
            "position": 1_500.25,
            "window_before": 0.4,
            "window_after": 0.6,
            "approach_distance": 550.0,
            "station_id": "ST-01",
            "source": "teacher_platform_table",
            "source_index": 7,
        },
        default_line_id="LINE-1",
    )

    assert target.line_id == "LINE-1"
    assert target.direction == "forward"
    assert target.position_m == 1_500.25
    assert target.window_before_m == 0.4
    assert target.window_after_m == 0.6
    assert target.approach_distance_m == 550.0
    assert target.metadata["source_index"] == 7
    assert target.to_dict()["position_m"] == 1_500.25
    assert "position" not in target.to_dict()


@pytest.mark.parametrize("alias", [1, "1", "forward", "up", "0x55", 0x55])
def test_forward_direction_aliases(alias):
    assert normalize_direction(alias) == "forward"


@pytest.mark.parametrize("alias", [-1, 2, "2", "reverse", "down", "0xaa", 0xAA])
def test_reverse_direction_aliases(alias):
    assert normalize_direction(alias) == "reverse"


def test_invalid_target_configuration_is_rejected():
    base = {
        "target_id": "STOP-01",
        "line_id": "LINE-1",
        "route_id": "R_MAIN",
        "direction": "forward",
        "position_m": 100.0,
    }

    with pytest.raises(ValueError, match="line_id"):
        StopTarget.from_dict({key: value for key, value in base.items() if key != "line_id"})
    with pytest.raises(ValueError, match="position_m"):
        StopTarget.from_dict({**base, "position_m": -1.0})
    with pytest.raises(ValueError, match="position_m"):
        StopTarget.from_dict({**base, "position_m": math.nan})
    with pytest.raises(ValueError, match="direction"):
        StopTarget.from_dict({**base, "direction": "neutral"})
    with pytest.raises(ValueError, match="conflicting"):
        StopTarget.from_dict({**base, "position": 101.0})


def test_forward_query_filters_line_route_and_direction_and_returns_nearest():
    provider = StopTargetProvider(
        [
            _target("PAST", 90.0),
            _target("NEXT", 120.0),
            _target("LATER", 200.0),
            _target("OTHER-LINE", 105.0, line_id="LINE-2"),
            _target("OTHER-ROUTE", 106.0, route_id="R_BRANCH"),
            _target("OTHER-DIRECTION", 107.0, direction="reverse"),
        ]
    )

    target = provider.find_next(
        line_id="LINE-1",
        route_id="R_MAIN",
        direction="forward",
        position_m=100.0,
    )

    assert target is not None
    assert target.target_id == "NEXT"
    assert target.signed_distance_m(100.0) == 20.0


def test_reverse_query_uses_decreasing_absolute_mileage():
    provider = StopTargetProvider(
        [
            _target("PASSED", 220.0, direction="reverse"),
            _target("NEXT", 180.0, direction="reverse"),
            _target("LATER", 100.0, direction="reverse"),
        ]
    )

    ordered = provider.targets_for(line_id="LINE-1", route_id="R_MAIN", direction="down")
    target = provider.find_next(
        line_id="LINE-1",
        route_id="R_MAIN",
        direction=2,
        position_m=200.0,
    )

    assert [item.target_id for item in ordered] == ["PASSED", "NEXT", "LATER"]
    assert target is not None
    assert target.target_id == "NEXT"
    assert target.signed_distance_m(200.0) == 20.0
    assert target.signed_distance_m(170.0) == -10.0


def test_target_at_current_position_can_be_included_or_excluded():
    provider = StopTargetProvider([_target("HERE", 100.0), _target("NEXT", 200.0)])

    included = provider.find_next(
        line_id="LINE-1",
        route_id="R_MAIN",
        direction="forward",
        position_m=100.0,
    )
    excluded = provider.find_next(
        line_id="LINE-1",
        route_id="R_MAIN",
        direction="forward",
        position_m=100.0,
        include_current=False,
    )

    assert included.target_id == "HERE"
    assert excluded.target_id == "NEXT"


def test_missing_runtime_context_or_no_matching_target_returns_none():
    provider = StopTargetProvider([_target("STOP-01", 100.0)])

    assert provider.find_next(
        line_id=None,
        route_id="R_MAIN",
        direction="forward",
        position_m=0.0,
    ) is None
    assert provider.find_next(
        line_id="LINE-1",
        route_id=None,
        direction="forward",
        position_m=0.0,
    ) is None
    assert provider.find_next(
        line_id="LINE-1",
        route_id="R_MAIN",
        direction=None,
        position_m=0.0,
    ) is None
    assert provider.find_next(
        line_id="LINE-1",
        route_id="R_MAIN",
        direction="forward",
        position_m=None,
    ) is None
    assert provider.find_next(
        line_id="LINE-1",
        route_id="NO-SUCH-ROUTE",
        direction="forward",
        position_m=0.0,
    ) is None


def test_completed_target_exclusion_allows_explicit_switch_at_same_position():
    provider = StopTargetProvider([_target("CURRENT", 100.0), _target("NEXT", 200.0)])

    target = provider.find_next(
        line_id="LINE-1",
        route_id="R_MAIN",
        direction="forward",
        position_m=100.0,
        exclude_target_ids={"CURRENT"},
    )

    assert target is not None
    assert target.target_id == "NEXT"


def test_resolve_keeps_overshot_target_until_completion_then_switches():
    provider = StopTargetProvider([_target("CURRENT", 100.0), _target("NEXT", 200.0)])

    retained = provider.resolve_target(
        line_id="LINE-1",
        route_id="R_MAIN",
        direction="forward",
        position_m=101.0,
        current_target_id="CURRENT",
    )
    switched = provider.resolve_target(
        line_id="LINE-1",
        route_id="R_MAIN",
        direction="forward",
        position_m=101.0,
        current_target_id="CURRENT",
        completed_target_ids={"CURRENT"},
    )

    assert retained is not None
    assert retained.target_id == "CURRENT"
    assert retained.signed_distance_m(101.0) == -1.0
    assert switched is not None
    assert switched.target_id == "NEXT"


def test_resolve_does_not_retain_target_after_route_or_direction_change():
    provider = StopTargetProvider(
        [
            _target("OLD", 100.0),
            _target("NEW-ROUTE", 150.0, route_id="R_BRANCH"),
            _target("NEW-DIRECTION", 80.0, direction="reverse"),
        ]
    )

    route_target = provider.resolve_target(
        line_id="LINE-1",
        route_id="R_BRANCH",
        direction="forward",
        position_m=90.0,
        current_target_id="OLD",
    )
    direction_target = provider.resolve_target(
        line_id="LINE-1",
        route_id="R_MAIN",
        direction="reverse",
        position_m=90.0,
        current_target_id="OLD",
    )

    assert route_target is not None
    assert route_target.target_id == "NEW-ROUTE"
    assert direction_target is not None
    assert direction_target.target_id == "NEW-DIRECTION"


def test_from_dicts_and_pure_lookup_do_not_require_signal_service_imports():
    provider = StopTargetProvider.from_dicts(
        [
            {
                "target_id": "STOP-01",
                "route_id": "R_MAIN",
                "direction": "up",
                "position": 100.0,
            }
        ],
        default_line_id="LINE-1",
    )

    result = find_next_stop_target(
        provider.targets,
        line_id="LINE-1",
        route_id="R_MAIN",
        direction="forward",
        position_m=0.0,
    )

    assert result is not None
    assert result.target_id == "STOP-01"


def test_duplicate_target_ids_are_rejected_for_unambiguous_switching():
    with pytest.raises(ValueError, match="duplicate stop target id"):
        StopTargetProvider([_target("DUPLICATE", 100.0), _target("DUPLICATE", 200.0)])
