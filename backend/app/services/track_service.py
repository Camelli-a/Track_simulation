import time
from app.services.base_service import BaseService
from app.schemas.track import TrackStatus, TrackSegment


class TrackService(BaseService):

    def get_status(self) -> TrackStatus:
        # 不论 DATA_SOURCE 是什么，数据始终来自 state_store（ZMQ 聚合层）
        # state_store 无数据时降级返回静态 mock
        return self._live_status()

    def get_segments(self):
        return self.get_status().segments

    # ------------------------------------------------------------------
    # 实时数据：从 state_store 读区间占用状态
    # ------------------------------------------------------------------
    def _live_status(self) -> TrackStatus:
        try:
            from app.data_flow.state_store import state_store
            snapshot = state_store.get_snapshot()
            if snapshot.sections:
                segments = [
                    TrackSegment(
                        segment_id=sec.section_id,
                        start=sec.start,
                        end=sec.end,
                        condition=sec.condition or "normal",
                    )
                    for sec in sorted(snapshot.sections, key=lambda s: s.start)
                ]
                total_length = max((s.end for s in snapshot.sections), default=0.0)
                fault_count = sum(1 for s in snapshot.sections if s.condition == "fault")
                return TrackStatus(
                    timestamp=time.time(),
                    total_length=total_length,
                    segments=segments,
                    fault_count=fault_count,
                )
        except Exception:
            pass
        return self._mock_status()

    # ------------------------------------------------------------------
    # 静态 mock（state_store 尚无数据时使用）
    # ------------------------------------------------------------------
    @staticmethod
    def _mock_status() -> TrackStatus:
        segments = [
            TrackSegment(segment_id=f"SEG-{i:02d}",
                         start=i * 500.0,
                         end=(i + 1) * 500.0,
                         condition="normal")
            for i in range(10)
        ]
        return TrackStatus(
            timestamp=time.time(),
            total_length=5000.0,
            segments=segments,
            fault_count=0,
        )
