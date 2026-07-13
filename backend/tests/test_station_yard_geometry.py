import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from station_yard import build_station_yard_layout_v2  # noqa: E402


def test_station_yard_v2_generates_all_stations_with_finite_geometry():
    source = json.loads((ROOT / "backend" / "data" / "line-layout.json").read_text(encoding="utf-8"))

    yard = build_station_yard_layout_v2(source)

    assert yard["schema_version"] == "2.0"
    assert len(yard["stations"]) == 13
    assert yard["yard_tracks"]
    assert yard["yard_sections"]
    assert yard["yard_signals"]

    for station in yard["stations"]:
        assert station["tracks"], station["station_id"]
        assert station["platforms"], station["station_id"]
        assert station["viewBox"]["width"] > 0
        assert station["viewBox"]["height"] > 0
        for track in station["tracks"]:
            points = track["geometry"]["points"]
            assert len(points) >= 2
            assert all(math.isfinite(value) for point in points for value in point)


def test_station_yard_v2_marks_inferred_switch_geometry():
    source = json.loads((ROOT / "backend" / "data" / "line-layout.json").read_text(encoding="utf-8"))

    yard = build_station_yard_layout_v2(source)

    assert yard["geometry_policy"]["missing_source_fields"]
    for switch in yard["yard_switches"]:
        assert switch["ratio"] == 1 / 9
        assert switch["curve_radius_m"] == 200.0
        assert "switch_ratio_default_1_9" in switch["assumptions"]


def test_station_turnouts_are_uniquely_assigned_from_source_relations():
    source = json.loads((ROOT / "backend" / "data" / "line-layout.json").read_text(encoding="utf-8"))

    yard = build_station_yard_layout_v2(source)
    source_rows = source["workbook_tables"]["道岔表"]["records"]
    source_by_index = {int(row["索引编号"]): row for row in source_rows}
    rendered = yard["yard_switches"]

    assert len(source_rows) == 60
    assert len(rendered) == 42
    assert len({switch["source_index"] for switch in rendered}) == len(rendered)
    assert yard["quality_summary"]["unassigned_turnout_source_indexes"] == list(range(43, 61))

    station_switches = {
        station["station_id"]: station["switches"]
        for station in yard["stations"]
    }
    for station_id in ("ST-02", "ST-03", "ST-04", "ST-06", "ST-08", "ST-10", "ST-12"):
        assert station_switches[station_id] == []

    for station in yard["stations"]:
        track_by_id = {track["track_id"]: track for track in station["tracks"]}
        for switch in station["switches"]:
            switch_point = (switch["geometry"]["x"], switch["geometry"]["y"])
            assert len(switch["connects"]) == 3
            for track_id in switch["connects"]:
                points = track_by_id[track_id]["geometry"]["points"]
                endpoint_distance = min(
                    math.dist(switch_point, points[0]),
                    math.dist(switch_point, points[-1]),
                )
                assert endpoint_distance < 0.011, (switch["source_index"], track_id, endpoint_distance)

    for switch in rendered:
        row = source_by_index[switch["source_index"]]
        assert switch["source_direction"] == int(row["方向"])
        assert switch["normal_to"].endswith(f"SEG-{int(row['定位SegID'])}")
        assert switch["reverse_to"].endswith(f"SEG-{int(row['反位SegID'])}")
        assert any(item.endswith(f"SEG-{int(row['汇合SegID'])}") for item in switch["connects"])


def test_all_stations_expose_the_reference_schematic_contract():
    source = json.loads((ROOT / "backend" / "data" / "line-layout.json").read_text(encoding="utf-8"))

    yard = build_station_yard_layout_v2(source)
    expected_path_counts = {
        "ST-01": 6,
        "ST-02": 0,
        "ST-03": 0,
        "ST-04": 0,
        "ST-05": 2,
        "ST-06": 0,
        "ST-07": 6,
        "ST-08": 0,
        "ST-09": 6,
        "ST-10": 0,
        "ST-11": 4,
        "ST-12": 0,
        "ST-13": 3,
    }

    for station in yard["stations"]:
        schematic = station["schematic"]
        reference_paths = [
            track
            for track in schematic["tracks"]
            if track["geometry_source"] == "user-reference-schematic"
        ]
        assert schematic["viewBox"]["width"] == 1000
        assert schematic["viewBox"]["height"] == 300
        assert len(reference_paths) == expected_path_counts[station["station_id"]]
        assert len(schematic["platforms"]) == 2
        for platform in schematic["platforms"]:
            center_x = platform["geometry"]["x"] + platform["geometry"]["width"] / 2
            assert center_x == 500
