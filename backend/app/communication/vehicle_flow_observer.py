"""Compact ZMQ observer for one vehicle's station-stop flow.

Usage:
    python -m app.communication.vehicle_flow_observer --vehicle-id TRAIN-001
    python -m app.communication.vehicle_flow_observer --vehicle-id TRAIN-001 --topics train_state,ato_state --sample-interval 1
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

from app.communication.message_bus import MessageBus


DEFAULT_TOPICS = (
    "driver_input",
    "comm_state",
    "ma_state",
    "power_state",
    "train_state",
    "ato_state",
    "atp_state",
    "door_state",
    "alarm_event",
)

CHANGE_KEYS = {
    "train_state": (
        "driving",
        "source",
        "ato_state",
        "cmd",
        "applied",
        "atp",
        "eb",
        "stop_result",
    ),
    "ato_state": ("driving", "state", "ato"),
    "atp_state": ("intervened", "reason"),
    "door_state": ("door_state", "all_closed"),
    "driver_input": ("mode", "dir", "handle", "trac", "brake", "eb"),
    "ma_state": ("ma_limit", "allowed", "permission", "signal"),
    "comm_state": ("driver_console_connected", "zmq_connected"),
}


def _round(value: Any, digits: int = 2):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return value


def _belongs_to_vehicle(data: dict, vehicle_id: str) -> bool:
    msg_vehicle_id = data.get("vehicle_id")
    if msg_vehicle_id is not None:
        return str(msg_vehicle_id) == vehicle_id
    ma_limits = data.get("ma_limits")
    if isinstance(ma_limits, list):
        return any(str(item.get("vehicle_id")) == vehicle_id for item in ma_limits if isinstance(item, dict))
    # comm_state and power_state can be broadcasts.
    return True


def _summarize(topic: str, data: dict, vehicle_id: str) -> dict:
    if topic == "driver_input":
        return {
            "vehicle_id": data.get("vehicle_id"),
            "mode": data.get("control_mode"),
            "dir": data.get("direction"),
            "handle": data.get("main_handle_raw"),
            "trac": data.get("traction_level"),
            "brake": data.get("brake_level"),
            "key": data.get("key_switch"),
            "door_closed": data.get("door_closed_light"),
            "ato_active": data.get("ato_active"),
            "eb": data.get("emergency_button") or data.get("emergency_cmd"),
        }
    if topic == "ma_state":
        items = data.get("ma_limits")
        if isinstance(items, list):
            data = next((item for item in items if str(item.get("vehicle_id")) == vehicle_id), {})
        return {
            "vehicle_id": data.get("vehicle_id"),
            "ma_limit": data.get("ma_limit", data.get("ma_limit_m")),
            "allowed": data.get("allowed_speed_kmh", data.get("speed_limit")),
            "target_dist": data.get("target_distance_m", data.get("distance_to_ma")),
            "permission": data.get("permission"),
            "signal": data.get("signal_state"),
        }
    if topic == "comm_state":
        return {
            "driver_console_connected": data.get("driver_console_connected"),
            "zmq_connected": data.get("zmq_connected"),
            "last_message_at": _round(data.get("last_message_at"), 3),
        }
    if topic == "train_state":
        stop_result = data.get("stop_result") or {}
        return {
            "vehicle_id": data.get("vehicle_id"),
            "pos": _round(data.get("position_m", data.get("position"))),
            "speed": _round(data.get("speed_mps", data.get("speed_ms"))),
            "speed_kmh": _round(data.get("speed_kmh", data.get("speed"))),
            "mode": data.get("mode"),
            "driving": data.get("driving_mode"),
            "source": data.get("control_source"),
            "ato_state": data.get("ato_state"),
            "cmd": [data.get("commanded_traction_level"), data.get("commanded_brake_level")],
            "applied": [data.get("applied_traction_level"), data.get("applied_brake_level")],
            "stop": _round(data.get("stop_target")),
            "dist_stop": _round(data.get("distance_to_stop")),
            "atp": data.get("atp_intervened"),
            "eb": data.get("emergency_brake"),
            "stop_result": (
                {
                    "error_cm": _round(stop_result.get("error_cm")),
                    "status": stop_result.get("status"),
                    "qualified": stop_result.get("qualified"),
                }
                if stop_result
                else None
            ),
        }
    if topic == "ato_state":
        return {
            "vehicle_id": data.get("vehicle_id"),
            "driving": data.get("driving_mode"),
            "state": data.get("ato_state"),
            "target": _round(data.get("ato_target_speed_kmh")),
            "recommended": _round(data.get("recommended_speed_kmh")),
            "ato": [data.get("ato_traction_level"), data.get("ato_brake_level")],
            "stop": _round(data.get("stop_target_m")),
            "dist_stop": _round(data.get("distance_to_stop_m")),
        }
    if topic == "atp_state":
        return {
            "vehicle_id": data.get("vehicle_id"),
            "intervened": data.get("atp_intervened", data.get("emergency_brake")),
            "reason": data.get("reason"),
            "allowed": data.get("allowed_speed_kmh"),
            "eb_trigger": data.get("eb_trigger_speed_kmh"),
        }
    if topic == "door_state":
        return {
            "vehicle_id": data.get("vehicle_id"),
            "door_state": data.get("door_state"),
            "all_closed": data.get("doors_all_closed"),
            "mode": data.get("door_mode"),
        }
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Observe one vehicle's ZMQ station-stop flow.")
    parser.add_argument("--vehicle-id", default="TRAIN-001")
    parser.add_argument("--raw", action="store_true", help="print raw data instead of compact summaries")
    parser.add_argument(
        "--topics",
        default=",".join(DEFAULT_TOPICS),
        help="comma-separated topics to print, e.g. train_state,ato_state",
    )
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=0.0,
        help="minimum seconds between prints for the same topic; 0 disables throttling",
    )
    parser.add_argument(
        "--only-changes",
        action="store_true",
        help="print only when key status fields changed",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="optional jsonl file path to save printed summaries",
    )
    args = parser.parse_args()
    topics = tuple(item.strip() for item in args.topics.split(",") if item.strip())

    bus = MessageBus()
    bus.start()
    last_printed_at: dict[str, float] = {}
    last_signatures: dict[str, tuple] = {}
    log_file = open(args.log_file, "a", encoding="utf-8") if args.log_file else None

    def on_message(topic: str, data: dict) -> None:
        if not _belongs_to_vehicle(data, args.vehicle_id):
            return
        payload = data if args.raw else _summarize(topic, data, args.vehicle_id)
        now = time.time()
        if args.sample_interval > 0:
            last_at = last_printed_at.get(topic, 0.0)
            if now - last_at < args.sample_interval:
                return
        if args.only_changes and not args.raw:
            keys = CHANGE_KEYS.get(topic, tuple(payload))
            signature = tuple(json.dumps(payload.get(key), ensure_ascii=False, sort_keys=True) for key in keys)
            if last_signatures.get(topic) == signature:
                return
            last_signatures[topic] = signature
        last_printed_at[topic] = now
        line = f"{time.strftime('%H:%M:%S')} [{topic}] {json.dumps(payload, ensure_ascii=False)}"
        print(line, flush=True)
        if log_file is not None:
            log_file.write(
                json.dumps(
                    {
                        "time": now,
                        "topic": topic,
                        "data": payload,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            log_file.flush()

    for topic in topics:
        bus.subscribe(topic, on_message)

    print(
        f"Observing {args.vehicle_id}; topics={','.join(topics)}; press Ctrl+C to stop.",
        flush=True,
    )
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        if log_file is not None:
            log_file.close()
        bus.stop()


if __name__ == "__main__":
    main()
