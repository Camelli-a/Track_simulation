from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TopologyNode:
    key: str
    endpoint_type: int
    source_id: int
    name: str = ""
    position_m: float | None = None
    direction: int | None = None
    track_name: str | None = None
    siding_description: str | None = None
    segment_ids: set[int] = field(default_factory=set)
    x_source: str = "unresolved"


@dataclass
class TopologySegment:
    seg_id: int
    start_node: str
    end_node: str
    length_m: float
    start_type: int
    end_type: int
    forward_seg_id: int | None = None
    lateral_seg_id: int | None = None
    physical_track_name: str | None = None
    direction: int | None = None
    station_ids: set[str] = field(default_factory=set)
    display_points: list[list[float]] = field(default_factory=list)
    geometry_source: str = "topology-derived"


@dataclass
class GeometryIssue:
    code: str
    severity: str
    message: str
    object_type: str
    object_id: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "details": self.details,
        }
