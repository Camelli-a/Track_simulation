import time

from app.core.config import settings
from app.data_flow.state_store import state_store
from app.schemas.signal import SignalEvaluateRequest, SignalStatus
from app.services.base_service import BaseService
from app.services.signal_control import calculate_signal_snapshot


class SignalService(BaseService):
    def get_status(self) -> SignalStatus:
        """Return the current signal snapshot from the shared dashboard store.

        Runtime signal data now enters through the ZMQ bus and is cached in
        state_store by data_flow. This endpoint is a REST compatibility view and
        must not branch on DATA_SOURCE or raise NotImplementedError for ZMQ.
        """

        snapshot = state_store.get_snapshot()
        if snapshot.signals or snapshot.sections or snapshot.ma_limits:
            return SignalStatus(
                timestamp=snapshot.timestamp,
                system_mode=snapshot.system.system_mode,
                lights=[
                    {
                        "signal_id": item.signal_id,
                        "position": item.position,
                        "state": item.state,
                    }
                    for item in snapshot.signals
                ],
                signals=[
                    {
                        "signal_id": item.signal_id,
                        "position": item.position,
                        "state": item.state,
                        "route_id": item.route_id or "",
                        "signal_state": item.signal_state,
                        "permission": item.permission,
                    }
                    for item in snapshot.signals
                ],
                sections=[
                    {
                        "section_id": item.section_id,
                        "start": item.start,
                        "end": item.end,
                        "occupied": item.occupied,
                        "vehicle_id": item.vehicle_id,
                        "locked": item.locked,
                        "locked_by_route_id": item.locked_by_route_id,
                        "condition": item.condition,
                    }
                    for item in snapshot.sections
                ],
                switches=[
                    {
                        "switch_id": item.switch_id,
                        "position": item.position,
                        "locked": item.locked,
                        "locked_by_route_id": item.locked_by_route_id,
                        "related_section": item.related_section or "",
                        "reason": item.reason or "",
                    }
                    for item in snapshot.switches
                ],
                ma_limits=[
                    {key: value for key, value in item.model_dump().items() if value is not None}
                    for item in snapshot.ma_limits
                ],
                route_results=[
                    {
                        "vehicle_id": item.vehicle_id or "",
                        "route_id": item.route_id or "",
                        "allowed": item.allowed,
                        "reason": item.reason or "",
                        "required_switch_id": item.required_switch_id or "",
                        "required_position": item.required_position or "unknown",
                        "current_position": item.current_position or "unknown",
                        "locked_by_route_id": item.locked_by_route_id,
                    }
                    for item in snapshot.route_results
                ],
            )

        if settings.ENABLE_DASHBOARD_MOCK:
            return self._mock_status()

        return SignalStatus(
            timestamp=time.time(),
            system_mode="offline",
            lights=[],
            signals=[],
            sections=[],
            switches=[],
            ma_limits=[],
            route_results=[],
        )

    def get_all_lights(self):
        return self.get_status().lights

    def evaluate(self, request: SignalEvaluateRequest) -> SignalStatus:
        train_states = [item.model_dump() for item in request.train_states]
        route_requests = [item.model_dump() for item in request.route_requests]
        control_result = calculate_signal_snapshot(train_states, route_requests)
        return SignalStatus(
            timestamp=time.time(),
            system_mode="normal",
            **control_result,
        )

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
