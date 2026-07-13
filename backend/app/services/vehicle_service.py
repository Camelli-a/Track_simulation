import time
import random
from app.services.base_service import BaseService
from app.schemas.vehicle import VehicleStatus


class VehicleService(BaseService):

    def get_status(self) -> VehicleStatus:
        if self.source == "mock":
            return self._mock_status()
        elif self.source in {"zmq", "udp"}:
            return self._zmq_status()
        else:
            raise ValueError(f"未知数据源: {self.source}")

    def _zmq_status(self) -> VehicleStatus:
        """从 state_store 读取第一辆车的实时状态，无数据时降级 mock。"""
        try:
            from app.data_flow.state_store import state_store
            snapshot = state_store.get_snapshot()
            trains = snapshot.trains
            if trains:
                t = trains[0]
                return VehicleStatus(
                    timestamp=time.time(),
                    vehicle_id=t.vehicle_id,
                    position=t.position,
                    speed=t.speed,
                    acceleration=t.acceleration,
                    line_id=t.line_id,
                    is_running=t.is_running,
                )
        except Exception:
            pass
        return self._mock_status()

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
