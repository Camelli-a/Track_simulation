from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.vehicle_sim.line_data_loader import build_track_map_from_line_layout, default_line_layout_path
from app.vehicle_sim.train import Train


EXPECTED_STOPS = [
    ("ST-01", 313.0),
    ("ST-02", 1660.5),
    ("ST-03", 2448.6),
    ("ST-04", 3429.3),
    ("ST-05", 5014.5),
    ("ST-06", 6339.9),
    ("ST-07", 8118.8),
    ("ST-08", 9429.2),
    ("ST-09", 10598.7),
    ("ST-10", 11997.0),
    ("ST-11", 13906.8),
    ("ST-12", 14954.0),
    ("ST-13", 16048.9),
]


def _layout_sections(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("track_info", {}).get("sections") or data.get("blocks") or []


def _key(section_id: str, start: float, end: float) -> tuple[str, float, float]:
    return (section_id, round(float(start), 3), round(float(end), 3))


def main() -> int:
    layout_path = default_line_layout_path()
    raw_sections = _layout_sections(layout_path)
    track = build_track_map_from_line_layout(layout_path)
    train = Train("TRAIN-001", "LINE-1", track, train_index=1)

    loaded_by_key = {
        _key(section.section_id, section.start, section.end): section
        for section in track.sections
    }

    print(f"line_layout={layout_path}")
    print()
    print("Stop-position candidates:")
    print(
        f"{'section_id':<12} {'station':<8} {'raw_stop':>10} "
        f"{'loaded_stop':>12} {'start':>10} {'end':>10} {'ato':>5}"
    )

    for raw in raw_sections:
        raw_stop = raw.get("stop_position")
        station = raw.get("station_id")
        loaded = loaded_by_key.get(
            _key(raw.get("section_id") or raw.get("segment_id"), raw.get("start", 0.0), raw.get("end", 0.0))
        )
        loaded_stop = getattr(loaded, "stop_position", None)
        if raw_stop is None and loaded_stop is None:
            continue
        participates = bool(getattr(loaded, "station_id", None) and loaded_stop is not None)
        print(
            f"{str(raw.get('section_id')):<12} {str(station):<8} "
            f"{str(raw_stop):>10} {str(loaded_stop):>12} "
            f"{float(raw.get('start', 0.0)):>10.1f} {float(raw.get('end', 0.0)):>10.1f} "
            f"{'yes' if participates else 'no':>5}"
        )

    print()
    print("ATO usable stop sequence:")
    active_stops = train._track_stop_positions()
    for index, stop in enumerate(active_stops, start=1):
        station = next(
            (
                section.station_id
                for section in track.sections
                if section.stop_position is not None and round(section.stop_position, 2) == round(stop, 2)
            ),
            None,
        )
        print(f"{index:02d}. {station}: {stop:.1f}m")

    print()
    missing = [
        f"{station}={stop:.1f}"
        for station, stop in EXPECTED_STOPS
        if all(round(candidate, 1) != round(stop, 1) for candidate in active_stops)
    ]
    extra = [
        stop
        for stop in active_stops
        if all(round(stop, 1) != round(expected, 1) for _, expected in EXPECTED_STOPS)
    ]
    print(f"missing_expected={missing or 'none'}")
    print(f"unexpected_active={extra or 'none'}")
    return 1 if missing or extra else 0


if __name__ == "__main__":
    raise SystemExit(main())
