import time
import random
from app.services.base_service import BaseService
from app.schemas.power import PowerStatus


class PowerService(BaseService):

    def get_status(self) -> PowerStatus:
        if self.source == "mock":
            return self._mock_status()
        elif self.source in {"zmq", "udp"}:
            return self._zmq_status()
        else:
            raise ValueError(f"未知数据源: {self.source}")

    def _zmq_status(self) -> PowerStatus:
        """从 state_store 读取实时供电状态，无数据时降级 mock。"""
        try:
            from app.data_flow.state_store import state_store
            snapshot = state_store.get_snapshot()
            p = snapshot.power
            if p and not p.is_stale:
                return PowerStatus(
                    timestamp=time.time(),
                    voltage=p.voltage,
                    current=p.current,
                    power=p.power,
                    substation_id=p.substation_id,
                    is_fault=p.is_fault,
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
    def _mock_status() -> PowerStatus:
        return PowerStatus(
            timestamp=time.time(),
            voltage=round(random.uniform(1450, 1550), 2),   # 标称 1500V 直流
            current=round(random.uniform(200, 400), 2),
            power=round(random.uniform(300, 600), 2),
            substation_id="SS-01",
            is_fault=False,
        )
