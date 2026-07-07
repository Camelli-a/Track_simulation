import time
import random
from app.services.base_service import BaseService
from app.schemas.signal import SignalStatus, SignalLight


class SignalService(BaseService):

    def get_status(self) -> SignalStatus:
        if self.source == "mock":
            return self._mock_status()
        elif self.source == "udp":
            raise NotImplementedError("UDP 数据源尚未实现")
        elif self.source == "zmq":
            raise NotImplementedError("ZMQ 数据源尚未实现")
        else:
            raise ValueError(f"未知数据源: {self.source}")

    def get_all_lights(self):
        return self._mock_status().lights

    # ------------------------------------------------------------------
    # Mock 数据
    # ------------------------------------------------------------------
    @staticmethod
    def _mock_status() -> SignalStatus:
        states = ["red", "yellow", "green"]
        lights = [
            SignalLight(
                signal_id=f"SIG-{i:02d}",
                position=i * 500.0,
                state=random.choice(states),
            )
            for i in range(10)
        ]
        return SignalStatus(
            timestamp=time.time(),
            lights=lights,
            system_mode="normal",
        )
