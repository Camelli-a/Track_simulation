import pytest

from app.vehicle_sim.line_data_loader import build_track_map_from_line_layout
from app.vehicle_sim.models import TrackSection
from app.vehicle_sim.track_map import TrackMap
from app.vehicle_sim.train import Train


EXPECTED_STOP_SEQUENCE = [
    431.0,
    1778.52,
    2566.61,
    3547.32,
    5133.834,
    6459.274,
    8238.204,
    9547.344,
    10718.11378,
    12117.07,
    14029.28014,
    15072.91,
    16169.01966,
]


def _train_at(position_m: float) -> Train:
    train = Train(
        "TRAIN-001",
        "LINE-1",
        build_track_map_from_line_layout(),
        train_index=1,
    )
    train.state.position = position_m
    train.state.direction_code = 1
    return train


def test_line_layout_loader_exposes_st03_stop_position():
    track = build_track_map_from_line_layout()
    st03_sections = [
        section
        for section in track.sections
        if section.station_id == "ST-03" and section.stop_position is not None
    ]

    assert st03_sections
    assert st03_sections[0].stop_position == pytest.approx(2566.61)
    assert st03_sections[0].start <= 2566.61 <= st03_sections[0].end


def test_ato_usable_stop_sequence_contains_expected_stops_only():
    train = _train_at(0.0)
    stops = train._track_stop_positions()

    assert stops == pytest.approx(EXPECTED_STOP_SEQUENCE)
    assert all(round(stop, 1) != 11424.2 for stop in stops)


def test_station_none_stop_position_is_not_selected():
    track = TrackMap(
        [
            TrackSection("A", 0.0, 100.0, 0.0, 80.0, "ST-01", 50.0),
            TrackSection("BAD", 100.0, 200.0, 0.0, 80.0, None, 150.0),
            TrackSection("B", 200.0, 300.0, 0.0, 80.0, "ST-02", 250.0),
        ]
    )
    train = Train("TRAIN-001", "LINE-1", track, train_index=1)
    train.state.position = 100.0
    train.state.direction_code = 1

    assert train._resolve_stop_target_m() == pytest.approx(250.0)


def test_next_station_from_start_is_st01():
    train = _train_at(0.0)

    assert train._resolve_stop_target_m() == pytest.approx(431.0)


def test_next_station_after_st02_is_st03():
    train = _train_at(2000.0)

    assert train._resolve_stop_target_m() == pytest.approx(2566.61)


def test_spurious_11424_stop_is_not_selected_after_5751():
    train = _train_at(5751.1)

    assert train._resolve_stop_target_m() == pytest.approx(6459.274)
    assert train.next_stop_target_m == pytest.approx(6459.274)
