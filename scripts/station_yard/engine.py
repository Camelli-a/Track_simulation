from __future__ import annotations

import heapq
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape

from .models import GeometryIssue, TopologyNode, TopologySegment
from .reference_schematics import build_reference_schematic


INVALID_ID = 65535
SCHEMA_VERSION = "2.0"
DEFAULT_METERS_PER_UNIT = 0.5
DEFAULT_TRACK_SPACING_M = 4.0
DEFAULT_VERTICAL_EXAGGERATION = 5.0
DEFAULT_HORIZONTAL_COMPRESSION = 0.5
DEFAULT_SWITCH_RATIO = 1 / 9
DEFAULT_CURVE_RADIUS_M = 200.0
ARC_STEP_M = 0.5


def _records(layout: dict[str, Any], sheet_name: str) -> list[dict[str, Any]]:
    table = layout.get("workbook_tables", {}).get(sheet_name, {})
    records = table.get("records", [])
    return records if isinstance(records, list) else []


def _as_int(value: Any) -> int | None:
    if value in (None, "", INVALID_ID, str(INVALID_ID)):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round(value: float) -> float:
    return round(float(value), 3)


def _endpoint_key(endpoint_type: int, source_id: int) -> str:
    return f"{endpoint_type}:{source_id}"


def _valid_track_name(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or text in {"65535", "None", "nan"}:
        return None
    return text


def _natural_key(value: str) -> tuple:
    parts: list[Any] = []
    cursor = ""
    numeric = False
    for char in value:
        if char.isdigit() != numeric and cursor:
            parts.append(int(cursor) if numeric else cursor.lower())
            cursor = ""
        cursor += char
        numeric = char.isdigit()
    if cursor:
        parts.append(int(cursor) if numeric else cursor.lower())
    return tuple(parts)


def _build_topology(layout: dict[str, Any]) -> tuple[dict[str, TopologyNode], dict[int, TopologySegment]]:
    point_by_id = {
        int(point["point_id"]): point
        for point in layout.get("points", [])
        if _as_int(point.get("point_id")) is not None
    }
    nodes: dict[str, TopologyNode] = {}
    segments: dict[int, TopologySegment] = {}

    def ensure_node(endpoint_type: int, source_id: int) -> TopologyNode:
        key = _endpoint_key(endpoint_type, source_id)
        if key in nodes:
            return nodes[key]
        point = point_by_id.get(source_id) if endpoint_type == 2 else None
        position = _as_float(point.get("position_m")) if point else None
        node = TopologyNode(
            key=key,
            endpoint_type=endpoint_type,
            source_id=source_id,
            name=str(point.get("name") or "") if point else "",
            position_m=position,
            direction=_as_int(point.get("direction")) if point else None,
            track_name=_valid_track_name(point.get("track_name")) if point else None,
            siding_description=_valid_track_name(point.get("siding_description")) if point else None,
            x_source="point_mileage" if point else "unresolved",
        )
        nodes[key] = node
        return node

    for record in _records(layout, "Seg表"):
        seg_id = _as_int(record.get("索引编号"))
        start_type = _as_int(record.get("起点端点类型"))
        start_id = _as_int(record.get("起点端点编号"))
        end_type = _as_int(record.get("终点端点类型"))
        end_id = _as_int(record.get("终点端点编号"))
        if None in {seg_id, start_type, start_id, end_type, end_id}:
            continue
        start_node = ensure_node(start_type, start_id)
        end_node = ensure_node(end_type, end_id)
        start_node.segment_ids.add(seg_id)
        end_node.segment_ids.add(seg_id)
        segments[seg_id] = TopologySegment(
            seg_id=seg_id,
            start_node=start_node.key,
            end_node=end_node.key,
            length_m=_as_float(record.get("长度（cm)")) / 100,
            start_type=start_type,
            end_type=end_type,
            forward_seg_id=_as_int(record.get("终点正向相邻点SegID")),
            lateral_seg_id=_as_int(record.get("终点侧向相邻点SegID")),
        )

    _attach_physical_track_names(layout, nodes, segments)
    _anchor_platform_segments(layout, nodes, segments)
    _solve_node_mileages(nodes, segments)
    return nodes, segments


def _attach_physical_track_names(
    layout: dict[str, Any],
    nodes: dict[str, TopologyNode],
    segments: dict[int, TopologySegment],
) -> None:
    axle_by_id = {
        _as_int(item.get("axle_section_id")): item
        for item in layout.get("axle_sections", [])
        if _as_int(item.get("axle_section_id")) is not None
    }
    names_by_seg: dict[int, list[str]] = defaultdict(list)
    for physical in layout.get("physical_sections", []):
        name = _valid_track_name(physical.get("name"))
        if not name:
            continue
        for axle_id in physical.get("axle_section_ids", []):
            axle = axle_by_id.get(_as_int(axle_id))
            if not axle:
                continue
            for seg_id in axle.get("seg_ids", []):
                normalized = _as_int(seg_id)
                if normalized is not None and name not in names_by_seg[normalized]:
                    names_by_seg[normalized].append(name)

    for segment in segments.values():
        start = nodes[segment.start_node]
        end = nodes[segment.end_node]
        point_names = [name for name in (start.track_name, end.track_name) if name]
        candidates = names_by_seg.get(segment.seg_id, []) or point_names
        segment.physical_track_name = sorted(candidates, key=_natural_key)[0] if candidates else f"SEG-{segment.seg_id}"
        directions = [value for value in (start.direction, end.direction) if value in {0, 1}]
        segment.direction = Counter(directions).most_common(1)[0][0] if directions else None


def _anchor_platform_segments(
    layout: dict[str, Any],
    nodes: dict[str, TopologyNode],
    segments: dict[int, TopologySegment],
) -> None:
    for platform in layout.get("platforms", []):
        seg_id = _as_int(platform.get("seg_id"))
        position = platform.get("position_m")
        segment = segments.get(seg_id)
        if segment is None or position is None:
            continue
        start = nodes[segment.start_node]
        end = nodes[segment.end_node]
        center = _as_float(position)
        if start.position_m is None and end.position_m is None:
            start.position_m = center - segment.length_m / 2
            end.position_m = center + segment.length_m / 2
            start.x_source = "platform_anchor"
            end.x_source = "platform_anchor"


def _solve_node_mileages(nodes: dict[str, TopologyNode], segments: dict[int, TopologySegment]) -> None:
    for _ in range(max(8, len(segments))):
        changed = False
        for segment in segments.values():
            start = nodes[segment.start_node]
            end = nodes[segment.end_node]
            if start.position_m is not None and end.position_m is None:
                end.position_m = start.position_m + segment.length_m
                end.x_source = "topology_propagated"
                changed = True
            elif end.position_m is not None and start.position_m is None:
                start.position_m = end.position_m - segment.length_m
                start.x_source = "topology_propagated"
                changed = True
        if not changed:
            break

    unresolved = {key for key, node in nodes.items() if node.position_m is None}
    component_offset = 0.0
    while unresolved:
        seed_key = sorted(unresolved)[0]
        nodes[seed_key].position_m = component_offset
        nodes[seed_key].x_source = "component_fallback"
        component_offset += 1000.0
        for _ in range(len(segments) + 1):
            changed = False
            for segment in segments.values():
                start = nodes[segment.start_node]
                end = nodes[segment.end_node]
                if start.position_m is not None and end.position_m is None:
                    end.position_m = start.position_m + segment.length_m
                    end.x_source = "component_fallback"
                    changed = True
                elif end.position_m is not None and start.position_m is None:
                    start.position_m = end.position_m - segment.length_m
                    start.x_source = "component_fallback"
                    changed = True
            if not changed:
                break
        unresolved = {key for key, node in nodes.items() if node.position_m is None}


def _segment_adjacency(segments: dict[int, TopologySegment]) -> dict[int, dict[int, float]]:
    by_node: dict[str, list[int]] = defaultdict(list)
    for segment in segments.values():
        by_node[segment.start_node].append(segment.seg_id)
        by_node[segment.end_node].append(segment.seg_id)
    adjacency: dict[int, dict[int, float]] = {seg_id: {} for seg_id in segments}
    for connected in by_node.values():
        for seg_id in connected:
            for other_id in connected:
                if seg_id == other_id:
                    continue
                cost = min(120.0, max(15.0, (segments[seg_id].length_m + segments[other_id].length_m) / 4))
                adjacency[seg_id][other_id] = min(cost, adjacency[seg_id].get(other_id, math.inf))
    for segment in segments.values():
        for other_id in (segment.forward_seg_id, segment.lateral_seg_id):
            if other_id in segments:
                cost = min(120.0, max(15.0, (segment.length_m + segments[other_id].length_m) / 4))
                adjacency[segment.seg_id][other_id] = min(cost, adjacency[segment.seg_id].get(other_id, math.inf))
                adjacency[other_id][segment.seg_id] = min(cost, adjacency[other_id].get(segment.seg_id, math.inf))
    return adjacency


def _station_seed_segments(layout: dict[str, Any], station: dict[str, Any]) -> set[int]:
    platform_ids = {_as_int(value) for value in station.get("platform_ids", [])}
    return {
        seg_id
        for platform in layout.get("platforms", [])
        if _as_int(platform.get("platform_id")) in platform_ids
        for seg_id in [_as_int(platform.get("seg_id"))]
        if seg_id is not None
    }


def _station_radius(stations: list[dict[str, Any]], index: int) -> float:
    current = _as_float(stations[index].get("position"))
    distances = []
    if index:
        distances.append(abs(current - _as_float(stations[index - 1].get("position"))))
    if index + 1 < len(stations):
        distances.append(abs(_as_float(stations[index + 1].get("position")) - current))
    nearest = min(distances) if distances else 1200.0
    return max(320.0, min(720.0, nearest * 0.42))


def _turnout_relation_key(turnout: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    return (
        _as_int(turnout.get("normal_seg") or turnout.get("定位SegID")),
        _as_int(turnout.get("reverse_seg") or turnout.get("反位SegID")),
        _as_int(turnout.get("merge_seg_id") or turnout.get("汇合SegID")),
    )


def _enrich_turnouts(layout: dict[str, Any]) -> list[dict[str, Any]]:
    source_by_relation = {
        _turnout_relation_key(record): record
        for record in _records(layout, "道岔表")
        if all(value is not None for value in _turnout_relation_key(record))
    }
    enriched = []
    for turnout in layout.get("turnouts", []):
        source = source_by_relation.get(_turnout_relation_key(turnout), {})
        source_index = _as_int(turnout.get("source_index")) or _as_int(source.get("索引编号"))
        linked_turnout_id = _as_int(turnout.get("linked_turnout_id")) or _as_int(source.get("联动道岔编号"))
        enriched.append(
            {
                **turnout,
                "source_index": source_index,
                "switch_uid": turnout.get("switch_uid") or (f"SWI-{source_index}" if source_index is not None else None),
                "source_direction": _as_int(turnout.get("source_direction")) or _as_int(source.get("方向")),
                "linked_turnout_id": None if linked_turnout_id == INVALID_ID else linked_turnout_id,
                "lateral_speed_limit_raw": _as_int(turnout.get("lateral_speed_limit_raw")) or _as_int(source.get("侧向静态限速")),
            }
        )
    return enriched


def _segment_distances(
    seeds: set[int],
    adjacency: dict[int, dict[int, float]],
    max_distance: float = math.inf,
) -> dict[int, float]:
    distances = {seg_id: 0.0 for seg_id in seeds if seg_id in adjacency}
    queue = [(0.0, seg_id) for seg_id in distances]
    heapq.heapify(queue)
    while queue:
        distance, seg_id = heapq.heappop(queue)
        if distance != distances.get(seg_id) or distance > max_distance:
            continue
        for other_id, cost in adjacency.get(seg_id, {}).items():
            next_distance = distance + cost
            if next_distance <= max_distance and next_distance < distances.get(other_id, math.inf):
                distances[other_id] = next_distance
                heapq.heappush(queue, (next_distance, other_id))
    return distances


def _collect_station_segments(
    station: dict[str, Any],
    radius_m: float,
    seeds: set[int],
    segments: dict[int, TopologySegment],
    nodes: dict[str, TopologyNode],
    adjacency: dict[int, dict[int, float]],
    turnouts: list[dict[str, Any]],
) -> set[int]:
    distances = _segment_distances(seeds, adjacency, radius_m)

    station_position = _as_float(station.get("position"))
    hard_window_m = max(600.0, radius_m * 1.65)
    included = {
        seg_id
        for seg_id in distances
        if seg_id in seeds or abs(_segment_midpoint_m(segments[seg_id], nodes) - station_position) <= hard_window_m
    }
    for _ in range(3):
        changed = False
        for turnout in turnouts:
            connected = {
                value
                for value in (
                    _as_int(turnout.get("merge_seg_id")),
                    _as_int(turnout.get("normal_seg")),
                    _as_int(turnout.get("reverse_seg")),
                )
                if value in segments
            }
            if not connected or not (connected & included):
                continue
            near_station = any(
                abs(_segment_midpoint_m(segments[seg_id], nodes) - station_position) <= hard_window_m
                for seg_id in connected
            )
            if near_station and not connected.issubset(included):
                included.update(connected)
                changed = True
        if not changed:
            break
    return included


def _segment_midpoint_m(segment: TopologySegment, nodes: dict[str, TopologyNode]) -> float:
    if not nodes:
        return 0.0
    start = nodes[segment.start_node].position_m or 0.0
    end = nodes[segment.end_node].position_m or start
    return (start + end) / 2


def _track_key(segment: TopologySegment) -> str:
    return segment.physical_track_name or f"SEG-{segment.seg_id}"


def _assign_track_lanes(
    included: set[int],
    seeds: set[int],
    segments: dict[int, TopologySegment],
    spacing_units: float,
) -> tuple[dict[str, float], dict[str, int | None]]:
    grouped: dict[str, list[TopologySegment]] = defaultdict(list)
    for seg_id in included:
        grouped[_track_key(segments[seg_id])].append(segments[seg_id])

    group_direction: dict[str, int | None] = {}
    group_length: dict[str, float] = {}
    group_seed: dict[str, bool] = {}
    for name, items in grouped.items():
        directions = [item.direction for item in items if item.direction in {0, 1}]
        group_direction[name] = Counter(directions).most_common(1)[0][0] if directions else None
        group_length[name] = sum(item.length_m for item in items)
        group_seed[name] = any(item.seg_id in seeds for item in items)

    lanes: dict[str, float] = {}
    for direction, base, sign in ((0, 0.0, -1), (1, spacing_units, 1)):
        names = [name for name in grouped if group_direction[name] == direction]
        names.sort(key=lambda name: (not group_seed[name], -group_length[name], _natural_key(name)))
        for index, name in enumerate(names):
            lanes[name] = base + sign * index * spacing_units

    unknown = sorted((name for name in grouped if name not in lanes), key=_natural_key)
    for index, name in enumerate(unknown):
        layer = index // 2 + 1
        lanes[name] = -layer * spacing_units if index % 2 == 0 else (layer + 1) * spacing_units
    return lanes, group_direction


def _turnout_node_key(turnout: dict[str, Any], segments: dict[int, TopologySegment]) -> str | None:
    segment_ids = [
        value
        for value in (
            _as_int(turnout.get("merge_seg_id")),
            _as_int(turnout.get("normal_seg")),
            _as_int(turnout.get("reverse_seg")),
        )
        if value in segments
    ]
    endpoint_counts: Counter[str] = Counter()
    endpoint_sets = []
    for seg_id in segment_ids:
        endpoint_set = {segments[seg_id].start_node, segments[seg_id].end_node}
        endpoint_sets.append(endpoint_set)
        endpoint_counts.update(endpoint_set)
    if endpoint_sets:
        shared = set.intersection(*endpoint_sets)
        if shared:
            return sorted(shared)[0]
    if endpoint_counts:
        key, count = endpoint_counts.most_common(1)[0]
        return key if count >= 2 else None
    return None


def _arc_interpolate(
    start: tuple[float, float],
    end: tuple[float, float],
    radius_units: float,
    clockwise: bool,
    step_units: float,
) -> list[list[float]]:
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    chord = math.hypot(dx, dy)
    if chord < 1e-9:
        return [[_round(x1), _round(y1)]]
    radius = max(radius_units, chord / 2 + 1e-6)
    midpoint_x = (x1 + x2) / 2
    midpoint_y = (y1 + y2) / 2
    height = math.sqrt(max(0.0, radius * radius - (chord / 2) ** 2))
    perpendicular_x = -dy / chord
    perpendicular_y = dx / chord
    centers = [
        (midpoint_x + height * perpendicular_x, midpoint_y + height * perpendicular_y),
        (midpoint_x - height * perpendicular_x, midpoint_y - height * perpendicular_y),
    ]

    candidates = []
    for center_x, center_y in centers:
        start_angle = math.atan2(y1 - center_y, x1 - center_x)
        end_angle = math.atan2(y2 - center_y, x2 - center_x)
        delta = end_angle - start_angle
        if clockwise:
            while delta >= 0:
                delta -= math.tau
        else:
            while delta <= 0:
                delta += math.tau
        candidates.append((abs(delta), center_x, center_y, start_angle, delta))
    _, center_x, center_y, start_angle, delta = min(candidates, key=lambda item: item[0])
    samples = max(8, int(math.ceil(abs(delta) * radius / max(step_units, 0.25))))
    return [
        [
            _round(center_x + radius * math.cos(start_angle + delta * index / samples)),
            _round(center_y + radius * math.sin(start_angle + delta * index / samples)),
        ]
        for index in range(samples + 1)
    ]


def _smooth_transition(start: tuple[float, float], end: tuple[float, float], samples: int = 16) -> list[list[float]]:
    x1, y1 = start
    x2, y2 = end
    result = []
    for index in range(samples + 1):
        ratio = index / samples
        eased = ratio * ratio * (3 - 2 * ratio)
        result.append([_round(x1 + (x2 - x1) * ratio), _round(y1 + (y2 - y1) * eased)])
    return result


def _append_path(target: list[list[float]], path: list[list[float]]) -> None:
    for point in path:
        if not target or math.dist(target[-1], point) > 1e-6:
            target.append(point)


def _lane_constrained_path(
    start: tuple[float, float],
    end: tuple[float, float],
    lane_y: float,
    *,
    use_circular_arc: bool,
    meters_per_unit: float,
    vertical_exaggeration: float,
) -> list[list[float]]:
    x1, y1 = start
    x2, y2 = end
    span = abs(x2 - x1)
    if span < 1e-6:
        return _smooth_transition(start, end)
    direction = 1 if x2 >= x1 else -1
    start_delta = abs(y1 - lane_y)
    end_delta = abs(y2 - lane_y)
    start_physical_delta = start_delta / max(vertical_exaggeration, 1e-6)
    end_physical_delta = end_delta / max(vertical_exaggeration, 1e-6)
    start_transition = min(span * 0.4, max(24.0, start_physical_delta / DEFAULT_SWITCH_RATIO)) if start_delta > 1e-6 else 0.0
    end_transition = min(span * 0.4, max(24.0, end_physical_delta / DEFAULT_SWITCH_RATIO)) if end_delta > 1e-6 else 0.0
    if start_transition + end_transition > span * 0.82:
        scale = span * 0.82 / max(start_transition + end_transition, 1e-6)
        start_transition *= scale
        end_transition *= scale

    start_lane = (x1 + direction * start_transition, lane_y)
    end_lane = (x2 - direction * end_transition, lane_y)
    path: list[list[float]] = [[_round(x1), _round(y1)]]
    if start_delta > 1e-6:
        _append_path(path, [[_round(start_lane[0]), _round(start_lane[1])]])
    _append_path(path, [[_round(end_lane[0]), _round(end_lane[1])]])
    if end_delta > 1e-6:
        _append_path(path, [[_round(x2), _round(y2)]])
    return path


def _polyline_point(points: list[list[float]], ratio: float) -> tuple[float, float]:
    if not points:
        return 0.0, 0.0
    if len(points) == 1:
        return points[0][0], points[0][1]
    ratio = min(1.0, max(0.0, ratio))
    lengths = [math.dist(start, end) for start, end in zip(points, points[1:])]
    total = sum(lengths)
    if total <= 1e-9:
        return points[0][0], points[0][1]
    target = total * ratio
    cursor = 0.0
    for index, length in enumerate(lengths):
        if cursor + length >= target or index == len(lengths) - 1:
            local = (target - cursor) / length if length else 0.0
            start = points[index]
            end = points[index + 1]
            return start[0] + (end[0] - start[0]) * local, start[1] + (end[1] - start[1]) * local
        cursor += length
    return points[-1][0], points[-1][1]


def _slice_polyline(points: list[list[float]], start_ratio: float, end_ratio: float) -> list[list[float]]:
    start_ratio = min(1.0, max(0.0, start_ratio))
    end_ratio = min(1.0, max(start_ratio, end_ratio))
    if start_ratio == 0 and end_ratio == 1:
        return points
    samples = max(2, int(math.ceil((end_ratio - start_ratio) * max(8, len(points) - 1))))
    return [
        [_round(x), _round(y)]
        for x, y in (
            _polyline_point(points, start_ratio + (end_ratio - start_ratio) * index / samples)
            for index in range(samples + 1)
        )
    ]


def _logic_section_source(layout: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(record.get("名称")): record
        for record in _records(layout, "逻辑区段表")
        if record.get("名称") not in (None, "")
    }


def _label_layout(
    tracks: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    clearance: float = 3.0,
) -> list[dict[str, Any]]:
    rail_boxes = []
    for track in tracks:
        points = track.get("geometry", {}).get("points", [])
        for start, end in zip(points, points[1:]):
            rail_boxes.append(
                (
                    min(start[0], end[0]) - clearance,
                    min(start[1], end[1]) - clearance,
                    max(start[0], end[0]) + clearance,
                    max(start[1], end[1]) + clearance,
                )
            )

    occupied: list[tuple[float, float, float, float]] = []
    offsets = [(0, -14), (0, 16), (14, -14), (-14, -14), (14, 16), (-14, 16), (24, 0), (-24, 0)]
    result = []
    for label in labels:
        width = max(16.0, len(str(label["text"])) * 5.5 + 8)
        height = 9.0
        chosen = None
        for dx, dy in offsets:
            x = label["anchor_x"] + dx
            y = label["anchor_y"] + dy
            box = (x - width / 2, y - height / 2, x + width / 2, y + height / 2)
            if any(_boxes_intersect(box, other) for other in occupied):
                continue
            if any(_boxes_intersect(box, rail) for rail in rail_boxes):
                continue
            chosen = (x, y, box)
            break
        if chosen is None:
            x = label["anchor_x"]
            y = label["anchor_y"] - 14 - len(occupied) % 3 * 10
            chosen = (x, y, (x - width / 2, y - height / 2, x + width / 2, y + height / 2))
        occupied.append(chosen[2])
        result.append({**label, "x": _round(chosen[0]), "y": _round(chosen[1]), "width": _round(width), "height": height})
    return result


def _boxes_intersect(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _orientation(a: list[float], b: list[float], c: list[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _proper_intersection(a: list[float], b: list[float], c: list[float], d: list[float]) -> bool:
    return _orientation(a, b, c) * _orientation(a, b, d) < 0 and _orientation(c, d, a) * _orientation(c, d, b) < 0


def _validate_station_geometry(
    station_id: str,
    included: set[int],
    tracks: list[dict[str, Any]],
    switches: list[dict[str, Any]],
    nodes: dict[str, TopologyNode],
    segments: dict[int, TopologySegment],
) -> list[dict[str, Any]]:
    issues: list[GeometryIssue] = []
    for seg_id in included:
        segment = segments[seg_id]
        start = nodes[segment.start_node]
        end = nodes[segment.end_node]
        measured = abs((end.position_m or 0.0) - (start.position_m or 0.0))
        tolerance = max(5.0, segment.length_m * 0.05)
        if start.x_source == "point_mileage" and end.x_source == "point_mileage" and abs(measured - segment.length_m) > tolerance:
            issues.append(
                GeometryIssue(
                    code="segment_mileage_length_mismatch",
                    severity="warning",
                    message="Point mileage span differs from Seg length; point mileage was preserved.",
                    object_type="segment",
                    object_id=str(seg_id),
                    details={"mileage_span_m": _round(measured), "seg_length_m": _round(segment.length_m)},
                )
            )

    for switch in switches:
        if switch.get("topology_node") is None:
            issues.append(
                GeometryIssue(
                    code="switch_common_node_unresolved",
                    severity="error",
                    message="The three switch legs do not expose a shared endpoint.",
                    object_type="switch",
                    object_id=str(switch.get("switch_id")),
                )
            )

    line_parts = []
    for track in tracks:
        points = track.get("geometry", {}).get("points", [])
        if len(points) > 32:
            step = max(1, math.ceil((len(points) - 1) / 31))
            sampled = points[::step]
            if sampled[-1] != points[-1]:
                sampled.append(points[-1])
            points = sampled
        for start, end in zip(points, points[1:]):
            line_parts.append((track["track_id"], start, end))
    crossing_count = 0
    for index, (track_id, start, end) in enumerate(line_parts):
        for other_id, other_start, other_end in line_parts[index + 1 :]:
            if track_id == other_id:
                continue
            if any(math.dist(point, other) < 0.01 for point in (start, end) for other in (other_start, other_end)):
                continue
            if _proper_intersection(start, end, other_start, other_end):
                crossing_count += 1
    if crossing_count:
        issues.append(
            GeometryIssue(
                code="unexpected_track_crossings",
                severity="warning",
                message="Non-node track crossings were detected and retained for review.",
                object_type="station",
                object_id=station_id,
                details={"count": crossing_count},
            )
        )
    return [issue.as_dict() for issue in issues]


def _build_station(
    layout: dict[str, Any],
    station: dict[str, Any],
    included: set[int],
    seeds: set[int],
    nodes: dict[str, TopologyNode],
    segments: dict[int, TopologySegment],
    meters_per_unit: float,
    track_spacing_m: float,
    vertical_exaggeration: float,
    horizontal_compression: float,
    owned_turnout_keys: set[tuple[int | None, int | None, int | None]],
) -> dict[str, Any]:
    station_id = str(station["station_id"])
    spacing_units = track_spacing_m / meters_per_unit * vertical_exaggeration
    lanes, group_directions = _assign_track_lanes(included, seeds, segments, spacing_units)
    segment_lanes = {seg_id: lanes[_track_key(segments[seg_id])] for seg_id in included}
    turnouts = [
        turnout
        for turnout in layout.get("turnouts", [])
        if _turnout_relation_key(turnout) in owned_turnout_keys
        if {
            _as_int(turnout.get("merge_seg_id")),
            _as_int(turnout.get("normal_seg")),
            _as_int(turnout.get("reverse_seg")),
        } & included
    ]
    switch_node_y: dict[str, float] = {}
    turnout_node_by_key: dict[tuple[int | None, int | None, int | None], str | None] = {}
    reverse_seg_ids: set[int] = set()
    turnout_relations: list[tuple[str | None, int | None, int | None, int | None]] = []
    for turnout in turnouts:
        node_key = _turnout_node_key(turnout, segments)
        turnout_node_by_key[_turnout_relation_key(turnout)] = node_key
        merge_seg = _as_int(turnout.get("merge_seg_id"))
        normal_seg = _as_int(turnout.get("normal_seg"))
        reverse_seg = _as_int(turnout.get("reverse_seg"))
        turnout_relations.append((node_key, merge_seg, normal_seg, reverse_seg))
        if reverse_seg is not None:
            reverse_seg_ids.add(reverse_seg)

    parent = {seg_id: seg_id for seg_id in included}

    def find(seg_id: int) -> int:
        while parent[seg_id] != seg_id:
            parent[seg_id] = parent[parent[seg_id]]
            seg_id = parent[seg_id]
        return seg_id

    def union(first: int | None, second: int | None) -> None:
        if first not in parent or second not in parent:
            return
        first_root = find(first)
        second_root = find(second)
        if first_root != second_root:
            parent[second_root] = first_root

    switch_nodes = {node_key for node_key, _, _, _ in turnout_relations if node_key}
    connected_by_node: dict[str, list[int]] = defaultdict(list)
    for seg_id in included:
        connected_by_node[segments[seg_id].start_node].append(seg_id)
        connected_by_node[segments[seg_id].end_node].append(seg_id)
    for node_key, connected in connected_by_node.items():
        if node_key in switch_nodes or not connected:
            continue
        for seg_id in connected[1:]:
            union(connected[0], seg_id)
    for _, merge_seg, normal_seg, _ in turnout_relations:
        union(merge_seg, normal_seg)

    component_segments: dict[int, list[int]] = defaultdict(list)
    for seg_id in included:
        component_segments[find(seg_id)].append(seg_id)
    component_direction: dict[int, int | None] = {}
    component_lanes: dict[int, float] = {}
    for root, component in component_segments.items():
        directions = [segments[seg_id].direction for seg_id in component if segments[seg_id].direction in {0, 1}]
        direction = Counter(directions).most_common(1)[0][0] if directions else None
        component_direction[root] = direction
        if any(seg_id in seeds for seg_id in component):
            component_lanes[root] = 0.0 if direction == 0 else spacing_units

    # Propagate schematic lanes through actual turnout topology. A reverse branch
    # is always one display lane away from its merge/normal route.
    for _ in range(len(turnout_relations) + 1):
        changed = False
        for _, merge_seg, normal_seg, reverse_seg in turnout_relations:
            reference_seg = merge_seg if merge_seg in parent else normal_seg
            if reference_seg not in parent or reverse_seg not in parent:
                continue
            reference_root = find(reference_seg)
            reverse_root = find(reverse_seg)
            if reference_root == reverse_root:
                continue
            direction = segments[reverse_seg].direction
            branch_sign = -1 if direction == 0 else 1
            if reference_root in component_lanes and reverse_root not in component_lanes:
                component_lanes[reverse_root] = component_lanes[reference_root] + branch_sign * spacing_units
                changed = True
            elif reverse_root in component_lanes and reference_root not in component_lanes:
                component_lanes[reference_root] = component_lanes[reverse_root] - branch_sign * spacing_units
                changed = True
        if not changed:
            break

    unknown_roots = [root for root in component_segments if root not in component_lanes]
    unknown_roots.sort(
        key=lambda root: min(_segment_midpoint_m(segments[seg_id], nodes) for seg_id in component_segments[root])
    )
    for index, root in enumerate(unknown_roots):
        direction = component_direction[root]
        if direction == 0:
            component_lanes[root] = -spacing_units * (index % 2 + 1)
        elif direction == 1:
            component_lanes[root] = spacing_units * (index % 2 + 2)
        else:
            component_lanes[root] = -spacing_units if index % 2 == 0 else spacing_units * 2

    for root, component in component_segments.items():
        component_lane = component_lanes[root]
        for seg_id in component:
            segment_lanes[seg_id] = component_lane

    for node_key, merge_seg, normal_seg, _ in turnout_relations:
        reference_seg = merge_seg if merge_seg in segment_lanes else normal_seg
        if node_key and reference_seg in segment_lanes:
            switch_node_y[node_key] = segment_lanes[reference_seg]

    node_lane_candidates: dict[str, list[float]] = defaultdict(list)
    for seg_id in included:
        segment = segments[seg_id]
        node_lane_candidates[segment.start_node].append(segment_lanes[seg_id])
        node_lane_candidates[segment.end_node].append(segment_lanes[seg_id])
    node_display_y = {
        node_key: sorted(values)[len(values) // 2]
        for node_key, values in node_lane_candidates.items()
        if values
    }
    node_display_y.update(switch_node_y)

    tracks = []
    track_by_seg: dict[int, dict[str, Any]] = {}
    for seg_id in sorted(included):
        segment = segments[seg_id]
        start_node = nodes[segment.start_node]
        end_node = nodes[segment.end_node]
        lane = segment_lanes[seg_id]
        start = (
            (start_node.position_m or 0.0) / meters_per_unit * horizontal_compression,
            node_display_y.get(segment.start_node, lane),
        )
        end = (
            (end_node.position_m or 0.0) / meters_per_unit * horizontal_compression,
            node_display_y.get(segment.end_node, lane),
        )
        if abs(start[1] - lane) < 1e-6 and abs(end[1] - lane) < 1e-6:
            points = [[_round(start[0]), _round(start[1])], [_round(end[0]), _round(end[1])]]
            geometry_source = "point-mileage-and-lane"
        else:
            is_reverse_branch = seg_id in reverse_seg_ids
            points = _lane_constrained_path(
                start,
                end,
                lane,
                use_circular_arc=is_reverse_branch,
                meters_per_unit=meters_per_unit,
                vertical_exaggeration=vertical_exaggeration,
            )
            geometry_source = "ats-schematic-turnout" if is_reverse_branch else "ats-schematic-transition"
        segment.display_points = points
        segment.geometry_source = geometry_source
        track_id = f"{station_id}-SEG-{seg_id}"
        track = {
            "track_id": track_id,
            "track_name": _track_key(segment),
            "station_id": station_id,
            "track_type": "main" if lane in {0.0, spacing_units} and seg_id not in reverse_seg_ids else "siding",
            "direction": "down" if group_directions[_track_key(segment)] == 0 else "up" if group_directions[_track_key(segment)] == 1 else None,
            "section_ids": [],
            "seg_id": seg_id,
            "geometry": {"type": "polyline", "points": points},
            "geometry_source": geometry_source,
            "confidence": "high" if geometry_source == "point-mileage-and-lane" else "medium",
        }
        tracks.append(track)
        track_by_seg[seg_id] = track

    logic_sources = _logic_section_source(layout)
    sections = []
    for block in layout.get("blocks", []):
        seg_id = _as_int(block.get("track_seg_id"))
        track = track_by_seg.get(seg_id)
        if track is None:
            continue
        source = logic_sources.get(str(block.get("section_id")), {})
        start_seg = _as_int(source.get("起点所处Seg编号"))
        end_seg = _as_int(source.get("终点所处Seg编号"))
        points = track["geometry"]["points"]
        if start_seg == seg_id and end_seg == seg_id and segments[seg_id].length_m > 0:
            start_ratio = _as_float(source.get("起点所处Seg偏移量")) / 100 / segments[seg_id].length_m
            end_ratio = _as_float(source.get("终点所处Seg偏移量")) / 100 / segments[seg_id].length_m
            points = _slice_polyline(points, start_ratio, end_ratio)
        section_id = str(block.get("section_id"))
        track["section_ids"].append(section_id)
        sections.append(
            {
                "section_id": section_id,
                "station_id": station_id,
                "track_id": track["track_id"],
                "seg_id": seg_id,
                "start": block.get("start"),
                "end": block.get("end"),
                "geometry": {"type": "polyline", "points": points},
                "geometry_source": track["geometry_source"],
            }
        )

    switch_payloads = []
    for turnout in turnouts:
        switch_id = str(turnout.get("switch_id"))
        node_key = turnout_node_by_key.get(_turnout_relation_key(turnout))
        node = nodes.get(node_key) if node_key else None
        x = (node.position_m or 0.0) / meters_per_unit * horizontal_compression if node else 0.0
        y = switch_node_y.get(node_key or "", 0.0)
        switch_payloads.append(
            {
                "switch_id": switch_id,
                "switch_uid": turnout.get("switch_uid"),
                "source_index": turnout.get("source_index"),
                "turnout_id": str(turnout.get("turnout_id")),
                "station_id": station_id,
                "source_direction": turnout.get("source_direction"),
                "linked_turnout_id": turnout.get("linked_turnout_id"),
                "lateral_speed_limit_raw": turnout.get("lateral_speed_limit_raw"),
                "switch_type": turnout.get("switch_type", "single"),
                "connects": [f"{station_id}-SEG-{seg_id}" for seg_id in (_as_int(turnout.get("merge_seg_id")), _as_int(turnout.get("normal_seg")), _as_int(turnout.get("reverse_seg"))) if seg_id in included],
                "normal_to": f"{station_id}-SEG-{_as_int(turnout.get('normal_seg'))}" if _as_int(turnout.get("normal_seg")) in included else None,
                "reverse_to": f"{station_id}-SEG-{_as_int(turnout.get('reverse_seg'))}" if _as_int(turnout.get("reverse_seg")) in included else None,
                "topology_node": node_key,
                "ratio": DEFAULT_SWITCH_RATIO,
                "curve_radius_m": DEFAULT_CURVE_RADIUS_M,
                "geometry": {"type": "point", "x": _round(x), "y": _round(y)},
                "geometry_source": "shared-topology-node" if node else "unresolved",
                "assumptions": ["switch_ratio_default_1_9", "curve_radius_default_200m"],
            }
        )

    signal_source = {str(record.get("名称")): record for record in _records(layout, "信号机表")}
    signals = []
    label_candidates = []
    for signal in layout.get("signals", []):
        source = signal_source.get(str(signal.get("signal_id")), {})
        seg_id = _as_int(source.get("所处Seg编号")) or _as_int(str(signal.get("track_id", "")).replace("SEG-", ""))
        track = track_by_seg.get(seg_id)
        if track is None:
            continue
        offset_m = _as_float(source.get("所处Seg偏移量（cm）")) / 100
        ratio = offset_m / segments[seg_id].length_m if segments[seg_id].length_m else 0.5
        anchor_x, anchor_y = _polyline_point(track["geometry"]["points"], ratio)
        outside = -1 if anchor_y <= spacing_units / 2 else 1
        signal_y = anchor_y + outside * (1.5 / meters_per_unit * vertical_exaggeration)
        signal_id = str(signal.get("signal_id"))
        signals.append(
            {
                "signal_id": signal_id,
                "station_id": station_id,
                "track_id": track["track_id"],
                "seg_id": seg_id,
                "direction": "down" if str(source.get("防护方向", "")).lower() == "0x55" else "up",
                "signal_type": signal.get("signal_type"),
                "lamp_layout": source.get("灯列信息"),
                "protects_switch_id": None,
                "protects_section_id": signal.get("protects_section_id"),
                "geometry": {"type": "point", "x": _round(anchor_x), "y": _round(signal_y)},
                "track_anchor": {"x": _round(anchor_x), "y": _round(anchor_y)},
                "geometry_source": "seg-offset",
            }
        )
        label_candidates.append(
            {
                "key": f"signal:{signal_id}",
                "kind": "signal",
                "text": signal_id,
                "anchor_x": anchor_x,
                "anchor_y": signal_y,
            }
        )

    station_platform_ids = {_as_int(value) for value in station.get("platform_ids", [])}
    platforms = []
    for platform in layout.get("platforms", []):
        if _as_int(platform.get("platform_id")) not in station_platform_ids:
            continue
        seg_id = _as_int(platform.get("seg_id"))
        track = track_by_seg.get(seg_id)
        if track is None:
            continue
        x, y = _polyline_point(track["geometry"]["points"], 0.5)
        platforms.append(
            {
                "platform_id": str(platform.get("platform_id")),
                "station_id": station_id,
                "track_id": track["track_id"],
                "seg_id": seg_id,
                "position_m": platform.get("position_m"),
                "geometry": {
                    "type": "rect",
                    "x": _round(x - 80 / meters_per_unit * horizontal_compression),
                    "y": _round(y + (3 if y <= spacing_units / 2 else -7)),
                    "width": _round(160 / meters_per_unit * horizontal_compression),
                    "height": 4.0,
                },
                "geometry_source": "platform-center-with-default-length",
                "assumptions": ["platform_length_default_160m"],
            }
        )

    section_labels = []
    for section in sections:
        x, y = _polyline_point(section["geometry"]["points"], 0.5)
        section_labels.append(
            {
                "key": f"section:{section['section_id']}",
                "kind": "section",
                "text": section["section_id"],
                "anchor_x": x,
                "anchor_y": y,
            }
        )
    labels = _label_layout(tracks, label_candidates + section_labels)

    all_points = [point for track in tracks for point in track["geometry"]["points"]]
    if all_points:
        feature_x = [
            value
            for value in (
                *(
                    platform["geometry"]["x"] + platform["geometry"]["width"] / 2
                    for platform in platforms
                ),
                *(switch["geometry"]["x"] for switch in switch_payloads),
                *(signal["geometry"]["x"] for signal in signals),
            )
            if math.isfinite(value)
        ]
        if not feature_x:
            feature_x = [_as_float(station.get("position")) / meters_per_unit * horizontal_compression]
        horizontal_padding = 120 / meters_per_unit * horizontal_compression
        min_x = min(feature_x) - horizontal_padding
        max_x = max(feature_x) + horizontal_padding
        minimum_width = 500 / meters_per_unit * horizontal_compression
        if max_x - min_x < minimum_width:
            center_x = (min_x + max_x) / 2
            min_x = center_x - minimum_width / 2
            max_x = center_x + minimum_width / 2
        min_y = min(point[1] for point in all_points) - 36
        max_y = max(point[1] for point in all_points) + 44
    else:
        center_x = _as_float(station.get("position")) / meters_per_unit * horizontal_compression
        half_width = 200 * horizontal_compression
        min_x, max_x, min_y, max_y = center_x - half_width, center_x + half_width, -40, 52
    view_box = {
        "minX": _round(min_x),
        "minY": _round(min_y),
        "maxX": _round(max_x),
        "maxY": _round(max_y),
        "width": _round(max_x - min_x),
        "height": _round(max_y - min_y),
    }
    issues = _validate_station_geometry(station_id, included, tracks, switch_payloads, nodes, segments)
    return {
        "station_id": station_id,
        "station_name": station.get("station_name") or station.get("name") or station_id,
        "position_m": station.get("position"),
        "track_ids": [track["track_id"] for track in tracks],
        "switch_ids": [switch["switch_id"] for switch in switch_payloads],
        "signal_ids": [signal["signal_id"] for signal in signals],
        "section_ids": [section["section_id"] for section in sections],
        "tracks": tracks,
        "switches": switch_payloads,
        "signals": signals,
        "sections": sections,
        "platforms": platforms,
        "labels": labels,
        "viewBox": view_box,
        "validation": {
            "status": "error" if any(issue["severity"] == "error" for issue in issues) else "warning" if issues else "ok",
            "issues": issues,
        },
        "source_coverage": {
            "seed_seg_ids": sorted(seeds),
            "seg_count": len(included),
            "track_count": len(tracks),
            "section_count": len(sections),
            "switch_count": len(switch_payloads),
            "signal_count": len(signals),
            "platform_count": len(platforms),
        },
    }


def build_station_yard_layout_v2(
    layout: dict[str, Any],
    *,
    meters_per_unit: float = DEFAULT_METERS_PER_UNIT,
    track_spacing_m: float = DEFAULT_TRACK_SPACING_M,
    vertical_exaggeration: float = DEFAULT_VERTICAL_EXAGGERATION,
    horizontal_compression: float = DEFAULT_HORIZONTAL_COMPRESSION,
) -> dict[str, Any]:
    nodes, segments = _build_topology(layout)
    adjacency = _segment_adjacency(segments)
    stations = sorted(layout.get("stations", []), key=lambda item: _as_float(item.get("position")))
    station_payloads = []
    all_turnouts = _enrich_turnouts(layout)
    render_layout = {**layout, "turnouts": all_turnouts}
    station_contexts = []
    for index, station in enumerate(stations):
        seeds = _station_seed_segments(layout, station)
        radius = _station_radius(stations, index)
        included = _collect_station_segments(
            station,
            radius,
            seeds,
            segments,
            nodes,
            adjacency,
            all_turnouts,
        )
        station_contexts.append(
            {
                "index": index,
                "station": station,
                "seeds": seeds,
                "included": included,
                "distances": _segment_distances(seeds, adjacency),
            }
        )

    turnout_owner_by_key: dict[tuple[int | None, int | None, int | None], str] = {}
    for turnout in all_turnouts:
        relation_key = _turnout_relation_key(turnout)
        connected = {seg_id for seg_id in relation_key if seg_id in segments}
        candidates = []
        for context in station_contexts:
            if not connected.intersection(context["included"]):
                continue
            distance = min(
                (context["distances"].get(seg_id, math.inf) for seg_id in connected),
                default=math.inf,
            )
            candidates.append((distance, context["index"], str(context["station"]["station_id"])))
        if candidates:
            turnout_owner_by_key[relation_key] = min(candidates)[2]

    for context in station_contexts:
        station = context["station"]
        seeds = context["seeds"]
        included = context["included"]
        station_id = str(station["station_id"])
        owned_turnout_keys = {
            relation_key
            for relation_key, owner_station_id in turnout_owner_by_key.items()
            if owner_station_id == station_id
        }
        for seg_id in included:
            segments[seg_id].station_ids.add(station_id)
        station_payload = _build_station(
            render_layout,
            station,
            included,
            seeds,
            nodes,
            segments,
            meters_per_unit,
            track_spacing_m,
            vertical_exaggeration,
            horizontal_compression,
            owned_turnout_keys,
        )
        station_payload["schematic"] = build_reference_schematic(station_payload)
        station_payloads.append(station_payload)

    yard_tracks = [item for station in station_payloads for item in station["tracks"]]
    yard_sections = [item for station in station_payloads for item in station["sections"]]
    yard_switches = [item for station in station_payloads for item in station["switches"]]
    yard_signals = [item for station in station_payloads for item in station["signals"]]
    issue_counts = Counter(
        issue["severity"]
        for station in station_payloads
        for issue in station["validation"]["issues"]
    )
    unresolved_nodes = sum(1 for node in nodes.values() if node.x_source == "component_fallback")
    assigned_turnout_keys = set(turnout_owner_by_key)
    unassigned_turnout_source_indexes = sorted(
        source_index
        for turnout in all_turnouts
        if _turnout_relation_key(turnout) not in assigned_turnout_keys
        for source_index in [_as_int(turnout.get("source_index"))]
        if source_index is not None
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "line_id": layout.get("line_id", "LINE-1"),
        "generated_at": time.time(),
        "coordinate_system": {
            "model_unit": "meter",
            "display_unit": "svg_user_unit",
            "meters_per_unit": meters_per_unit,
            "nominal_track_spacing_m": track_spacing_m,
            "vertical_display_exaggeration": vertical_exaggeration,
            "horizontal_display_compression": horizontal_compression,
            "x_axis": "line_mileage",
            "y_axis": "schematic_lane",
        },
        "geometry_policy": {
            "topology": "source-endpoint-relations",
            "x_coordinate": "point-mileage-then-topology-propagation",
            "y_coordinate": "direction-and-physical-track-lane",
            "switch_ratio_default": DEFAULT_SWITCH_RATIO,
            "curve_radius_default_m": DEFAULT_CURVE_RADIUS_M,
            "arc_sampling_step_m": ARC_STEP_M,
            "render_mode": "ats_schematic",
            "turnout_assignment": "unique-topology-distance-from-platform-segments",
            "missing_source_fields": [
                "survey_xy",
                "switch_model_or_ratio",
                "curve_radius_and_tangent",
                "platform_dimensions",
            ],
        },
        "quality_summary": {
            "status": "error" if issue_counts["error"] else "warning" if issue_counts["warning"] else "ok",
            "error_count": issue_counts["error"],
            "warning_count": issue_counts["warning"],
            "unresolved_component_node_count": unresolved_nodes,
            "source_turnout_count": len(all_turnouts),
            "assigned_station_turnout_count": len(yard_switches),
            "unassigned_turnout_source_indexes": unassigned_turnout_source_indexes,
        },
        "stations": station_payloads,
        "yard_tracks": yard_tracks,
        "yard_switches": yard_switches,
        "yard_signals": yard_signals,
        "yard_sections": yard_sections,
        "updated_at": time.time(),
    }


def _points_attribute(points: Iterable[Iterable[float]]) -> str:
    return " ".join(f"{_round(point[0])},{_round(point[1])}" for point in points)


def station_svg(station: dict[str, Any]) -> str:
    drawing = station.get("schematic") or station
    is_reference = drawing is not station
    box = drawing["viewBox"]
    width = box["width"]
    height = box["height"]
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box["minX"]} {box["minY"]} {width} {height}" '
            f'role="img" aria-label="{escape(str(station["station_name"]))} station yard">'
        ),
        f'<rect x="{box["minX"]}" y="{box["minY"]}" width="{width}" height="{height}" fill="#000000"/>',
        '<g id="tracks" fill="none" stroke-linecap="butt" stroke-linejoin="miter">',
    ]
    for track in drawing["tracks"]:
        color = "#a0a0ff" if track["track_type"] == "main" else "#8585df"
        stroke_width = "1.45" if track["track_type"] == "main" else "1.15"
        parts.append(
            f'<polyline id="{escape(track["track_id"])}" points="{_points_attribute(track["geometry"]["points"])}" '
            f'stroke="{color}" stroke-width="{stroke_width}"/>'
        )
    parts.append("</g>")
    parts.append('<g id="platforms">')
    for platform in drawing.get("platforms", []):
        geometry = platform["geometry"]
        center_x = _round(geometry["x"] + geometry["width"] / 2)
        center_y = _round(geometry["y"] + geometry["height"] / 2)
        if is_reference:
            parts.append(
                f'<rect x="{geometry["x"]}" y="{geometry["y"]}" width="{geometry["width"]}" '
                f'height="{geometry["height"]}" fill="#050505" stroke="#d7d7e8" stroke-width="1"/>'
            )
        else:
            parts.append(
                f'<line x1="{_round(center_x - 16)}" y1="{center_y}" x2="{_round(center_x + 16)}" y2="{center_y}" '
                'stroke="#d7d7e8" stroke-width="2.4"/>'
            )
            parts.append(
                f'<text x="{center_x}" y="{_round(center_y - 4)}" fill="#f8fafc" font-family="Consolas,monospace" '
                f'font-size="5.4" text-anchor="middle">{escape(str(platform["platform_id"]))}站台</text>'
            )
    parts.append("</g>")
    parts.append('<g id="switches" font-family="Consolas,monospace" font-size="5" text-anchor="middle">')
    for switch in drawing["switches"]:
        geometry = switch["geometry"]
        parts.append(
            f'<circle cx="{geometry["x"]}" cy="{geometry["y"]}" r="1.15" fill="#9a9cff"/>'
        )
        if not is_reference:
            parts.append(
                f'<text x="{geometry["x"]}" y="{_round(geometry["y"] - 6)}" fill="#22c55e">'
                f'{escape(str(switch["turnout_id"]))}</text>'
            )
    parts.append("</g>")
    parts.append('<g id="signals" font-family="Consolas,monospace" font-size="5.2">')
    for signal in drawing["signals"]:
        geometry = signal["geometry"]
        anchor = signal["track_anchor"]
        facing_sign = -1 if signal.get("direction") == "down" else 1
        head_x = _round(geometry["x"] + facing_sign * 5)
        spare_x = _round(head_x + facing_sign * 6.2)
        parts.append(
            f'<line x1="{anchor["x"]}" y1="{anchor["y"]}" x2="{geometry["x"]}" y2="{geometry["y"]}" stroke="#d1d5db" stroke-width="0.8"/>'
        )
        parts.append(
            f'<line x1="{geometry["x"]}" y1="{geometry["y"]}" x2="{head_x}" y2="{geometry["y"]}" stroke="#d1d5db" stroke-width="0.8"/>'
        )
        parts.append(
            f'<circle data-signal-id="{escape(signal["signal_id"])}" cx="{head_x}" cy="{geometry["y"]}" r="2.8" '
            'fill="#cc0000" stroke="#f8fafc" stroke-width="0.6"/>'
        )
        parts.append(
            f'<circle cx="{spare_x}" cy="{geometry["y"]}" r="2.5" fill="#050505" stroke="#d1d5db" stroke-width="0.6"/>'
        )
        text_anchor = "end" if facing_sign < 0 else "start"
        parts.append(
            f'<text x="{_round(geometry["x"] + facing_sign * 7)}" y="{_round(geometry["y"] - 7)}" fill="#e5e7eb" '
            f'text-anchor="{text_anchor}">{escape(signal["signal_id"])}</text>'
        )
    parts.append("</g>")
    parts.append('<g id="labels" font-family="Consolas,monospace" font-size="5.2" text-anchor="middle">')
    for label in drawing.get("labels", []):
        if label.get("kind") == "section":
            parts.append(
                f'<text x="{label["x"]}" y="{_round(label["y"] + 1.8)}" fill="#22c55e">'
                f'{escape(str(label["text"]))}</text>'
            )
    track_y_values = sorted(
        point[1]
        for track in drawing["tracks"]
        for point in track["geometry"]["points"]
    )
    center_y = track_y_values[len(track_y_values) // 2] if track_y_values else box["minY"] + height / 2
    parts.append(
        f'<text x="{_round(box["minX"] + 6)}" y="{_round(center_y - 18)}" fill="#ffffff" '
        'font-family="Consolas,monospace" font-size="6" text-anchor="start">&#8592; 上行方向</text>'
    )
    parts.append(
        f'<text x="{_round(box["maxX"] - 6)}" y="{_round(center_y + 25)}" fill="#ffffff" '
        'font-family="Consolas,monospace" font-size="6" text-anchor="end">下行方向 &#8594;</text>'
    )
    for annotation in drawing.get("annotations", []):
        parts.append(
            f'<text x="{annotation["x"]}" y="{annotation["y"]}" fill="#22c55e" '
            f'font-family="Consolas,monospace" font-size="6.5" text-anchor="middle">'
            f'{escape(str(annotation["text"]))}</text>'
        )
    parts.append("</g>")
    parts.append(
        f'<text x="{_round(box["minX"] + width / 2)}" y="{_round(box["minY"] + 14)}" fill="#ffffff" '
        f'font-family="Consolas,monospace" font-size="10" text-anchor="middle">{escape(str(station["station_name"]))}</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def export_station_yard_assets(
    yard_layout: dict[str, Any],
    *,
    json_paths: Iterable[Path],
    svg_directories: Iterable[Path],
) -> None:
    serialized = json.dumps(yard_layout, ensure_ascii=False, indent=2)
    for path in dict.fromkeys(Path(item) for item in json_paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialized, encoding="utf-8")
    for directory in dict.fromkeys(Path(item) for item in svg_directories):
        directory.mkdir(parents=True, exist_ok=True)
        for station in yard_layout["stations"]:
            filename = f'{station["station_id"]}.svg'
            (directory / filename).write_text(station_svg(station), encoding="utf-8")
