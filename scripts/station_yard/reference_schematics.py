from __future__ import annotations

from typing import Any


CANVAS_WIDTH = 1000.0
CANVAS_HEIGHT = 300.0
LEFT_X = 60.0
RIGHT_X = 940.0
TOP_Y = 100.0
BOTTOM_Y = 200.0


STATION_TEMPLATES: dict[str, dict[str, Any]] = {
    "ST-01": {
        "paths": [
            ("north-west", [[120, 38], [185, 100]]),
            ("south-west", [[120, 262], [185, 200]]),
            ("west-siding", [[78, 150], [155, 150]]),
            ("north-east", [[810, 38], [745, 100]]),
            ("south-east", [[810, 262], [745, 200]]),
            ("east-crossover", [[665, 100], [755, 150], [665, 200]]),
        ],
        "annotations": [(150, 28, "#1-#7"), (790, 28, "#8-#13")],
    },
    "ST-02": {"paths": [], "annotations": []},
    "ST-03": {"paths": [], "annotations": []},
    "ST-04": {"paths": [], "annotations": []},
    "ST-05": {
        "paths": [
            ("turnout-14", [[180, 38], [245, 100]]),
            ("turnout-15", [[180, 262], [245, 200]]),
        ],
        "annotations": [(205, 28, "#14"), (205, 278, "#15")],
    },
    "ST-06": {"paths": [], "annotations": []},
    "ST-07": {
        "paths": [
            ("north-west", [[120, 38], [185, 100]]),
            ("south-west", [[120, 262], [185, 200]]),
            ("west-crossover", [[405, 100], [345, 150], [405, 200]]),
            ("east-crossover", [[655, 100], [715, 150], [655, 200]]),
            ("north-east", [[815, 38], [750, 100]]),
            ("south-east", [[815, 262], [750, 200]]),
        ],
        "annotations": [
            (155, 28, "#16/#18"),
            (155, 278, "#21/#22"),
            (790, 28, "#17/#19"),
            (790, 278, "#20/#23"),
        ],
    },
    "ST-08": {"paths": [], "annotations": []},
    "ST-09": {
        "paths": [
            ("turnout-24", [[135, 30], [205, 100]]),
            ("turnout-31", [[135, 270], [205, 200]]),
            ("scissors-a", [[380, 100], [620, 200]]),
            ("scissors-b", [[620, 100], [380, 200]]),
            ("scissors-c", [[440, 100], [560, 200]]),
            ("scissors-d", [[560, 100], [440, 200]]),
        ],
        "annotations": [(155, 20, "#24"), (500, 28, "#25-#30"), (155, 286, "#31")],
    },
    "ST-10": {"paths": [], "annotations": []},
    "ST-11": {
        "paths": [
            ("north-west", [[125, 38], [190, 100]]),
            ("west-crossover", [[270, 100], [210, 150], [270, 200]]),
            ("south-west", [[125, 262], [190, 200]]),
            ("east-crossover", [[740, 100], [805, 140], [835, 262]]),
        ],
        "annotations": [(165, 28, "#32/#33"), (165, 278, "#35"), (825, 278, "#34/#36")],
    },
    "ST-12": {"paths": [], "annotations": []},
    "ST-13": {
        "paths": [
            ("west-combined", [[145, 38], [225, 100], [305, 150], [225, 200], [145, 262]]),
            ("turnout-41", [[815, 38], [750, 100]]),
            ("turnout-42", [[750, 200], [815, 262]]),
        ],
        "annotations": [(175, 28, "#37-#40"), (805, 28, "#41"), (805, 278, "#42")],
    },
}


def _track_lane(track: dict[str, Any] | None) -> float:
    return BOTTOM_Y if track and track.get("direction") == "up" else TOP_Y


def build_reference_schematic(station: dict[str, Any]) -> dict[str, Any]:
    station_id = str(station["station_id"])
    template = STATION_TEMPLATES[station_id]
    source_box = station["viewBox"]
    source_width = max(float(source_box["width"]), 1.0)

    def map_x(value: Any) -> float:
        ratio = (float(value) - float(source_box["minX"])) / source_width
        return round(LEFT_X + min(1.0, max(0.0, ratio)) * (RIGHT_X - LEFT_X), 3)

    source_tracks = {str(track["track_id"]): track for track in station["tracks"]}
    down_id = f"{station_id}-SCHEMATIC-DOWN"
    up_id = f"{station_id}-SCHEMATIC-UP"
    tracks = [
        {
            "track_id": down_id,
            "track_name": "DOWN-MAIN",
            "station_id": station_id,
            "track_type": "main",
            "direction": "down",
            "section_ids": [],
            "seg_id": "SCHEMATIC-DOWN",
            "geometry": {"type": "polyline", "points": [[LEFT_X, TOP_Y], [RIGHT_X, TOP_Y]]},
            "geometry_source": "reference-schematic-main-line",
            "confidence": "reference",
        },
        {
            "track_id": up_id,
            "track_name": "UP-MAIN",
            "station_id": station_id,
            "track_type": "main",
            "direction": "up",
            "section_ids": [],
            "seg_id": "SCHEMATIC-UP",
            "geometry": {"type": "polyline", "points": [[LEFT_X, BOTTOM_Y], [RIGHT_X, BOTTOM_Y]]},
            "geometry_source": "reference-schematic-main-line",
            "confidence": "reference",
        },
    ]
    tracks.extend(
        [
            {
                **tracks[0],
                "track_id": f"{station_id}-SCHEMATIC-GUIDE-DOWN",
                "track_name": "DOWN-MAIN-GUIDE",
                "seg_id": "SCHEMATIC-GUIDE-DOWN",
            },
            {
                **tracks[1],
                "track_id": f"{station_id}-SCHEMATIC-GUIDE-UP",
                "track_name": "UP-MAIN-GUIDE",
                "seg_id": "SCHEMATIC-GUIDE-UP",
            },
        ]
    )
    for path_id, points in template["paths"]:
        tracks.append(
            {
                "track_id": f"{station_id}-SCHEMATIC-{path_id.upper()}",
                "track_name": path_id,
                "station_id": station_id,
                "track_type": "siding",
                "direction": None,
                "section_ids": [],
                "seg_id": f"SCHEMATIC-{path_id}",
                "geometry": {"type": "polyline", "points": points},
                "geometry_source": "user-reference-schematic",
                "confidence": "reference",
            }
        )

    sections = []
    for section in station["sections"]:
        source_track = source_tracks.get(str(section["track_id"]))
        lane_y = _track_lane(source_track)
        source_points = section["geometry"]["points"]
        x_values = [map_x(point[0]) for point in source_points]
        start_x = min(x_values) if x_values else LEFT_X
        end_x = max(x_values) if x_values else RIGHT_X
        if end_x - start_x < 4:
            end_x = min(RIGHT_X, start_x + 4)
        sections.append(
            {
                **section,
                "source_track_id": section["track_id"],
                "track_id": up_id if lane_y == BOTTOM_Y else down_id,
                "geometry": {"type": "polyline", "points": [[start_x, lane_y], [end_x, lane_y]]},
                "geometry_source": "reference-schematic-section",
            }
        )

    signals = []
    for signal in station["signals"]:
        source_track = source_tracks.get(str(signal["track_id"]))
        lane_y = _track_lane(source_track)
        outside = -1 if lane_y == TOP_Y else 1
        x = map_x(signal["geometry"]["x"])
        signals.append(
            {
                **signal,
                "source_track_id": signal["track_id"],
                "track_id": up_id if lane_y == BOTTOM_Y else down_id,
                "geometry": {"type": "point", "x": x, "y": lane_y + outside * 18},
                "track_anchor": {"x": x, "y": lane_y},
                "geometry_source": "reference-schematic-signal",
            }
        )

    switches = []
    for switch in station["switches"]:
        normal_track = source_tracks.get(str(switch.get("normal_to")))
        lane_y = _track_lane(normal_track)
        switches.append(
            {
                **switch,
                "geometry": {
                    "type": "point",
                    "x": map_x(switch["geometry"]["x"]),
                    "y": lane_y,
                },
                "geometry_source": "reference-schematic-switch",
            }
        )

    platforms = []
    for platform in station["platforms"]:
        source_track = source_tracks.get(str(platform["track_id"]))
        lane_y = _track_lane(source_track)
        center_x = CANVAS_WIDTH / 2
        platforms.append(
            {
                **platform,
                "source_track_id": platform["track_id"],
                "track_id": up_id if lane_y == BOTTOM_Y else down_id,
                "geometry": {
                    "type": "rect",
                    "x": center_x - 70,
                    "y": lane_y - 10,
                    "width": 140,
                    "height": 8,
                },
                "geometry_source": "reference-schematic-platform",
            }
        )

    return {
        "schema_version": "1.0",
        "source": "user-provided-13-station-reference-2026-07-13",
        "station_id": station_id,
        "tracks": tracks,
        "sections": sections,
        "signals": signals,
        "switches": switches,
        "platforms": platforms,
        "annotations": [
            {"x": x, "y": y, "text": text}
            for x, y, text in template["annotations"]
        ],
        "viewBox": {
            "minX": 0.0,
            "minY": 0.0,
            "maxX": CANVAS_WIDTH,
            "maxY": CANVAS_HEIGHT,
            "width": CANVAS_WIDTH,
            "height": CANVAS_HEIGHT,
        },
    }
