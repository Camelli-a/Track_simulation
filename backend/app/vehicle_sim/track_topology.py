from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


INVALID_EDGE_ID = 65535


def normalize_edge_id(value) -> int | None:
    if value is None or value == "":
        return None
    text = str(value).strip().upper()
    if text.startswith("SEG-"):
        text = text[4:]
    try:
        edge_id = int(float(text))
    except (TypeError, ValueError):
        return None
    return None if edge_id == INVALID_EDGE_ID else edge_id


@dataclass(frozen=True)
class TopologyEdge:
    edge_id: int
    length_m: float
    start_point_id: int | None = None
    end_point_id: int | None = None
    start_normal_edge_id: int | None = None
    start_lateral_edge_id: int | None = None
    end_normal_edge_id: int | None = None
    end_lateral_edge_id: int | None = None
    global_start_m: float | None = None
    global_end_m: float | None = None
    station_id: str | None = None

    def neighbors(self, direction: int) -> tuple[int, ...]:
        values = (
            (self.end_normal_edge_id, self.end_lateral_edge_id)
            if direction >= 0
            else (self.start_normal_edge_id, self.start_lateral_edge_id)
        )
        return tuple(value for value in values if value is not None)

    def exit_point_id(self, direction: int) -> int | None:
        return self.end_point_id if direction >= 0 else self.start_point_id


@dataclass(frozen=True)
class TopologyTurnout:
    switch_id: str
    merge_edge_id: int
    normal_edge_id: int
    reverse_edge_id: int
    default_state: str = "normal"

    @property
    def edge_ids(self) -> frozenset[int]:
        return frozenset(
            (self.merge_edge_id, self.normal_edge_id, self.reverse_edge_id)
        )


@dataclass(frozen=True)
class TrackCursor:
    edge_id: int
    offset_m: float
    edge_direction: int
    next_edge_id: int | None = None
    blocked: bool = False


@dataclass(frozen=True)
class TrackAdvanceResult:
    cursor: TrackCursor
    moved_distance_m: float


class TrackTopology:
    """Advance a train over physical Seg adjacency without changing old mileage APIs."""

    def __init__(
        self,
        edges: Iterable[TopologyEdge],
        turnouts: Iterable[TopologyTurnout] = (),
    ) -> None:
        self.edges = {edge.edge_id: edge for edge in edges}
        if not self.edges:
            raise ValueError("track topology requires at least one edge")
        self.turnouts = tuple(turnouts)
        self._turnouts_by_edge: dict[int, list[TopologyTurnout]] = {}
        self._turnout_states: dict[str, str] = {}
        for turnout in self.turnouts:
            self._turnout_states[
                self._normalize_switch_id(turnout.switch_id)
            ] = turnout.default_state
            for edge_id in turnout.edge_ids:
                self._turnouts_by_edge.setdefault(edge_id, []).append(turnout)

    def set_turnout_states(self, values: Iterable[dict]) -> None:
        for value in values or ():
            raw_id = (
                value.get("switch_id")
                or value.get("turnout_id")
                or value.get("source_index")
            )
            if raw_id is None:
                continue
            switch_id = self._normalize_switch_id(raw_id)
            raw_state = str(
                value.get("routing")
                or value.get("position")
                or value.get("state")
                or "normal"
            ).lower()
            self._turnout_states[switch_id] = (
                "reverse"
                if raw_state in {"reverse", "diverging", "反位", "1", "true"}
                else "normal"
            )

    def initial_cursor(
        self,
        position_m: float,
        direction: int = 1,
        preferred_edge_id=None,
        edge_offset_m: float | None = None,
    ) -> TrackCursor:
        edge_id = normalize_edge_id(preferred_edge_id)
        edge = self.edges.get(edge_id) if edge_id is not None else None
        if edge is None:
            candidates = [
                item
                for item in self.edges.values()
                if item.global_start_m is not None
                and item.global_end_m is not None
                and min(item.global_start_m, item.global_end_m)
                <= position_m
                <= max(item.global_start_m, item.global_end_m)
            ]
            edge = min(
                candidates or self.edges.values(),
                key=lambda item: (
                    abs(self._edge_midpoint(item) - position_m),
                    item.edge_id,
                ),
            )

        if edge_offset_m is None:
            offset = self._offset_for_position(edge, position_m)
        else:
            offset = max(0.0, min(float(edge_offset_m), edge.length_m))
        edge_direction = 1 if int(direction) >= 0 else -1
        next_edge_id = self._select_next_edge(edge.edge_id, edge_direction)
        return TrackCursor(
            edge_id=edge.edge_id,
            offset_m=offset,
            edge_direction=edge_direction,
            next_edge_id=next_edge_id,
            blocked=next_edge_id is None and self._at_boundary(edge, offset, edge_direction),
        )

    def advance(
        self,
        edge_id,
        offset_m: float,
        distance_m: float,
        edge_direction: int,
    ) -> TrackAdvanceResult:
        current = self.edges.get(normalize_edge_id(edge_id))
        if current is None:
            cursor = self.initial_cursor(0.0, edge_direction, edge_id, offset_m)
            current = self.edges[cursor.edge_id]
        else:
            cursor = TrackCursor(
                edge_id=current.edge_id,
                offset_m=max(0.0, min(float(offset_m), current.length_m)),
                edge_direction=1 if int(edge_direction) >= 0 else -1,
            )

        remaining = max(0.0, float(distance_m))
        moved = 0.0
        for _ in range(128):
            if remaining <= 1e-9:
                break
            current = self.edges[cursor.edge_id]
            available = (
                current.length_m - cursor.offset_m
                if cursor.edge_direction >= 0
                else cursor.offset_m
            )
            step = min(remaining, max(0.0, available))
            offset = cursor.offset_m + cursor.edge_direction * step
            moved += step
            remaining -= step
            if remaining <= 1e-9:
                cursor = TrackCursor(
                    edge_id=current.edge_id,
                    offset_m=max(0.0, min(offset, current.length_m)),
                    edge_direction=cursor.edge_direction,
                    next_edge_id=self._select_next_edge(
                        current.edge_id, cursor.edge_direction
                    ),
                )
                break

            next_edge_id = self._select_next_edge(
                current.edge_id, cursor.edge_direction
            )
            if next_edge_id is None:
                cursor = TrackCursor(
                    edge_id=current.edge_id,
                    offset_m=0.0 if cursor.edge_direction < 0 else current.length_m,
                    edge_direction=cursor.edge_direction,
                    next_edge_id=None,
                    blocked=True,
                )
                break

            next_edge = self.edges.get(next_edge_id)
            if next_edge is None:
                cursor = TrackCursor(
                    edge_id=current.edge_id,
                    offset_m=offset,
                    edge_direction=cursor.edge_direction,
                    next_edge_id=None,
                    blocked=True,
                )
                break
            next_direction = self._entry_direction(
                current, next_edge, cursor.edge_direction
            )
            cursor = TrackCursor(
                edge_id=next_edge.edge_id,
                offset_m=0.0 if next_direction >= 0 else next_edge.length_m,
                edge_direction=next_direction,
                next_edge_id=self._select_next_edge(
                    next_edge.edge_id, next_direction
                ),
            )

        return TrackAdvanceResult(cursor=cursor, moved_distance_m=moved)

    def next_edge(self, edge_id, direction: int) -> int | None:
        normalized = normalize_edge_id(edge_id)
        if normalized is None:
            return None
        return self._select_next_edge(normalized, direction)

    def _select_next_edge(self, edge_id: int, direction: int) -> int | None:
        edge = self.edges.get(edge_id)
        if edge is None:
            return None
        candidates = tuple(
            candidate
            for candidate in edge.neighbors(direction)
            if candidate in self.edges
        )
        if not candidates:
            return None

        for turnout in self._turnouts_by_edge.get(edge_id, ()):
            state = self._turnout_states.get(
                self._normalize_switch_id(turnout.switch_id),
                turnout.default_state,
            )
            selected_branch = (
                turnout.reverse_edge_id
                if state == "reverse"
                else turnout.normal_edge_id
            )
            if edge_id == turnout.merge_edge_id:
                return selected_branch if selected_branch in candidates else None
            if edge_id in {turnout.normal_edge_id, turnout.reverse_edge_id}:
                if edge_id != selected_branch:
                    return None
                if turnout.merge_edge_id in candidates:
                    return turnout.merge_edge_id

        return candidates[0]

    @staticmethod
    def _entry_direction(
        current: TopologyEdge,
        next_edge: TopologyEdge,
        current_direction: int,
    ) -> int:
        exit_point = current.exit_point_id(current_direction)
        if exit_point is not None:
            if next_edge.start_point_id == exit_point:
                return 1
            if next_edge.end_point_id == exit_point:
                return -1
        return 1 if current_direction >= 0 else -1

    @staticmethod
    def _normalize_switch_id(value) -> str:
        text = str(value).strip().upper()
        if text.startswith("SW-"):
            text = text[3:]
        try:
            text = str(int(text))
        except ValueError:
            pass
        return f"SW-{text}"

    @staticmethod
    def _edge_midpoint(edge: TopologyEdge) -> float:
        if edge.global_start_m is None or edge.global_end_m is None:
            return float(edge.edge_id) * 1_000_000.0
        return (edge.global_start_m + edge.global_end_m) / 2.0

    @staticmethod
    def _offset_for_position(edge: TopologyEdge, position_m: float) -> float:
        if (
            edge.global_start_m is None
            or edge.global_end_m is None
            or edge.global_end_m == edge.global_start_m
        ):
            return 0.0
        ratio = (position_m - edge.global_start_m) / (
            edge.global_end_m - edge.global_start_m
        )
        return max(0.0, min(ratio, 1.0)) * edge.length_m

    @staticmethod
    def _at_boundary(
        edge: TopologyEdge, offset_m: float, direction: int
    ) -> bool:
        return (
            offset_m >= edge.length_m - 1e-9
            if direction >= 0
            else offset_m <= 1e-9
        )
