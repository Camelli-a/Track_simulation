from dataclasses import dataclass


@dataclass
class TrackEdge:
    edge_id: int
    section_id: str
    start_m: float
    end_m: float
    begin_switch: str | None = None
    end_switch: str | None = None
    direction_code: int = 1

    def contains(self, position_m: float) -> bool:
        return self.start_m <= position_m < self.end_m

    def offset(self, position_m: float) -> float:
        if self.direction_code >= 0:
            return position_m - self.start_m
        return self.end_m - position_m


DEFAULT_TRACK_EDGES = [
    TrackEdge(1, "SEG-01", 0.0, 500.0, "SW-START", "SW-01"),
    TrackEdge(2, "SEG-02", 500.0, 1000.0, "SW-01", "SW-02"),
    TrackEdge(3, "SEG-03", 1000.0, 1600.0, "SW-02", "SW-STA-01"),
]


class TrackEdgeMap:
    def __init__(self, edges: list[TrackEdge] | None = None):
        self.edges = edges or DEFAULT_TRACK_EDGES

    def resolve(self, position_m: float) -> dict:
        for edge in self.edges:
            if edge.contains(position_m):
                return {
                    "edge_id": edge.edge_id,
                    "section_id": edge.section_id,
                    "edge_offset_m": edge.offset(position_m),
                    "direction_code": edge.direction_code,
                }

        edge = self.edges[-1]
        return {
            "edge_id": edge.edge_id,
            "section_id": edge.section_id,
            "edge_offset_m": max(0.0, edge.offset(position_m)),
            "direction_code": edge.direction_code,
        }

