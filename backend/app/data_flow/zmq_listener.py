from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict

import zmq

from app.core.config import settings
from app.data_flow.schemas import IncomingMessage
from app.data_flow.state_store import state_store

logger = logging.getLogger(__name__)


class ZmqDashboardListener:
    """Background ZMQ subscriber for real module data.

    Supported inputs:

    Communication MessageBus frame:
    train_state {"topic": "train_state", "timestamp": 1720000000.123, "data": {...}}

    Wrapped JSON:
    {
      "topic": "train_state",
      "timestamp": 1720000000.123,
      "data": {...}
    }

    Legacy flat JSON:
    {
      "type": "train_state",
      "timestamp": 1720000000.123,
      "source": "vehicle_algo",
      "vehicle_id": "TRAIN-001",
      "position": 1234.5,
      "speed": 62.4
    }

    Compatibility input with a nested data object is also accepted.
    """

    def __init__(self, address: str | None = None) -> None:
        self.address = address or getattr(
            settings,
            "ZMQ_BROKER_FRONTEND",
            settings.ZMQ_ADDRESS,
        )
        self._task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="zmq-dashboard-listener")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        context = zmq.Context.instance()
        socket = context.socket(zmq.SUB)
        socket.setsockopt_string(zmq.SUBSCRIBE, "")
        socket.setsockopt(zmq.RCVTIMEO, 500)
        socket.connect(self.address)
        state_store.update_comm({"zmq_connected": True, "source": "zmq"})
        logger.info("ZMQ dashboard listener connected to %s", self.address)
        try:
            while self._running:
                try:
                    raw = await asyncio.to_thread(socket.recv)
                except zmq.Again:
                    continue
                self.handle_raw_message(raw)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("ZMQ dashboard listener failed")
        finally:
            state_store.update_comm({"zmq_connected": False})
            socket.close(0)

    def handle_raw_message(self, raw: bytes) -> None:
        try:
            frame_topic, payload = self._parse_raw_payload(raw)
            message_type = payload.get("topic") or payload.get("type") or frame_topic
            if not message_type:
                raise ValueError("missing message type")
            message = IncomingMessage(
                type=message_type,
                timestamp=payload.get("timestamp", 0),
                source=payload.get("source", "unknown"),
                data=self._extract_data(payload),
            )
        except Exception:
            logger.warning("Invalid ZMQ message: %r", raw)
            return
        self.dispatch(message.type, message.data)

    @staticmethod
    def _parse_raw_payload(raw: bytes) -> tuple[str | None, Dict[str, Any]]:
        text = raw.decode("utf-8").strip()
        try:
            return None, json.loads(text)
        except json.JSONDecodeError:
            pass

        topic, separator, payload_text = text.partition(" ")
        if not separator:
            raise ValueError("message is neither JSON nor '<topic> <json>' frame")
        payload = json.loads(payload_text)
        if not isinstance(payload, dict):
            raise ValueError("message payload must be a JSON object")
        return topic or None, payload

    @staticmethod
    def _extract_data(payload: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(payload.get("data"), dict):
            data = dict(payload["data"])
        else:
            data = {
                key: value
                for key, value in payload.items()
                if key
                not in {"topic", "type", "timestamp", "source", "version", "protocol_version"}
            }
        if "timestamp" in payload and "timestamp" not in data:
            data["timestamp"] = payload["timestamp"]
        if "source" in payload and "source" not in data:
            data["source"] = payload["source"]
        return data

    def dispatch(self, message_type: str, data: Dict[str, Any]) -> None:
        if message_type == "train_state":
            vehicle_id = data.get("vehicle_id") or data.get("train_id") or data.get("id")
            if vehicle_id:
                state_store.update_train(vehicle_id, data)
        elif message_type == "driver_input":
            vehicle_id = data.get("vehicle_id") or data.get("train_id") or data.get("id")
            if vehicle_id:
                state_store.update_driver_input(vehicle_id, data)
        elif message_type == "ato_command":
            vehicle_id = data.get("vehicle_id") or data.get("train_id") or data.get("id")
            if vehicle_id:
                state_store.update_ato_command(vehicle_id, data)
        elif message_type == "signal_state":
            state_store.update_signal_state(data)
        elif message_type == "ma_state":
            ma_limits = data.get("ma_limits")
            if ma_limits is None and data.get("vehicle_id"):
                ma_limits = [data]
            state_store.update_ma_limits(ma_limits or [])
        elif message_type == "track_info":
            state_store.update_track_info(data)
        elif message_type == "power_state":
            state_store.update_power(data)
        elif message_type == "comm_state":
            state_store.update_comm(data)
        elif message_type == "alarm_event":
            state_store.add_alarm(data)
        else:
            logger.warning("Unknown dashboard message type: %s", message_type)


zmq_dashboard_listener = ZmqDashboardListener()
