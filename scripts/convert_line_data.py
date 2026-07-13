"""Convert the teacher-provided line Excel workbook into frontend/backend seed JSON.

Outputs:
  - frontend/public/data/line-layout.json

The JSON keeps the legacy frontend fields (`blocks`, `signals`, `turnouts`,
`graph`, etc.) and additionally embeds backend-oriented `track_info` and
`yard_layout` payloads so the same converted data can seed dashboard/station
yard views without hand-written mock geometry.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import deque
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ModuleNotFoundError as exc:  # pragma: no cover - exercised by CLI users
    raise SystemExit(
        "Missing dependency: pandas. Install converter dependencies with "
        "`python -m pip install pandas xlrd`."
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_XLS_PATH = ROOT / "backend" / "线路数据(1).xls"
DEFAULT_OUT_PATH = ROOT / "frontend" / "public" / "data" / "line-layout.json"
LINE_ID = "LINE-1"
INVALID_ID = 65535

SHEET_SEG = "Seg表"
SHEET_PLATFORM = "站台表"
SHEET_STATION = "车站表"
SHEET_BLOCK = "逻辑区段表"
SHEET_SIGNAL = "信号机表"
SHEET_TURNOUT = "道岔表"
SHEET_SLOPE = "坡度表"
SHEET_POINT = "点表"
SHEET_AXLE_SECTION = "计轴区段表"
SHEET_PHYSICAL_SECTION = "物理区段表"
SHEET_AXLE_COUNTER = "计轴器表"
SHEET_PLATFORM_SCREEN_DOOR = "屏蔽门表"
SHEET_EMERGENCY_BUTTON = "紧急按钮表"
SHEET_BALISE = "应答器表"
SHEET_STATIC_SPEED_LIMIT = "静态限速表"
SHEET_ROUTE = "进路表"
SHEET_PROTECTION_SECTION = "保护区段表"
SHEET_POINT_APPROACH_SECTION = "点式接近区段表"
SHEET_CBTC_APPROACH_SECTION = "CBTC接近区段表"
SHEET_POINT_TRIGGER_SECTION = "点式触发区段表"
SHEET_CBTC_TRIGGER_SECTION = "CBTC触发区段表"
SHEET_AREA_ATTRIBUTE = "区域属性表"
SHEET_UNIFIED_SPEED_LIMIT = "线路统一限速信息表"
SHEET_UNIFIED_GRADIENT = "线路统一坡度信息表"
SHEET_FLOOD_GATE = "防淹门表"
SHEET_TUNNEL = "隧道表"
SHEET_STOP_BLOCK = "车档表"
SHEET_DEVICE_MAPPING = "设备编号映射表"
SHEET_VIRTUAL_POINT = "虚拟点表"
SHEET_SPKS = "SPKS开关表"
SHEET_GARAGE_DOOR = "车库门表"
SHEET_COLLISION_ZONE = "碰撞区域表"


def clean_key(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or str(value).strip() == ""


def read_sheet(xls_path: Path, name: str) -> "pd.DataFrame":
    df = pd.read_excel(xls_path, sheet_name=name, header=None)
    if len(df.index) < 5:
        raise ValueError(f"Sheet {name!r} does not contain expected header/data rows")
    header = [clean_key(item) or f"col{i}" for i, item in enumerate(df.iloc[3].tolist())]
    data = df.iloc[4:].copy()
    data.columns = header
    data = data.dropna(how="all")
    return data


def unique_headers(headers: list[Any]) -> list[str]:
    seen: dict[str, int] = {}
    result = []
    for index, header in enumerate(headers):
        key = clean_key(header) or f"col{index}"
        if key in seen:
            seen[key] += 1
            key = f"{key}_{seen[key]}"
        else:
            seen[key] = 0
        result.append(key)
    return result


def json_value(value: Any) -> Any:
    if is_blank(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return round(value, 6)
    return value


def read_sheet_records(xls_path: Path, name: str) -> dict:
    df = pd.read_excel(xls_path, sheet_name=name, header=None)
    if len(df.index) < 4:
        return {"sheet_name": name, "row_count": 0, "columns": [], "records": []}

    headers = unique_headers(df.iloc[3].tolist())
    data = df.iloc[4:].copy()
    data.columns = headers
    data = data.dropna(how="all")

    records = []
    for _, row in data.iterrows():
        record = {}
        for key in headers:
            value = json_value(row.get(key))
            if value is not None:
                record[key] = value
        if record:
            records.append(record)

    used_columns = [key for key in headers if any(key in record for record in records)]
    return {
        "sheet_name": name,
        "row_count": len(records),
        "columns": used_columns,
        "records": records,
    }


def read_workbook_tables(xls_path: Path) -> dict:
    excel = pd.ExcelFile(xls_path)
    tables = {}
    for sheet_name in excel.sheet_names:
        tables[sheet_name] = read_sheet_records(xls_path, sheet_name)
    return tables


def require(row: "pd.Series", key: str, sheet: str) -> Any:
    if key not in row.index:
        raise KeyError(f"Missing required column {key!r} in {sheet}")
    value = row[key]
    if is_blank(value):
        raise ValueError(f"Blank required value {key!r} in {sheet}")
    return value


def to_int(value: Any, default: int | None = None) -> int | None:
    if is_blank(value):
        return default
    return int(float(value))


def to_float(value: Any, default: float | None = None) -> float | None:
    if is_blank(value):
        return default
    return float(value)


def safe_name(value: Any) -> str:
    text = clean_key(value)
    if text.endswith(".0"):
        text = text[:-2]
    return text


def normalize_id(value: Any) -> int | str | None:
    if is_blank(value):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = float(text)
            if number.is_integer():
                value = int(number)
            else:
                return text
        except ValueError:
            return text
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if value.is_integer():
            value = int(value)
    if value == INVALID_ID:
        return None
    return value


def collect_numbered_values(row: "pd.Series", prefix: str, suffix: str) -> list:
    values = []
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)\s*{re.escape(suffix)}$")
    matched: list[tuple[int, Any]] = []
    for column in row.index:
        text = clean_key(column)
        match = pattern.match(text)
        if match:
            matched.append((int(match.group(1)), row.get(column)))
    for _, value in sorted(matched, key=lambda item: item[0]):
        normalized = normalize_id(value)
        if normalized is not None:
            values.append(normalized)
    return values


def collect_columns_containing(row: "pd.Series", includes: tuple[str, ...]) -> list:
    values = []
    for column in row.index:
        text = clean_key(column)
        if all(item in text for item in includes):
            normalized = normalize_id(row.get(column))
            if normalized is not None:
                values.append(normalized)
    return values


def parse_km(value: Any) -> float | None:
    """Parse K12+345.6 or centimeter-like numeric values to meters."""

    if is_blank(value):
        return None
    text = str(value).strip().upper().replace("K", "")
    match = re.match(r"^(\d+)\+(\d+(?:\.\d+)?)$", text)
    if match:
        return round(float(match.group(1)) * 1000 + float(match.group(2)), 1)
    try:
        # Source numeric mileage is stored in centimeters.
        return round(float(text) / 100, 1)
    except ValueError:
        return None


def normalize_track_type(raw: str | None) -> str:
    text = clean_key(raw).lower()
    if any(item in text for item in ("main", "正线", "上行", "下行")):
        return "main"
    if any(item in text for item in ("侧", "到发", "arrival", "departure")):
        return "arrival_departure"
    if any(item in text for item in ("折返", "存车", "siding", "牵出")):
        return "siding"
    return "unknown"


def direction_for_seg(seg_id: int) -> str:
    return "down" if seg_id % 2 == 0 else "up"


def build_seg_topology(xls_path: Path) -> tuple[dict[int, dict], dict]:
    seg_df = read_sheet(xls_path, SHEET_SEG)
    segs: dict[int, dict] = {}

    for _, row in seg_df.iterrows():
        if is_blank(row.get("索引编号")):
            continue
        sid = int(require(row, "索引编号", SHEET_SEG))
        length_cm = float(require(row, "长度（cm)", SHEET_SEG))
        segs[sid] = {
            "seg_id": sid,
            "length_m": round(length_cm / 100, 1),
            "start_type": int(require(row, "起点端点类型", SHEET_SEG)),
            "start_id": int(require(row, "起点端点编号", SHEET_SEG)),
            "end_type": int(require(row, "终点端点类型", SHEET_SEG)),
            "end_id": int(require(row, "终点端点编号", SHEET_SEG)),
            "end_fwd": int(require(row, "终点正向相邻点SegID", SHEET_SEG)),
            "end_lat": int(require(row, "终点侧向相邻点SegID", SHEET_SEG)),
        }

    if not segs:
        raise ValueError("No Seg records were converted")
    return segs, layout_graph(segs)


def layout_graph(segs: dict[int, dict]) -> dict:
    """Lay out every segment, including disconnected/branch-only components."""

    scale = 0.035  # px / m
    branch_dy = 85
    component_gap_y = 190
    base_y = 280

    edges: list[dict] = []
    nodes: dict[str, dict] = {}
    visited: set[int] = set()
    component_index = 0

    def add_node(key: str, x: float, y: float) -> None:
        nodes.setdefault(key, {"id": key, "x": round(x, 1), "y": round(y, 1), "kind": "junction"})

    def seed_queue(start_seg_id: int, component: int) -> deque:
        return deque([(start_seg_id, 0.0, base_y + component * component_gap_y, 0, "main")])

    remaining = sorted(segs)
    while len(visited) < len(segs):
        start_seg_id = next((seg_id for seg_id in remaining if seg_id not in visited), None)
        if start_seg_id is None:
            break
        queue = seed_queue(start_seg_id, component_index)
        component_index += 1

        while queue:
            seg_id, x, y, level, branch = queue.popleft()
            if seg_id in visited or seg_id not in segs:
                continue
            visited.add(seg_id)

            seg = segs[seg_id]
            length_px = max(12.0, seg["length_m"] * scale)
            x2 = x + length_px

            edges.append(
                {
                    "seg_id": seg_id,
                    "x1": round(x, 1),
                    "y1": round(y, 1),
                    "x2": round(x2, 1),
                    "y2": round(y, 1),
                    "length_m": seg["length_m"],
                    "branch": branch,
                    "component": component_index,
                }
            )

            start_key = f"{seg['start_type']}-{seg['start_id']}"
            end_key = f"{seg['end_type']}-{seg['end_id']}"
            add_node(start_key, x, y)
            add_node(end_key, x2, y)

            if seg["end_fwd"] != INVALID_ID and seg["end_fwd"] not in visited:
                queue.append((seg["end_fwd"], x2, y, level, "main"))
            if seg["end_lat"] != INVALID_ID and seg["end_lat"] not in visited:
                dy = y - branch_dy if level % 2 == 0 else y + branch_dy
                queue.append((seg["end_lat"], x2, dy, level + 1, "branch"))

    max_x = max((edge["x2"] for edge in edges), default=800)
    max_y = max((edge["y1"] for edge in edges), default=base_y)
    min_y = min((edge["y1"] for edge in edges), default=base_y)
    return {
        "edges": sorted(edges, key=lambda item: item["seg_id"]),
        "nodes": list(nodes.values()),
        "width": round(max_x + 120, 1),
        "height": round(max_y - min_y + 160, 1),
        "placed_seg_count": len(edges),
        "total_seg_count": len(segs),
        "component_count": component_index,
    }


def build_seg_linear_map(segs_topo: dict[int, dict]) -> dict[int, dict]:
    """Build a deterministic segment-offset to line-meter mapping.

    The source workbook stores many records as (SegID + offset cm). There is no
    dedicated absolute-meter field on those rows, so this keeps the historic
    deterministic SegID-order mapping while exposing the original SegID too.
    """

    cumulative_cm = 0.0
    linear: dict[int, dict] = {}
    for sid in sorted(segs_topo):
        length_cm = segs_topo[sid]["length_m"] * 100
        linear[sid] = {
            "seg_id": sid,
            "length_m": segs_topo[sid]["length_m"],
            "start_m": round(cumulative_cm / 100, 1),
            "end_m": round((cumulative_cm + length_cm) / 100, 1),
        }
        cumulative_cm += length_cm
    return linear


def seg_offset_to_m(segs: dict[int, dict], seg_id: Any, offset_cm: Any) -> float:
    sid = int(float(seg_id))
    offset_m = float(offset_cm) / 100
    base = segs.get(sid, {}).get("start_m", 0.0)
    return round(base + offset_m, 1)


def read_platforms(xls_path: Path) -> list[dict]:
    plat_df = read_sheet(xls_path, SHEET_PLATFORM)
    platforms = []
    for _, row in plat_df.iterrows():
        if is_blank(row.get("站台ID")):
            continue
        position = parse_km(row.get("站台中心公里标"))
        if position is None:
            continue
        platform_id = int(row["站台ID"])
        seg_id = to_int(row.get("关联seg编号"))
        platforms.append(
            {
                "platform_id": platform_id,
                "position_m": position,
                "seg_id": seg_id,
            }
        )
    return sorted(platforms, key=lambda item: (item["position_m"], item["platform_id"]))


def read_stations(xls_path: Path, platforms: list[dict]) -> list[dict]:
    st_df = read_sheet(xls_path, SHEET_STATION)
    stations = []
    platform_by_id = {item["platform_id"]: item for item in platforms}
    for _, row in st_df.iterrows():
        if is_blank(row.get("车站ID")):
            continue
        station_num = int(row["车站ID"])
        platform_ids = []
        for col in row.index:
            if "站台编号" in str(col):
                platform_id = to_int(row.get(col))
                if platform_id is not None and platform_id != INVALID_ID:
                    platform_ids.append(platform_id)

        matched = [platform_by_id[item] for item in platform_ids if item in platform_by_id]
        if not matched:
            continue
        station_id = f"ST-{station_num:02d}"
        stations.append(
            {
                "station_id": station_id,
                "station_name": safe_name(row.get("车站名称")),
                "name": safe_name(row.get("车站名称")),
                "position": min(item["position_m"] for item in matched),
                "seg_id": matched[0].get("seg_id"),
                "platform_ids": platform_ids,
            }
        )
    return sorted(stations, key=lambda item: item["position"])


def nearest_station_id(position_m: float | None, stations: list[dict], max_distance_m: float = 850.0) -> str | None:
    if position_m is None or not stations:
        return None
    nearest = min(stations, key=lambda station: abs(float(station["position"]) - position_m))
    if abs(float(nearest["position"]) - position_m) <= max_distance_m:
        return nearest["station_id"]
    return None


def build_blocks(xls_path: Path, segs: dict[int, dict], stations: list[dict]) -> list[dict]:
    logic_df = read_sheet(xls_path, SHEET_BLOCK)
    blocks = []
    for _, row in logic_df.iterrows():
        if is_blank(row.get("索引编号")):
            continue
        start_seg = int(require(row, "起点所处Seg编号", SHEET_BLOCK))
        end_seg = int(require(row, "终点所处Seg编号", SHEET_BLOCK))
        start = seg_offset_to_m(segs, start_seg, require(row, "起点所处Seg偏移量", SHEET_BLOCK))
        end = seg_offset_to_m(segs, end_seg, require(row, "终点所处Seg偏移量", SHEET_BLOCK))
        if end < start:
            start, end = end, start
        station_id = nearest_station_id((start + end) / 2, stations)
        blocks.append(
            {
                "section_id": safe_name(row["名称"]),
                "segment_id": safe_name(row["名称"]),
                "line_id": LINE_ID,
                "track_seg_id": str(start_seg),
                "track_id": f"SEG-{start_seg}",
                "start": start,
                "end": end,
                "length_m": round(end - start, 1),
                "station_id": station_id,
                "occupied": False,
                "aspect": "green",
                "condition": "normal",
            }
        )
    return sorted(blocks, key=lambda item: (item["start"], item["end"], item["section_id"]))


def build_signals(xls_path: Path, segs: dict[int, dict], stations: list[dict]) -> list[dict]:
    sig_df = read_sheet(xls_path, SHEET_SIGNAL)
    signals = []
    for _, row in sig_df.iterrows():
        if is_blank(row.get("索引编号")):
            continue
        seg_id = int(require(row, "所处Seg编号", SHEET_SIGNAL))
        position = seg_offset_to_m(segs, seg_id, require(row, "所处Seg偏移量（cm）", SHEET_SIGNAL))
        station_id = nearest_station_id(position, stations)
        signal_type = to_int(row.get("类型"), 0)
        signals.append(
            {
                "signal_id": safe_name(row["名称"]),
                "position": position,
                "signal_type": str(signal_type),
                "station_id": station_id,
                "track_id": f"SEG-{seg_id}",
                "section_id": None,
                "direction": direction_for_seg(seg_id),
                "state": "green",
                "signal_state": "green",
                "permission": "allow",
            }
        )
    return sorted(signals, key=lambda item: (item["position"], item["signal_id"]))


def build_turnouts(xls_path: Path, segs: dict[int, dict], graph: dict, stations: list[dict]) -> list[dict]:
    turn_df = read_sheet(xls_path, SHEET_TURNOUT)
    edge_by_seg = {int(edge["seg_id"]): edge for edge in graph["edges"]}
    turnouts = []
    for _, row in turn_df.iterrows():
        if is_blank(row.get("索引编号")):
            continue
        merge_seg = to_int(row.get("汇合SegID"))
        normal_seg = to_int(row.get("定位SegID"))
        reverse_seg = to_int(row.get("反位SegID"))
        position = segs.get(merge_seg, {}).get("start_m", 0.0) if merge_seg else 0.0
        station_id = nearest_station_id(position, stations, max_distance_m=1200.0)
        turnout_id = safe_name(row["名称"])
        turnout = {
            "turnout_id": turnout_id,
            "switch_id": f"SW-{turnout_id}",
            "position": position,
            "position_m": position,
            "merge_seg_id": merge_seg,
            "normal_seg": normal_seg,
            "reverse_seg": reverse_seg,
            "station_id": station_id,
            "switch_type": "single",
            "connects": [f"SEG-{item}" for item in (merge_seg, normal_seg, reverse_seg) if item is not None],
            "normal_to": f"SEG-{normal_seg}" if normal_seg is not None else None,
            "reverse_to": f"SEG-{reverse_seg}" if reverse_seg is not None else None,
            "state": "normal",
            "routing": "normal",
            "locked": False,
            "related_section": f"SEG-{merge_seg}" if merge_seg is not None else None,
        }
        edge = edge_by_seg.get(merge_seg)
        if edge:
            turnout["graph_x"] = edge["x2"]
            turnout["graph_y"] = edge["y2"]
        else:
            # Fallback keeps every turnout drawable even when the graph component
            # could not place the merge segment exactly.
            turnout["graph_x"] = round(position * 0.035, 1)
            turnout["graph_y"] = 280
            turnout["graph_fallback"] = True
        turnouts.append(turnout)
    return sorted(turnouts, key=lambda item: (item["position"], item["turnout_id"]))


def attach_station_graph_positions(stations: list[dict], graph: dict) -> None:
    edge_by_seg = {int(edge["seg_id"]): edge for edge in graph["edges"]}
    for station in stations:
        edge = edge_by_seg.get(station.get("seg_id"))
        if edge:
            station["graph_x"] = round((edge["x1"] + edge["x2"]) / 2, 1)
            station["graph_y"] = edge["y1"] - 28
        else:
            station["graph_x"] = round(float(station["position"]) * 0.035, 1)
            station["graph_y"] = 252
            station["graph_fallback"] = True


def build_slope_profile(xls_path: Path, segs: dict[int, dict]) -> list[dict]:
    slope_df = read_sheet(xls_path, SHEET_SLOPE)
    profile = []
    for _, row in slope_df.iterrows():
        if is_blank(row.get("索引编号")):
            continue
        profile.append(
            {
                "position": seg_offset_to_m(
                    segs,
                    require(row, "坡度起点所处seg编号", SHEET_SLOPE),
                    require(row, "坡度起点所处seg偏移量", SHEET_SLOPE),
                ),
                "slope": float(row["坡度值"]) if not is_blank(row.get("坡度值")) else 0.0,
            }
        )
    return sorted(profile, key=lambda item: item["position"])


def build_points(xls_path: Path) -> list[dict]:
    df = read_sheet(xls_path, SHEET_POINT)
    points = []
    for _, row in df.iterrows():
        point_id = normalize_id(row.get("索引编号"))
        if point_id is None:
            continue
        km_cm = to_float(row.get("公里标（cm)"), 0.0)
        points.append(
            {
                "point_id": point_id,
                "name": safe_name(row.get("名称")),
                "track_name": safe_name(row.get("起点轨道名称")),
                "position_m": round((km_cm or 0.0) / 100, 1),
                "point_type": normalize_id(row.get("点类型")),
                "start_forward_point_id": normalize_id(row.get("起点正向相邻点ID")),
                "start_lateral_point_id": normalize_id(row.get("起点侧向相邻点ID")),
                "end_forward_point_id": normalize_id(row.get("终点正向相邻点ID")),
                "end_lateral_point_id": normalize_id(row.get("终点侧向相邻点ID")),
                "zc_area_id": normalize_id(row.get("所属ZC区域编号")),
                "ats_area_id": normalize_id(row.get("所属ATS区域编号")),
                "ci_area_id": normalize_id(row.get("所属CI区域编号")),
                "direction": normalize_id(row.get("上下行")),
                "siding_description": safe_name(row.get("侧线描述")),
            }
        )
    return points


def build_axle_sections(xls_path: Path) -> list[dict]:
    df = read_sheet(xls_path, SHEET_AXLE_SECTION)
    sections = []
    for _, row in df.iterrows():
        section_id = normalize_id(row.get("索引编号"))
        if section_id is None:
            continue
        sections.append(
            {
                "axle_section_id": section_id,
                "name": safe_name(row.get("名称")),
                "seg_ids": collect_numbered_values(row, "seg", "编号"),
                "ci": normalize_id(row.get("CI")),
                "spks_switch_ids": collect_numbered_values(row, "所属SPKS开关ID", ""),
                "raw_seg_count": normalize_id(row.get("包含Seg数目")),
            }
        )
    return sections


def build_physical_sections(xls_path: Path) -> list[dict]:
    df = read_sheet(xls_path, SHEET_PHYSICAL_SECTION)
    sections = []
    for _, row in df.iterrows():
        section_id = normalize_id(row.get("索引编号"))
        if section_id is None:
            continue
        sections.append(
            {
                "physical_section_id": section_id,
                "name": safe_name(row.get("名称")),
                "axle_section_ids": collect_numbered_values(row, "计轴区段", "编号"),
                "raw_axle_section_count": normalize_id(row.get("包含计轴区段数目")),
            }
        )
    return sections


def build_axle_counters(xls_path: Path) -> list[dict]:
    df = read_sheet(xls_path, SHEET_AXLE_COUNTER)
    counters = []
    for _, row in df.iterrows():
        counter_id = normalize_id(row.get("索引编号"))
        if counter_id is None:
            continue
        km_cm = to_float(row.get("所处公里标（cm）"), 0.0)
        counters.append(
            {
                "axle_counter_id": counter_id,
                "name": safe_name(row.get("计轴器名称")),
                "position_m": round((km_cm or 0.0) / 100, 1),
            }
        )
    return counters


def build_platform_devices(xls_path: Path, sheet: str, device_key: str) -> list[dict]:
    df = read_sheet(xls_path, sheet)
    devices = []
    for _, row in df.iterrows():
        device_id = normalize_id(row.get("索引编号"))
        if device_id is None:
            continue
        devices.append(
            {
                f"{device_key}_id": device_id,
                "name": safe_name(row.get("名称")),
                "platform_id": normalize_id(row.get("所属站台编号")),
                "interop_id": normalize_id(row.get("互联互通编号")),
                "ci": normalize_id(row.get("CI")),
            }
        )
    return devices


def build_balises(xls_path: Path, segs: dict[int, dict]) -> list[dict]:
    df = read_sheet(xls_path, SHEET_BALISE)
    balises = []
    for _, row in df.iterrows():
        balise_index = normalize_id(row.get("索引编号"))
        if balise_index is None:
            continue
        seg_id = normalize_id(row.get("所处seg编号"))
        position_m = seg_offset_to_m(segs, seg_id, row.get("所处Seg偏移量（cm）")) if seg_id is not None else None
        balises.append(
            {
                "balise_index": balise_index,
                "balise_id": normalize_id(row.get("ID")),
                "name": safe_name(row.get("名称")),
                "seg_id": seg_id,
                "offset_cm": normalize_id(row.get("所处Seg偏移量（cm）")),
                "position_m": position_m,
                "interop_id": normalize_id(row.get("互联互通编号")),
                "attribute": normalize_id(row.get("应答器属性")),
                "related_signal_id": normalize_id(row.get("关联信号机编号")),
                "direction": normalize_id(row.get("应答器作用方向")),
            }
        )
    return balises


def build_static_speed_limits(xls_path: Path, segs: dict[int, dict]) -> list[dict]:
    df = read_sheet(xls_path, SHEET_STATIC_SPEED_LIMIT)
    limits = []
    for _, row in df.iterrows():
        limit_id = normalize_id(row.get("索引编号"))
        if limit_id is None:
            continue
        seg_id = normalize_id(row.get("限速区段所处seg编号"))
        start = seg_offset_to_m(segs, seg_id, row.get("起点所处seg偏移量")) if seg_id is not None else None
        end = seg_offset_to_m(segs, seg_id, row.get("终点所处seg偏移量")) if seg_id is not None else None
        if start is not None and end is not None and end < start:
            start, end = end, start
        limits.append(
            {
                "speed_limit_id": limit_id,
                "seg_id": seg_id,
                "start_m": start,
                "end_m": end,
                "related_switch_id": normalize_id(row.get("关联道岔编号")),
                "speed_limit": to_float(row.get("限速值"), 0.0),
            }
        )
    return limits


def build_unified_speed_limits(xls_path: Path) -> list[dict]:
    df = read_sheet(xls_path, SHEET_UNIFIED_SPEED_LIMIT)
    return [
        {
            "speed_limit_id": normalize_id(row.get("索引编号")),
            "speed_limit": to_float(row.get("限速值"), 0.0),
        }
        for _, row in df.iterrows()
        if normalize_id(row.get("索引编号")) is not None
    ]


def build_unified_gradients(xls_path: Path) -> list[dict]:
    df = read_sheet(xls_path, SHEET_UNIFIED_GRADIENT)
    return [
        {
            "gradient_id": normalize_id(row.get("索引编号")),
            "gradient": to_float(row.get("坡度值"), 0.0),
        }
        for _, row in df.iterrows()
        if normalize_id(row.get("索引编号")) is not None
    ]


def build_routes(xls_path: Path) -> list[dict]:
    df = read_sheet(xls_path, SHEET_ROUTE)
    routes = []
    for _, row in df.iterrows():
        route_id = normalize_id(row.get("索引编号"))
        if route_id is None:
            continue
        routes.append(
            {
                "route_id": route_id,
                "route_name": safe_name(row.get("进路名称")),
                "route_type": normalize_id(row.get("进路性质")),
                "start_signal_id": normalize_id(row.get("始端信号机编号")),
                "end_signal_id": normalize_id(row.get("终端信号机编号")),
                "axle_section_ids": collect_numbered_values(row, "计轴区段", "编号"),
                "protection_section_ids": collect_numbered_values(row, "保护区段", "编号"),
                "point_approach_section_ids": collect_numbered_values(row, "点式接近区段", "编号"),
                "cbtc_approach_section_ids": collect_numbered_values(row, "CBTC接近区段", "编号"),
                "point_trigger_section_ids": collect_numbered_values(row, "点式触发区段", "ID"),
                "cbtc_trigger_section_ids": collect_numbered_values(row, "CBTC触发区段", "ID"),
                "ci_area_id": normalize_id(row.get("所属CI区域编号")),
                "direction": normalize_id(row.get("进路方向")),
            }
        )
    return routes


def build_protection_sections(xls_path: Path) -> list[dict]:
    df = read_sheet(xls_path, SHEET_PROTECTION_SECTION)
    sections = []
    for _, row in df.iterrows():
        section_id = normalize_id(row.get("索引编号"))
        if section_id is None:
            continue
        sections.append(
            {
                "protection_section_id": section_id,
                "axle_section_ids": collect_numbered_values(row, "包含的计轴区段", "编号"),
                "raw_axle_section_count": normalize_id(row.get("包含的计轴区段数目")),
            }
        )
    return sections


def build_approach_sections(xls_path: Path) -> dict:
    point_df = read_sheet(xls_path, SHEET_POINT_APPROACH_SECTION)
    cbtc_df = read_sheet(xls_path, SHEET_CBTC_APPROACH_SECTION)

    point_sections = []
    for _, row in point_df.iterrows():
        section_id = normalize_id(row.get("索引编号"))
        if section_id is None:
            continue
        point_sections.append(
            {
                "approach_section_id": section_id,
                "mode": "point",
                "axle_section_ids": collect_numbered_values(row, "计轴区段", "编号"),
                "raw_section_count": normalize_id(row.get("包含计轴区段数目")),
            }
        )

    cbtc_sections = []
    for _, row in cbtc_df.iterrows():
        section_id = normalize_id(row.get("索引编号"))
        if section_id is None:
            continue
        cbtc_sections.append(
            {
                "approach_section_id": section_id,
                "mode": "cbtc",
                "logical_section_ids": collect_numbered_values(row, "逻辑区段", "编号"),
                "raw_section_count": normalize_id(row.get("包含逻辑区段数目")),
            }
        )

    return {"point": point_sections, "cbtc": cbtc_sections}


def build_trigger_sections(xls_path: Path) -> dict:
    point_df = read_sheet(xls_path, SHEET_POINT_TRIGGER_SECTION)
    cbtc_df = read_sheet(xls_path, SHEET_CBTC_TRIGGER_SECTION)

    point_sections = []
    for _, row in point_df.iterrows():
        section_id = normalize_id(row.get("ID"))
        if section_id is None:
            continue
        point_sections.append(
            {
                "trigger_section_id": section_id,
                "mode": "point",
                "axle_section_ids": collect_numbered_values(row, "计轴区段", "ID"),
                "raw_section_count": normalize_id(row.get("计轴区段数量")),
            }
        )

    cbtc_sections = []
    for _, row in cbtc_df.iterrows():
        section_id = normalize_id(row.get("ID"))
        if section_id is None:
            continue
        cbtc_sections.append(
            {
                "trigger_section_id": section_id,
                "mode": "cbtc",
                "logical_section_ids": collect_numbered_values(row, "逻辑区段", "ID"),
                "raw_section_count": normalize_id(row.get("逻辑区段数量")),
            }
        )

    return {"point": point_sections, "cbtc": cbtc_sections}


def build_area_attributes(xls_path: Path) -> list[dict]:
    df = read_sheet(xls_path, SHEET_AREA_ATTRIBUTE)
    areas = []
    for _, row in df.iterrows():
        area_index = normalize_id(row.get("索引编号"))
        if area_index is None:
            continue
        areas.append(
            {
                "area_index": area_index,
                "area_type": normalize_id(row.get("区域类型")),
                "area_id": normalize_id(row.get("区域ID")),
                "area_attribute": normalize_id(row.get("区域属性")),
                "map_checksum": normalize_id(row.get("管辖区电子地图数据校验信息")),
            }
        )
    return areas


def build_segment_position_devices(
    xls_path: Path,
    segs: dict[int, dict],
    sheet: str,
    id_key: str,
    seg_column: str,
    offset_column: str,
    extra_builder,
) -> list[dict]:
    df = read_sheet(xls_path, sheet)
    devices = []
    for _, row in df.iterrows():
        device_id = normalize_id(row.get("索引编号"))
        if device_id is None:
            continue
        seg_id = normalize_id(row.get(seg_column))
        position_m = seg_offset_to_m(segs, seg_id, row.get(offset_column)) if seg_id is not None else None
        payload = {
            id_key: device_id,
            "seg_id": seg_id,
            "offset_cm": normalize_id(row.get(offset_column)),
            "position_m": position_m,
        }
        payload.update(extra_builder(row))
        devices.append(payload)
    return devices


def build_safety_devices(xls_path: Path, segs: dict[int, dict]) -> dict:
    flood_gates = build_segment_position_devices(
        xls_path,
        segs,
        SHEET_FLOOD_GATE,
        "flood_gate_id",
        "所处Seg编号",
        "所处Seg偏移量",
        lambda row: {
            "adjacent_gate_id": normalize_id(row.get("相邻防护门编号")),
            "protect_signal_ids": collect_numbered_values(row, "防护信号机ID", ""),
            "protect_axle_section_ids": collect_numbered_values(row, "防护区域计轴区段ID", ""),
            "interop_id": normalize_id(row.get("互联互通编号")),
            "protect_area_length": to_float(row.get("防护区域长度"), 0.0),
            "ci": normalize_id(row.get("所属CI")),
        },
    )

    spks_switches = build_segment_position_devices(
        xls_path,
        segs,
        SHEET_SPKS,
        "spks_switch_id",
        "所处Seg编号",
        "所处Seg偏移量",
        lambda row: {
            "area_description": safe_name(row.get("区域描述")),
            "interop_id": normalize_id(row.get("互联互通编号")),
            "ci": normalize_id(row.get("CI")),
        },
    )

    stop_blocks = build_segment_position_devices(
        xls_path,
        segs,
        SHEET_STOP_BLOCK,
        "stop_block_id",
        "所属Seg编号",
        "所属Seg偏移量",
        lambda row: {
            "stop_block_type": normalize_id(row.get("车档类型\n（1:可碰撞车档\n2：不可碰撞车档）")),
            "interop_id": normalize_id(row.get("互联互通编号")),
        },
    )

    garage_doors = build_segment_position_devices(
        xls_path,
        segs,
        SHEET_GARAGE_DOOR,
        "garage_door_id",
        "所处Seg编号",
        "所处Seg偏移量",
        lambda row: {
            "protection_length": to_float(row.get("车库门防护区段长度"), 0.0),
            "door_attribute": normalize_id(row.get("车库门属性\n1:库线\n2：洗车库")),
            "in_route_ids": collect_numbered_values(row, "入库进路", "编号"),
            "out_route_ids": collect_numbered_values(row, "出库进路", "编号"),
            "spks_switch_ids": collect_numbered_values(row, "SPKS开关", "编号"),
            "protect_signal_ids": collect_numbered_values(row, "防护信号机", "编号"),
            "protect_axle_section_ids": collect_numbered_values(row, "对应防护计轴区段", "ID"),
            "interop_id": normalize_id(row.get("互联互通编号")),
            "ci": normalize_id(row.get("CI")),
        },
    )

    return {
        "platform_screen_doors": build_platform_devices(xls_path, SHEET_PLATFORM_SCREEN_DOOR, "screen_door"),
        "emergency_buttons": build_platform_devices(xls_path, SHEET_EMERGENCY_BUTTON, "emergency_button"),
        "flood_gates": flood_gates,
        "spks_switches": spks_switches,
        "stop_blocks": stop_blocks,
        "garage_doors": garage_doors,
    }


def build_tunnels(xls_path: Path, segs: dict[int, dict]) -> list[dict]:
    df = read_sheet(xls_path, SHEET_TUNNEL)
    tunnels = []
    for _, row in df.iterrows():
        tunnel_id = normalize_id(row.get("索引编号"))
        if tunnel_id is None:
            continue
        seg_id = normalize_id(row.get("隧道所处Seg编号"))
        start_m = seg_offset_to_m(segs, seg_id, row.get("起点所处Seg偏移量")) if seg_id is not None else None
        end_m = seg_offset_to_m(segs, seg_id, row.get("终点所处Seg偏移量")) if seg_id is not None else None
        tunnels.append(
            {
                "tunnel_id": tunnel_id,
                "seg_id": seg_id,
                "start_m": start_m,
                "end_m": end_m,
                "length_m": to_float(row.get("隧道长度"), 0.0),
            }
        )
    return tunnels


def build_device_mappings(xls_path: Path) -> list[dict]:
    df = read_sheet(xls_path, SHEET_DEVICE_MAPPING)
    mappings = []
    for _, row in df.iterrows():
        mapping_id = normalize_id(row.get("索引编号"))
        if mapping_id is None:
            continue
        mappings.append(
            {
                "mapping_id": mapping_id,
                "area_type": normalize_id(row.get("区域类型")),
                "area_id": normalize_id(row.get("区域ID")),
                "interop_id": normalize_id(row.get("对应互联互通ID")),
            }
        )
    return mappings


def build_collision_zones(xls_path: Path) -> list[dict]:
    df = read_sheet(xls_path, SHEET_COLLISION_ZONE)
    zones = []
    for _, row in df.iterrows():
        zone_id = normalize_id(row.get("索引编号"))
        if zone_id is None:
            continue
        zones.append(
            {
                "collision_zone_id": zone_id,
                "point_type": normalize_id(row.get("点类型\n（1:车档为碰撞点\n2：列检库车辆碰撞点）")),
                "stop_block_id": normalize_id(row.get("车档编号")),
                "speed_limit_cmps": to_float(row.get("碰撞点限速(cm/s)"), 0.0),
                "logical_section_ids": collect_numbered_values(row, "逻辑区段ID", ""),
                "raw_logical_section_count": normalize_id(row.get("逻辑区段数量")),
            }
        )
    return zones


def nearest_block(position: float, blocks: list[dict]) -> dict | None:
    if not blocks:
        return None
    for block in blocks:
        if block["start"] <= position <= block["end"]:
            return block
    return min(blocks, key=lambda block: min(abs(position - block["start"]), abs(position - block["end"])))


def enrich_signals_with_sections(signals: list[dict], blocks: list[dict]) -> None:
    for signal in signals:
        block = nearest_block(signal["position"], blocks)
        if block:
            signal["section_id"] = block["section_id"]
            signal["protects_section_id"] = block["section_id"]


def enrich_blocks_with_slopes_and_platforms(blocks: list[dict], slope_profile: list[dict], platforms: list[dict]) -> None:
    slopes = sorted(slope_profile, key=lambda item: item["position"])
    for block in blocks:
        block_slopes = [
            item["slope"]
            for item in slopes
            if block["start"] <= float(item["position"]) <= block["end"]
        ]
        if block_slopes:
            block["gradient"] = block_slopes[0]
        else:
            previous = [item["slope"] for item in slopes if float(item["position"]) <= block["start"]]
            block["gradient"] = previous[-1] if previous else 0.0

        platform_positions = [
            item["position_m"]
            for item in platforms
            if block["start"] <= float(item["position_m"]) <= block["end"]
        ]
        if platform_positions:
            block["stop_position"] = round(sum(platform_positions) / len(platform_positions), 1)


def build_track_info(blocks: list[dict]) -> dict:
    return {
        "line_id": LINE_ID,
        "sections": [
            {
                "section_id": block["section_id"],
                "line_id": LINE_ID,
                "track_seg_id": block["track_seg_id"],
                "track_id": block["track_id"],
                "start": block["start"],
                "end": block["end"],
                "length_m": block["length_m"],
                "gradient": block.get("gradient", 0.0),
                "speed_limit": block.get("speed_limit", 60.0),
                "station_id": block.get("station_id"),
                "stop_position": block.get("stop_position"),
            }
            for block in blocks
        ],
    }


def build_signal_state(blocks: list[dict], signals: list[dict], turnouts: list[dict]) -> dict:
    return {
        "system_mode": "normal",
        "sections": [
            {
                "section_id": block["section_id"],
                "line_id": LINE_ID,
                "track_seg_id": block["track_seg_id"],
                "track_id": block["track_id"],
                "start": block["start"],
                "end": block["end"],
                "station_id": block.get("station_id"),
                "occupied": False,
                "vehicle_id": None,
                "occupied_by": None,
                "aspect": "green",
                "locked": False,
                "locked_by_route_id": None,
                "condition": "normal",
            }
            for block in blocks
        ],
        "signals": [
            {
                "signal_id": signal["signal_id"],
                "position": signal["position"],
                "state": signal.get("state", "green"),
                "station_id": signal.get("station_id"),
                "track_id": signal.get("track_id"),
                "section_id": signal.get("section_id"),
                "direction": signal.get("direction"),
                "signal_type": signal.get("signal_type"),
                "protects_section_id": signal.get("protects_section_id"),
                "signal_state": signal.get("signal_state", "green"),
                "permission": signal.get("permission", "allow"),
            }
            for signal in signals
        ],
        "switches": [
            {
                "switch_id": turnout["switch_id"],
                "turnout_id": turnout["turnout_id"],
                "station_id": turnout.get("station_id"),
                "switch_type": turnout.get("switch_type", "single"),
                "connects": turnout.get("connects", []),
                "normal_to": turnout.get("normal_to"),
                "reverse_to": turnout.get("reverse_to"),
                "position": "normal",
                "routing": turnout.get("routing", "normal"),
                "state": turnout.get("state", "normal"),
                "locked": False,
                "locked_by_route_id": None,
                "related_section": turnout.get("related_section"),
                "reason": None,
            }
            for turnout in turnouts
        ],
        "route_results": [],
    }


def geometry_from_edge(edge: dict | None, fallback_x: float, fallback_y: float) -> dict:
    if edge:
        return {"type": "polyline", "points": [[edge["x1"], edge["y1"]], [edge["x2"], edge["y2"]]]}
    return {"type": "point", "x": round(fallback_x, 1), "y": round(fallback_y, 1)}


def build_yard_layout(
    stations: list[dict],
    blocks: list[dict],
    signals: list[dict],
    turnouts: list[dict],
    graph: dict,
) -> dict:
    edge_by_seg = {int(edge["seg_id"]): edge for edge in graph["edges"]}
    station_payloads = []
    yard_tracks = []
    yard_switches = []
    yard_signals = []
    yard_sections = []

    for station in stations:
        station_id = station["station_id"]
        station_blocks = [block for block in blocks if block.get("station_id") == station_id]
        station_signals = [signal for signal in signals if signal.get("station_id") == station_id]
        station_turnouts = [turnout for turnout in turnouts if turnout.get("station_id") == station_id]

        if not station_blocks and not station_signals and not station_turnouts:
            continue

        tracks_by_id: dict[str, dict] = {}
        for block in station_blocks:
            track_id = block.get("track_id") or f"SEG-{block['track_seg_id']}"
            edge = edge_by_seg.get(int(block["track_seg_id"])) if str(block["track_seg_id"]).isdigit() else None
            tracks_by_id.setdefault(
                track_id,
                {
                    "track_id": track_id,
                    "track_name": track_id,
                    "station_id": station_id,
                    "track_type": normalize_track_type(track_id),
                    "direction": direction_for_seg(int(block["track_seg_id"])) if str(block["track_seg_id"]).isdigit() else None,
                    "section_ids": [],
                    "geometry": geometry_from_edge(edge, station.get("graph_x", 0.0), station.get("graph_y", 0.0)),
                },
            )
            tracks_by_id[track_id]["section_ids"].append(block["section_id"])

            yard_sections.append(
                {
                    "section_id": block["section_id"],
                    "station_id": station_id,
                    "track_id": track_id,
                    "start": block["start"],
                    "end": block["end"],
                    "geometry": geometry_from_edge(edge, station.get("graph_x", 0.0), station.get("graph_y", 0.0)),
                }
            )

        station_tracks = list(tracks_by_id.values())
        yard_tracks.extend(station_tracks)

        station_switches = []
        for turnout in station_turnouts:
            switch_payload = {
                "switch_id": turnout["switch_id"],
                "station_id": station_id,
                "switch_type": turnout.get("switch_type", "single"),
                "connects": turnout.get("connects", []),
                "normal_to": turnout.get("normal_to"),
                "reverse_to": turnout.get("reverse_to"),
                "geometry": {
                    "type": "point",
                    "x": turnout.get("graph_x"),
                    "y": turnout.get("graph_y"),
                },
            }
            station_switches.append(switch_payload)
            yard_switches.append(switch_payload)

        station_signal_payloads = []
        for signal in station_signals:
            signal_payload = {
                "signal_id": signal["signal_id"],
                "station_id": station_id,
                "track_id": signal.get("track_id"),
                "direction": signal.get("direction"),
                "protects_switch_id": nearest_switch_id(signal, station_turnouts),
                "protects_section_id": signal.get("protects_section_id") or signal.get("section_id"),
                "geometry": signal_geometry(signal, edge_by_seg),
            }
            station_signal_payloads.append(signal_payload)
            yard_signals.append(signal_payload)

        station_payloads.append(
            {
                "station_id": station_id,
                "station_name": station.get("station_name") or station.get("name") or station_id,
                "track_ids": [track["track_id"] for track in station_tracks],
                "switch_ids": [switch["switch_id"] for switch in station_switches],
                "signal_ids": [signal["signal_id"] for signal in station_signal_payloads],
                "section_ids": [section["section_id"] for section in yard_sections if section["station_id"] == station_id],
                "tracks": station_tracks,
                "switches": station_switches,
                "signals": station_signal_payloads,
                "sections": [section for section in yard_sections if section["station_id"] == station_id],
            }
        )

    return {
        "line_id": LINE_ID,
        "stations": station_payloads,
        "yard_tracks": yard_tracks,
        "yard_switches": yard_switches,
        "yard_signals": yard_signals,
        "yard_sections": yard_sections,
        "updated_at": time.time(),
    }


def signal_geometry(signal: dict, edge_by_seg: dict[int, dict]) -> dict:
    track_id = clean_key(signal.get("track_id")).replace("SEG-", "")
    seg_id = int(track_id) if track_id.isdigit() else None
    edge = edge_by_seg.get(seg_id) if seg_id is not None else None
    if edge:
        return {
            "type": "point",
            "x": round((edge["x1"] + edge["x2"]) / 2, 1),
            "y": round(edge["y1"] - 18, 1),
        }
    return {"type": "point", "x": round(float(signal.get("position", 0.0)) * 0.035, 1), "y": 262}


def nearest_switch_id(signal: dict, turnouts: list[dict]) -> str | None:
    if not turnouts:
        return None
    position = float(signal.get("position", 0.0))
    nearest = min(turnouts, key=lambda turnout: abs(float(turnout.get("position", 0.0)) - position))
    if abs(float(nearest.get("position", 0.0)) - position) <= 1000.0:
        return nearest.get("switch_id")
    return None


def validate_payload(payload: dict) -> None:
    required_top = {
        "source",
        "total_length_m",
        "seg_count",
        "graph",
        "stations",
        "platforms",
        "blocks",
        "signals",
        "turnouts",
        "slope_profile",
        "track_info",
        "signal_state",
        "yard_layout",
        "workbook_tables",
        "points",
        "axle_sections",
        "physical_sections",
        "axle_counters",
        "routes",
        "protection_sections",
        "approach_sections",
        "trigger_sections",
        "balises",
        "speed_limits",
        "area_attributes",
        "safety_devices",
        "tunnels",
        "device_mappings",
        "collision_zones",
    }
    missing = required_top - set(payload)
    if missing:
        raise ValueError(f"Converted payload missing top-level keys: {sorted(missing)}")

    graph = payload["graph"]
    if graph["placed_seg_count"] != graph["total_seg_count"]:
        raise ValueError(
            f"Graph placement incomplete: {graph['placed_seg_count']}/{graph['total_seg_count']}"
        )

    checks = [
        ("stations", ["station_id", "name", "position", "seg_id"]),
        ("platforms", ["platform_id", "position_m", "seg_id"]),
        ("blocks", ["section_id", "segment_id", "track_seg_id", "start", "end", "length_m"]),
        ("signals", ["signal_id", "position", "signal_type", "state", "signal_state"]),
        ("turnouts", ["turnout_id", "switch_id", "position", "merge_seg_id", "normal_seg", "reverse_seg", "graph_x", "graph_y"]),
    ]
    for collection, fields in checks:
        for index, item in enumerate(payload[collection]):
            missing_fields = [field for field in fields if field not in item or item[field] is None]
            if missing_fields:
                raise ValueError(f"{collection}[{index}] missing fields: {missing_fields}; item={item}")

    for block in payload["blocks"]:
        if float(block["end"]) < float(block["start"]):
            raise ValueError(f"Block end < start: {block}")
        if float(block["length_m"]) < 0:
            raise ValueError(f"Block length is negative: {block}")

    track_sections = payload["track_info"].get("sections", [])
    if len(track_sections) != len(payload["blocks"]):
        raise ValueError("track_info.sections count must match blocks count")

    signal_state = payload["signal_state"]
    if len(signal_state.get("sections", [])) != len(payload["blocks"]):
        raise ValueError("signal_state.sections count must match blocks count")
    if len(signal_state.get("signals", [])) != len(payload["signals"]):
        raise ValueError("signal_state.signals count must match signals count")
    if len(signal_state.get("switches", [])) != len(payload["turnouts"]):
        raise ValueError("signal_state.switches count must match turnouts count")

    yard = payload["yard_layout"]
    if not yard.get("stations") or not yard.get("yard_sections"):
        raise ValueError("yard_layout must contain station and section geometry")

    workbook_tables = payload["workbook_tables"]
    if len(workbook_tables) != 33:
        raise ValueError(f"Expected 33 workbook sheets, got {len(workbook_tables)}")
    for sheet_name, table in workbook_tables.items():
        if "row_count" not in table or "records" not in table or "columns" not in table:
            raise ValueError(f"Workbook table {sheet_name!r} is missing structured metadata")

    expected_counts = {
        "points": 297,
        "axle_sections": 259,
        "physical_sections": 199,
        "axle_counters": 243,
        "routes": 249,
        "protection_sections": 49,
        "balises": 374,
        "area_attributes": 12,
        "tunnels": 215,
        "device_mappings": 92,
        "collision_zones": 14,
    }
    for key, minimum in expected_counts.items():
        if len(payload.get(key, [])) != minimum:
            raise ValueError(f"{key} expected {minimum} records, got {len(payload.get(key, []))}")


def convert(xls_path: Path = DEFAULT_XLS_PATH) -> dict:
    if not xls_path.exists():
        raise FileNotFoundError(f"Source Excel not found: {xls_path}")

    segs_topo, graph = build_seg_topology(xls_path)
    segs = build_seg_linear_map(segs_topo)
    workbook_tables = read_workbook_tables(xls_path)
    platforms = read_platforms(xls_path)
    stations = read_stations(xls_path, platforms)
    attach_station_graph_positions(stations, graph)

    blocks = build_blocks(xls_path, segs, stations)
    signals = build_signals(xls_path, segs, stations)
    turnouts = build_turnouts(xls_path, segs, graph, stations)
    slope_profile = build_slope_profile(xls_path, segs)
    points = build_points(xls_path)
    axle_sections = build_axle_sections(xls_path)
    physical_sections = build_physical_sections(xls_path)
    axle_counters = build_axle_counters(xls_path)
    routes = build_routes(xls_path)
    protection_sections = build_protection_sections(xls_path)
    approach_sections = build_approach_sections(xls_path)
    trigger_sections = build_trigger_sections(xls_path)
    balises = build_balises(xls_path, segs)
    static_speed_limits = build_static_speed_limits(xls_path, segs)
    unified_speed_limits = build_unified_speed_limits(xls_path)
    unified_gradients = build_unified_gradients(xls_path)
    area_attributes = build_area_attributes(xls_path)
    safety_devices = build_safety_devices(xls_path, segs)
    tunnels = build_tunnels(xls_path, segs)
    device_mappings = build_device_mappings(xls_path)
    collision_zones = build_collision_zones(xls_path)

    enrich_signals_with_sections(signals, blocks)
    enrich_blocks_with_slopes_and_platforms(blocks, slope_profile, platforms)

    total_length = max(
        [block["end"] for block in blocks]
        + [station["position"] for station in stations]
        + [platform["position_m"] for platform in platforms]
        + [edge["length_m"] for edge in graph["edges"]]
        + [0.0]
    )

    payload = {
        "source": xls_path.relative_to(ROOT).as_posix() if xls_path.is_relative_to(ROOT) else str(xls_path),
        "line_id": LINE_ID,
        "total_length_m": round(total_length, 1),
        "seg_count": len(segs),
        "graph": graph,
        "stations": stations,
        "platforms": platforms,
        "blocks": blocks,
        "signals": signals,
        "turnouts": turnouts,
        "slope_profile": slope_profile,
        "workbook_tables": workbook_tables,
        "points": points,
        "axle_sections": axle_sections,
        "physical_sections": physical_sections,
        "axle_counters": axle_counters,
        "routes": routes,
        "protection_sections": protection_sections,
        "approach_sections": approach_sections,
        "trigger_sections": trigger_sections,
        "balises": balises,
        "speed_limits": {
            "static": static_speed_limits,
            "unified": unified_speed_limits,
        },
        "gradients": {
            "profile": slope_profile,
            "unified": unified_gradients,
        },
        "area_attributes": area_attributes,
        "safety_devices": safety_devices,
        "tunnels": tunnels,
        "device_mappings": device_mappings,
        "collision_zones": collision_zones,
    }
    payload["track_info"] = build_track_info(blocks)
    payload["signal_state"] = build_signal_state(blocks, signals, turnouts)
    payload["yard_layout"] = build_yard_layout(stations, blocks, signals, turnouts, graph)
    validate_payload(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert official line workbook to line-layout.json")
    parser.add_argument("--input", type=Path, default=DEFAULT_XLS_PATH, help="Source .xls/.xlsx workbook")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT_PATH, help="Output JSON path")
    args = parser.parse_args()

    payload = convert(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(
        "total={total}m stations={stations} platforms={platforms} blocks={blocks} "
        "signals={signals} turnouts={turnouts} graph_edges={placed}/{total_edges} "
        "yard_stations={yard_stations}".format(
            total=payload["total_length_m"],
            stations=len(payload["stations"]),
            platforms=len(payload["platforms"]),
            blocks=len(payload["blocks"]),
            signals=len(payload["signals"]),
            turnouts=len(payload["turnouts"]),
            placed=payload["graph"]["placed_seg_count"],
            total_edges=payload["graph"]["total_seg_count"],
            yard_stations=len(payload["yard_layout"]["stations"]),
        )
    )


if __name__ == "__main__":
    main()
