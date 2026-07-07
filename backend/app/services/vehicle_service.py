import time
import random
from app.services.base_service import BaseService
from app.schemas.vehicle import VehicleStatus


class VehicleService(BaseService):

    def get_status(self) -> VehicleStatus:
        if self.source == "mock":
            return self._mock_status()
        elif self.source == "udp":
            # TODO: 接入 UDP 数据源
            raise NotImplementedError("UDP 数据源尚未实现")
        elif self.source == "zmq":
            # TODO: 接入 ZMQ 数据源
            raise NotImplementedError("ZMQ 数据源尚未实现")
        else:
            raise ValueError(f"未知数据源: {self.source}")

    def get_history(self, limit: int = 100):
        # TODO: 接入历史数据存储
        return [self._mock_status() for _ in range(limit)]

    # ------------------------------------------------------------------
    # Mock 数据
    # ------------------------------------------------------------------
    @staticmethod
    def _mock_status() -> VehicleStatus:
        return VehicleStatus(
            timestamp=time.time(),
            vehicle_id="TRAIN-001",
            position=round(random.uniform(0, 5000), 1),
            speed=round(random.uniform(0, 120), 1),
            acceleration=round(random.uniform(-1.5, 1.5), 2),
            line_id="LINE-1",
            is_running=True,
        )
