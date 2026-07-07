import time
from app.services.base_service import BaseService
from app.schemas.track import TrackStatus, TrackSegment


class TrackService(BaseService):

    def get_status(self) -> TrackStatus:
        if self.source == "mock":
            return self._mock_status()
        elif self.source == "udp":
            raise NotImplementedError("UDP 数据源尚未实现")
        elif self.source == "zmq":
            raise NotImplementedError("ZMQ 数据源尚未实现")
        else:
            raise ValueError(f"未知数据源: {self.source}")

    def get_segments(self):
        return self._mock_status().segments

    # ------------------------------------------------------------------
    # Mock 数据
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
