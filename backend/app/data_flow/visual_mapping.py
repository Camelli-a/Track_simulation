from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from app.core.config import settings

logger = logging.getLogger(__name__)

VISUAL_EDGE_MIN_ID = 1
VISUAL_EDGE_MAX_ID = 48
DEFAULT_DOWN_EDGE_FILE = Path(__file__).with_name("visual_edges_down.json")


@dataclass(frozen=True)
class VisualEdgeDefinition:
    edge_id: int
    start_m: float
    end_m: float
    length_m: float

    def contains(self, position_m: float) -> bool:
        return self.start_m <= position_m <= self.end_m

    def offset(self, position_m: float) -> float:
        return position_m - self.start_m


@dataclass(frozen=True)
class VisualVehiclePosition:
    vehicle_id: str
    track: int
    direction: int
    direction_name: str
    position_m: float
    speed_mps: float
    edge_id: Optional[int]
    edge_offset_m: Optional[float]
    viewer_position_m: float
    line_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id,
            "track": self.track,
            "direction": self.direction,
            "direction_name": self.direction_name,
            "position_m": round(self.position_m, 3),
            "speed_mps": round(self.speed_mps, 3),
            "edge_id": self.edge_id,
            "edge_offset_m": (
                None if self.edge_offset_m is None else round(self.edge_offset_m, 3)
            ),
            "viewer_position_m": round(self.viewer_position_m, 3),
            "line_id": self.line_id,
        }


def _get(source: Mapping[str, Any] | Any, key: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=4)
def load_visual_edges(path: str | Path = DEFAULT_DOWN_EDGE_FILE) -> tuple[VisualEdgeDefinition, ...]:
    raw_edges = json.loads(Path(path).read_text(encoding="utf-8"))
    edges = tuple(
        VisualEdgeDefinition(
            edge_id=int(item["edge_id"]),
            start_m=float(item["start_m"]),
            end_m=float(item["end_m"]),
            length_m=float(item["length_m"]),
        )
        for item in raw_edges
    )
    for edge in edges:
        if not (VISUAL_EDGE_MIN_ID <= edge.edge_id <= VISUAL_EDGE_MAX_ID):
            logger.warning(
                "Visual edge id %s is outside the expected viewer range %s..%s",
                edge.edge_id,
                VISUAL_EDGE_MIN_ID,
                VISUAL_EDGE_MAX_ID,
            )
    return edges


def find_visual_edge(
    position_m: float,
    edges: Sequence[VisualEdgeDefinition] | None = None,
) -> Optional[VisualEdgeDefinition]:
    visual_edges = tuple(edges) if edges is not None else load_visual_edges()
    for edge in visual_edges:
        if edge.contains(position_m):
            if not (VISUAL_EDGE_MIN_ID <= edge.edge_id <= VISUAL_EDGE_MAX_ID):
                logger.warning(
                    "Matched visual edge id %s for position %.3fm is outside %s..%s",
                    edge.edge_id,
                    position_m,
                    VISUAL_EDGE_MIN_ID,
                    VISUAL_EDGE_MAX_ID,
                )
                return None
            return edge

    logger.warning(
        "No visual edge matched position_m=%.3f on %s mapping",
        position_m,
        getattr(settings, "VISUAL_DIRECTION_NAME", "down"),
    )
    return None


def build_visual_vehicle_position(
    train_state: Mapping[str, Any] | Any,
    edges: Sequence[VisualEdgeDefinition] | None = None,
) -> VisualVehiclePosition:
    """Convert internal train mileage into the viewer-facing edge contract.

    ``position_m`` remains the vehicle/ATO internal coordinate.  The calibrated
    ``viewer_position_m`` is only for the 3D viewer and must not feed back into
    ATO, ATP, or dynamics.
    """

    position_m = _to_float(_get(train_state, "position_m", _get(train_state, "position", 0.0)))
    speed_mps = _to_float(_get(train_state, "speed_mps", _get(train_state, "speed_ms", 0.0)))
    edge = find_visual_edge(position_m, edges=edges)
    edge_offset_m = None if edge is None else edge.offset(position_m)
    direction = int(_to_float(_get(train_state, "direction", 1), 1.0) or 1)
    viewer_position_m = (
        position_m
        + float(getattr(settings, "SIGNAL_COORD_OFFSET_M", 216.46))
        + float(getattr(settings, "VIEWER_ABS_OFFSET_M", 4028.28))
    )

    return VisualVehiclePosition(
        vehicle_id=str(_get(train_state, "vehicle_id", "TRAIN-001")),
        track=int(getattr(settings, "VISUAL_TRACK", 0)),
        direction=direction,
        direction_name=str(getattr(settings, "VISUAL_DIRECTION_NAME", "down")),
        position_m=position_m,
        speed_mps=speed_mps,
        edge_id=None if edge is None else edge.edge_id,
        edge_offset_m=edge_offset_m,
        viewer_position_m=viewer_position_m,
        line_id=str(_get(train_state, "line_id", "LINE-1")),
    )


def build_visual_payload(train_state: Mapping[str, Any] | Any) -> dict[str, Any]:
    return build_visual_vehicle_position(train_state).to_dict()
