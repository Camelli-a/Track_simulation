import time

from app.services.base_service import BaseService
from app.schemas.signal import SignalEvaluateRequest, SignalStatus
from app.services.signal_control import calculate_signal_snapshot


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

    def evaluate(self, request: SignalEvaluateRequest) -> SignalStatus:
        train_states = [item.model_dump() for item in request.train_states]
        route_requests = [item.model_dump() for item in request.route_requests]
        control_result = calculate_signal_snapshot(train_states, route_requests)
        return SignalStatus(
            timestamp=time.time(),
            system_mode="normal",
            **control_result,
        )

    # ------------------------------------------------------------------
    # Mock：B 组 signal_control 算法（5 区段演示线）
    # ------------------------------------------------------------------
    @staticmethod
    def _mock_status() -> SignalStatus:
        mock_train_states = [
            {
                "vehicle_id": "TRAIN-001",
                "position": 300.0,
                "speed": 42.0,
                "route_id": "R_MAIN",
            },
            {
                "vehicle_id": "TRAIN-002",
                "position": 620.0,
                "speed": 55.0,
                "route_id": "R_MAIN",
            },
            {
                "vehicle_id": "TRAIN-003",
                "position": 2435.0,
                "speed": 25.0,
                "route_id": "R_MAIN",
            },
        ]
        mock_route_requests = [
            {
                "vehicle_id": "TRAIN-003",
                "route_id": "R_BRANCH",
            }
        ]
        control_result = calculate_signal_snapshot(mock_train_states, mock_route_requests)
        return SignalStatus(
            timestamp=time.time(),
            system_mode="normal",
            **control_result,
        )
