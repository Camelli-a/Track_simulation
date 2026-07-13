import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException


router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_LINE_LAYOUT_PATH = PROJECT_ROOT / "backend" / "data" / "line-layout.json"
BACKEND_STATION_YARD_V2_PATH = PROJECT_ROOT / "backend" / "data" / "station-yard-v2.json"
FRONTEND_LINE_LAYOUT_PATH = PROJECT_ROOT / "frontend" / "public" / "data" / "line-layout.json"
LINE_LAYOUT_PATHS = (BACKEND_LINE_LAYOUT_PATH, FRONTEND_LINE_LAYOUT_PATH)

REQUIRED_LINE_LAYOUT_COLLECTIONS = {
    "graph",
    "stations",
    "platforms",
    "blocks",
    "signals",
    "turnouts",
    "points",
    "axle_sections",
    "physical_sections",
    "routes",
    "protection_sections",
    "approach_sections",
    "trigger_sections",
    "balises",
    "speed_limits",
    "gradients",
    "area_attributes",
    "safety_devices",
    "tunnels",
    "device_mappings",
    "collision_zones",
    "track_info",
    "signal_state",
}
REQUIRED_STATION_YARD_SHEETS = {
    "点表",
    "Seg表",
    "计轴区段表",
    "物理区段表",
    "逻辑区段表",
    "道岔表",
    "信号机表",
    "车站表",
    "站台表",
    "应答器表",
    "静态限速表",
    "进路表",
    "保护区段表",
    "点式接近区段表",
    "CBTC接近区段表",
    "点式触发区段表",
    "CBTC触发区段表",
    "区域属性表",
    "隧道表",
    "车档表",
    "设备编号映射表",
    "虚拟点表",
    "SPKS开关表",
    "碰撞区域表",
}


@router.get("/stations/yards/v2", response_model=None, summary="Get high-fidelity station yard geometry")
def get_station_yards_v2() -> dict[str, Any]:
    payload = load_station_yard_v2()
    if payload is None:
        raise HTTPException(status_code=503, detail="station_yard_v2_unavailable")
    return payload


@router.get("/line-layout", response_model=None, summary="Get complete normalized line layout")
def get_line_layout() -> dict[str, Any]:
    payload = load_static_line_layout()
    if payload is None:
        raise HTTPException(status_code=503, detail="complete_line_layout_unavailable")
    return payload


@lru_cache(maxsize=1)
def load_static_line_layout() -> dict[str, Any] | None:
    for path in LINE_LAYOUT_PATHS:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            continue
        if is_complete_line_layout(payload):
            return payload
    return None


def is_complete_line_layout(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if not REQUIRED_LINE_LAYOUT_COLLECTIONS.issubset(payload):
        return False

    workbook_tables = payload.get("workbook_tables")
    if not isinstance(workbook_tables, dict):
        return False
    if not REQUIRED_STATION_YARD_SHEETS.issubset(workbook_tables):
        return False
    for table in workbook_tables.values():
        if not isinstance(table, dict):
            return False
        records = table.get("records")
        if not isinstance(records, list) or table.get("row_count") != len(records):
            return False

    yard_layout = payload.get("yard_layout")
    if not isinstance(yard_layout, dict):
        return False
    required_yard_collections = ("stations", "yard_tracks", "yard_sections", "yard_signals", "yard_switches")
    if any(not isinstance(yard_layout.get(key), list) for key in required_yard_collections):
        return False
    if len(yard_layout["stations"]) != len(payload["stations"]):
        return False
    return bool(yard_layout["stations"] and yard_layout["yard_sections"])


@lru_cache(maxsize=1)
def load_station_yard_v2() -> dict[str, Any] | None:
    if not BACKEND_STATION_YARD_V2_PATH.exists():
        return None
    try:
        with BACKEND_STATION_YARD_V2_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("schema_version") != "2.0":
        return None
    if len(payload.get("stations", [])) != 13:
        return None
    if not payload.get("yard_tracks") or not payload.get("yard_sections"):
        return None
    return payload
