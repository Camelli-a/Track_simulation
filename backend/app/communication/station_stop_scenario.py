"""Publish a minimal AM station-stop scenario over the shared ZMQ bus.

This script only publishes external inputs (driver_input, ma_state,
comm_state, power_state).  It does not modify vehicle state directly.

Recommended train process for the default line-layout stop near 313m:
    python -m app.vehicle_sim.main_integrated --vehicle-id TRAIN-001 --train-index 1 --initial-position 0

Then run:
    python -m app.communication.station_stop_scenario --vehicle-id TRAIN-001
"""

from __future__ import annotations

import argparse
import time

from app.communication.message_bus import MessageBus


def _publish_inputs(
    bus: MessageBus,
    *,
    vehicle_id: str,
    ma_limit_m: float,
    allowed_speed_kmh: float,
    stop_target_m: float | None,
    duration_s: float,
    dt: float,
) -> None:
    steps = max(1, int(duration_s / dt))
    for step in range(steps):
        now = time.time()
        driver_input = {
            "vehicle_id": vehicle_id,
            "line_id": "LINE-1",
            "source": "demo",
            "direction": "forward",
            "direction_code": 1,
            "main_handle_raw": 0,
            "traction_level": 0,
            "brake_level": 0,
            "traction_percent": 0.0,
            "brake_percent": 0.0,
            "control_mode": "ato",
            "ato_capable": True,
            "ato_active": True,
            "ato_start_btn": True if step < 3 else False,
            "emergency_button": False,
            "emergency_cmd": False,
            "key_switch": True,
            "door_closed_light": True,
            "parking_apply": False,
            "parking_release": False,
            "network_fault_light": False,
            "wash_mode_status": False,
        }
        ma_state = {
            "vehicle_id": vehicle_id,
            "ma_limit": ma_limit_m,
            "ma_limit_m": ma_limit_m,
            "allowed_speed_kmh": allowed_speed_kmh,
            "speed_limit": allowed_speed_kmh,
            "eb_trigger_speed_kmh": allowed_speed_kmh + 10.0,
            "target_distance_m": ma_limit_m,
            "permission": "allow",
            "signal_state": "green",
            "updated_at": now,
        }
        if stop_target_m is not None:
            ma_state["stop_target_m"] = stop_target_m
        comm_state = {
            "source": "demo",
            "driver_console_connected": True,
            "zmq_connected": True,
            "last_message_at": now,
        }
        power_state = {
            "source": "demo",
            "voltage": 1500.0,
            "current": 100.0,
            "power": 150.0,
            "is_fault": False,
        }

        bus.publish("driver_input", driver_input)
        bus.publish("ma_state", ma_state)
        bus.publish("comm_state", comm_state)
        bus.publish("power_state", power_state)

        if step % max(1, int(1.0 / dt)) == 0:
            print(
                f"sent t={step * dt:.1f}s vehicle={vehicle_id} "
                f"mode=ato ma_limit={ma_limit_m} allowed={allowed_speed_kmh} "
                f"stop_target={stop_target_m}",
                flush=True,
            )
        time.sleep(dt)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish one AM station-stop demo scenario.")
    parser.add_argument("--vehicle-id", default="TRAIN-001")
    parser.add_argument("--ma-limit", type=float, default=500.0)
    parser.add_argument("--allowed-speed", type=float, default=45.0)
    parser.add_argument(
        "--stop-target",
        type=float,
        default=313.0,
        help="Absolute stop target in meters. Use a negative value to omit it.",
    )
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--dt", type=float, default=0.1)
    args = parser.parse_args()
    stop_target_m = None if args.stop_target < 0.0 else args.stop_target

    bus = MessageBus()
    bus.start()
    try:
        _publish_inputs(
            bus,
            vehicle_id=args.vehicle_id,
            ma_limit_m=args.ma_limit,
            allowed_speed_kmh=args.allowed_speed,
            stop_target_m=stop_target_m,
            duration_s=args.duration,
            dt=args.dt,
        )
    finally:
        bus.stop()


if __name__ == "__main__":
    main()
