from pydantic import BaseModel
from typing import List


class TrackSegment(BaseModel):
    segment_id: str
    start: float     # 起始里程 (m)
    end: float       # 终止里程 (m)
    condition: str   # normal | warning | fault


class TrackStatus(BaseModel):
    timestamp: float
    total_length: float          # 总长度 (m)
    segments: List[TrackSegment]
    fault_count: int = 0
