from app.vehicle_sim.line_data_loader import (
    build_initial_train_configs,
    build_track_map_from_line_layout,
    build_track_sections,
    load_line_layout,
)


def test_line_layout_loader_builds_real_track_sections():
    layout = load_line_layout()
    sections = build_track_sections(layout)

    assert len(sections) == len(layout["track_info"]["sections"]) == 386
    assert len(sections) > 3
    assert sections[0].section_id
    assert sections[0].start <= sections[0].end
    assert all(section.speed_limit > 0 for section in sections)


def test_line_layout_loader_exposes_stop_positions_from_platform_data():
    sections = build_track_sections(load_line_layout())
    stop_positions = [section.stop_position for section in sections if section.stop_position is not None]

    assert stop_positions
    assert all(position > 0 for position in stop_positions)


def test_line_layout_loader_normalizes_raw_gradient_tenths_permille():
    sections = build_track_sections(load_line_layout())
    section = next(item for item in sections if item.section_id == "3G-D")

    assert section.gradient == 30.0
    assert all(abs(item.gradient) <= 60.0 for item in sections)


def test_track_map_from_line_layout_uses_real_sections():
    track = build_track_map_from_line_layout()

    assert len(track.sections) == 386
    assert track.get_section(0.0).section_id


def test_initial_train_configs_are_runtime_configuration_not_line_data():
    configs = build_initial_train_configs(4, spacing_m=500.0, start_position_m=100.0)

    assert [item["vehicle_id"] for item in configs] == [
        "TRAIN-001",
        "TRAIN-002",
        "TRAIN-003",
        "TRAIN-004",
    ]
    assert [item["position_m"] for item in configs] == [100.0, 600.0, 1100.0, 1600.0]
