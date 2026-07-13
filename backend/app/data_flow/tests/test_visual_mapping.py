import logging

import pytest

from app.data_flow.visual_mapping import (
    build_visual_payload,
    find_visual_edge,
    load_visual_edges,
)
from app.vehicle_sim.models import TrainState


def _train_state(position_m: float) -> dict:
    return {
        "vehicle_id": "TRAIN-001",
        "line_id": "LINE-1",
        "position_m": position_m,
        "speed_mps": 0.0,
        "direction": 1,
    }


@pytest.mark.parametrize("position_m", [313.0, 2448.610])
def test_down_position_maps_to_visual_edge_in_viewer_range(position_m):
    payload = build_visual_payload(_train_state(position_m))

    assert payload["vehicle_id"] == "TRAIN-001"
    assert payload["track"] == 0
    assert payload["direction_name"] == "down"
    assert payload["edge_id"] is not None
    assert 1 <= payload["edge_id"] <= 48


def test_edge_offset_is_relative_to_visual_edge_start():
    position_m = 2448.610
    edge = find_visual_edge(position_m)
    payload = build_visual_payload(_train_state(position_m))

    assert edge is not None
    assert payload["edge_id"] == edge.edge_id
    assert payload["edge_offset_m"] == pytest.approx(position_m - edge.start_m)


def test_viewer_position_uses_configured_calibration_offsets():
    payload = build_visual_payload(_train_state(2448.610))

    assert payload["viewer_position_m"] == pytest.approx(2448.610 + 216.46 + 4028.28)


def test_out_of_range_position_returns_null_edge_and_logs_warning(caplog):
    caplog.set_level(logging.WARNING)

    payload = build_visual_payload(_train_state(-1.0))

    assert payload["edge_id"] is None
    assert payload["edge_offset_m"] is None
    assert "No visual edge matched position_m" in caplog.text


def test_visual_edge_file_does_not_contain_link_ids():
    edges = load_visual_edges()

    assert edges
    assert max(edge.edge_id for edge in edges) <= 48


def test_train_state_protocol_exposes_viewer_edge_not_internal_link_id():
    state = TrainState(
        vehicle_id="TRAIN-001",
        line_id="LINE-1",
        position=2448.610,
        speed_ms=0.0,
        acceleration=0.0,
        mode="manual",
        is_running=False,
        emergency_brake=False,
        edge_id=205,
        edge_offset_m=123.0,
        direction_code=1,
    )
    protocol = state.to_protocol()

    assert protocol["edge_id"] == 17
    assert protocol["edge_offset_m"] == pytest.approx(1937.42)
    assert protocol["viewer_position_m"] == pytest.approx(6693.35)
    assert state.edge_id == 205
    assert state.edge_offset_m == 123.0
