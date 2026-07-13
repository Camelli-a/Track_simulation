"""Generate topology-preserving station-yard JSON and SVG assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from station_yard import build_station_yard_layout_v2, export_station_yard_assets


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "backend" / "data" / "line-layout.json"
DEFAULT_BACKEND_OUTPUT = ROOT / "backend" / "data" / "station-yard-v2.json"
DEFAULT_FRONTEND_OUTPUT = ROOT / "frontend" / "public" / "data" / "station-yard-v2.json"
DEFAULT_BACKEND_SVG_DIR = ROOT / "backend" / "data" / "station-yards"
DEFAULT_FRONTEND_SVG_DIR = ROOT / "frontend" / "public" / "data" / "station-yards"
DEFAULT_FRONTEND_LINE_LAYOUT = ROOT / "frontend" / "public" / "data" / "line-layout.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate high-fidelity station-yard geometry")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--backend-output", type=Path, default=DEFAULT_BACKEND_OUTPUT)
    parser.add_argument("--frontend-output", type=Path, default=DEFAULT_FRONTEND_OUTPUT)
    parser.add_argument("--meters-per-unit", type=float, default=0.5)
    parser.add_argument("--track-spacing-m", type=float, default=4.0)
    parser.add_argument("--vertical-exaggeration", type=float, default=5.0)
    parser.add_argument("--horizontal-compression", type=float, default=0.5)
    parser.add_argument("--update-line-layout", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    layout = json.loads(args.input.read_text(encoding="utf-8"))
    yard_layout = build_station_yard_layout_v2(
        layout,
        meters_per_unit=args.meters_per_unit,
        track_spacing_m=args.track_spacing_m,
        vertical_exaggeration=args.vertical_exaggeration,
        horizontal_compression=args.horizontal_compression,
    )
    export_station_yard_assets(
        yard_layout,
        json_paths=(args.backend_output, args.frontend_output),
        svg_directories=(DEFAULT_BACKEND_SVG_DIR, DEFAULT_FRONTEND_SVG_DIR),
    )

    if args.update_line_layout:
        layout["yard_layout"] = yard_layout
        serialized = json.dumps(layout, ensure_ascii=False, indent=2)
        for output in dict.fromkeys((args.input, DEFAULT_FRONTEND_LINE_LAYOUT)):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialized, encoding="utf-8")

    summary = yard_layout["quality_summary"]
    print(
        "Generated {stations} stations, {tracks} tracks, {switches} switches, "
        "{signals} signals; quality={quality} errors={errors} warnings={warnings}".format(
            stations=len(yard_layout["stations"]),
            tracks=len(yard_layout["yard_tracks"]),
            switches=len(yard_layout["yard_switches"]),
            signals=len(yard_layout["yard_signals"]),
            quality=summary["status"],
            errors=summary["error_count"],
            warnings=summary["warning_count"],
        )
    )


if __name__ == "__main__":
    main()
