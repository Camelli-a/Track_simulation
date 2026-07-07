import time
import random
from app.services.base_service import BaseService
from app.schemas.power import PowerStatus


class PowerService(BaseService):

    def get_status(self) -> PowerStatus:
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
    def _mock_status() -> PowerStatus:
        return PowerStatus(
            timestamp=time.time(),
            voltage=round(random.uniform(1450, 1550), 2),   # 标称 1500V 直流
            current=round(random.uniform(200, 400), 2),
            power=round(random.uniform(300, 600), 2),
            substation_id="SS-01",
            is_fault=False,
        )
