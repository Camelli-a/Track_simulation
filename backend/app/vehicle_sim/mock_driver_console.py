import argparse
import json
import time
from dataclasses import dataclass

from .zmq_bus import ZmqPublisher


@dataclass(frozen=True)
class MockDriverConsoleConfig:
    vehicle_id: str = "TRAIN-001"
    interval_sec: float = 0.1
    include_demo_ma: bool = True
    control_mode: str = "ato"
    direction: str = "forward"
    key_switch: bool = True
    door_closed_light: bool = True
    ato_start_btn: bool = True
    ato_capable: bool = True
    ato_active: bool = True
    emergency_button: bool = False
    emergency_cmd: bool = False
    parking_apply: bool = False
    parking_release: bool = True
    main_handle_raw: int = 0
    traction_level: int = 0
    brake_level: int = 0
    driver_console_connected: bool = True
    zmq_connected: bool = True
    speed_limit_kmh: float = 40.0
    target_speed_kmh: float = 40.0
    ma_limit_m: float = 500.0
    distance_to_ma_m: float = 500.0
    comm_source: str = "mock_driver_console"
    demo_ma_source: str = "single_vehicle_demo_ma"


def build_driver_input_message(
    config: MockDriverConsoleConfig,
) -> dict:
    return {
        "type": "driver_input",
        "source": config.comm_source,
        "vehicle_id": config.vehicle_id,
        "control_mode": config.control_mode,
        "direction": config.direction,
        "key_switch": config.key_switch,
        "door_closed_light": config.door_closed_light,
        "ato_start_btn": config.ato_start_btn,
        "ato_capable": config.ato_capable,
        "ato_active": config.ato_active,
        "emergency_button": config.emergency_button,
        "emergency_cmd": config.emergency_cmd,
        "parking_apply": config.parking_apply,
        "parking_release": config.parking_release,
        "main_handle_raw": config.main_handle_raw,
        "traction_level": config.traction_level,
        "brake_level": config.brake_level,
    }


def build_comm_state_message(
    config: MockDriverConsoleConfig,
) -> dict:
    return {
        "type": "comm_state",
        "source": config.comm_source,
        "driver_console_connected": config.driver_console_connected,
        "zmq_connected": config.zmq_connected,
    }


def build_demo_ma_message(
    config: MockDriverConsoleConfig,
) -> dict:
    return {
        "type": "ma_state",
        "vehicle_id": config.vehicle_id,
        "permission": "allow",
        "signal_state": "green",
        "speed_limit": config.speed_limit_kmh,
        "target_speed": config.target_speed_kmh,
        "ma_limit": config.ma_limit_m,
        "distance_to_ma": config.distance_to_ma_m,
        "source": config.demo_ma_source,
    }


def build_cycle_messages(
    config: MockDriverConsoleConfig,
) -> list[dict]:
    messages = [
        build_driver_input_message(config),
        build_comm_state_message(config),
    ]
    if config.include_demo_ma:
        messages.append(build_demo_ma_message(config))
    return messages


def publish_cycle(
    publisher: ZmqPublisher | None,
    config: MockDriverConsoleConfig,
) -> list[dict]:
    messages = build_cycle_messages(config)
    for message in messages:
        if publisher is not None:
            publisher.publish(message)
    return messages


def _print_cycle(messages: list[dict]) -> None:
    now = time.time()
    for message in messages:
        topic = message["type"]
        data = {key: value for key, value in message.items() if key != "type"}
        envelope = {
            "topic": topic,
            "timestamp": now,
            "data": data,
        }
        print(json.dumps(envelope, ensure_ascii=False))


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def _print_operator_logs(messages: list[dict], cycle: int) -> None:
    for message in messages:
        topic = message["type"]
        if topic == "driver_input":
            print(
                "[MockDriverConsole] 已下发driver_input | "
                f"周期: {cycle} | "
                f"vehicle_id: {message['vehicle_id']} | "
                f"control_mode: {message['control_mode']} | "
                f"ATO启动按钮: {_format_bool(bool(message['ato_start_btn']))} | "
                f"方向: {message['direction']} | "
                f"钥匙: {_format_bool(bool(message['key_switch']))} | "
                f"门关好: {_format_bool(bool(message['door_closed_light']))} | "
                f"紧急按钮: {_format_bool(bool(message['emergency_button']))}",
                flush=True,
            )
        elif topic == "comm_state":
            print(
                "[MockDriverConsole] 已下发comm_state | "
                f"周期: {cycle} | "
                f"司机台在线: {_format_bool(bool(message['driver_console_connected']))} | "
                f"ZMQ在线: {_format_bool(bool(message['zmq_connected']))}",
                flush=True,
            )
        elif topic == "ma_state":
            print(
                "[MockDriverConsole] 已下发demo MA授权 | "
                f"周期: {cycle} | "
                f"限速{message['speed_limit']}km/h | "
                f"目标速度{message['target_speed']}km/h | "
                f"MA终点{message['ma_limit']}m",
                flush=True,
            )


def _str_to_bool(value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value}")


def _non_negative_interval(value: str) -> float:
    interval = float(value)
    if interval <= 0:
        raise argparse.ArgumentTypeError("--interval must be positive")
    return interval


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="外部 mock 司机台：持续发布 driver_input / comm_state / demo ma_state。"
    )
    parser.add_argument("--vehicle-id", default="TRAIN-001")
    parser.add_argument("--mode", default="ato", choices=["ato", "manual"])
    parser.add_argument("--publish-ma", action="store_true")
    parser.add_argument("--interval", type=_non_negative_interval, default=0.1)
    parser.add_argument("--cycles", type=int, default=None)
    parser.add_argument("--zmq-pub-address", default=None)
    parser.add_argument("--speed-limit", type=float, default=40.0)
    parser.add_argument("--target-speed", type=float, default=40.0)
    parser.add_argument("--ma-limit", type=float, default=500.0)
    parser.add_argument("--distance-to-ma", type=float, default=500.0)
    parser.add_argument("--direction", default="forward", choices=["forward", "backward", "neutral"])
    parser.add_argument("--ato-start", type=_str_to_bool, default=True)
    parser.add_argument("--key-switch", type=_str_to_bool, default=True)
    parser.add_argument("--door-closed", type=_str_to_bool, default=True)
    parser.add_argument("--emergency", type=_str_to_bool, default=False)
    parser.add_argument("--driver-console-connected", type=_str_to_bool, default=True)
    parser.add_argument("--zmq-connected", type=_str_to_bool, default=True)
    parser.add_argument("--print-only", action="store_true")
    parser.add_argument("--json-log", action="store_true")
    return parser


def config_from_args(args: argparse.Namespace) -> MockDriverConsoleConfig:
    return MockDriverConsoleConfig(
        vehicle_id=args.vehicle_id,
        interval_sec=args.interval,
        include_demo_ma=args.publish_ma,
        control_mode=args.mode,
        direction=args.direction,
        key_switch=args.key_switch,
        door_closed_light=args.door_closed,
        ato_start_btn=args.ato_start,
        ato_capable=args.mode == "ato",
        ato_active=args.mode == "ato",
        emergency_button=args.emergency,
        emergency_cmd=args.emergency,
        driver_console_connected=args.driver_console_connected,
        zmq_connected=args.zmq_connected,
        speed_limit_kmh=args.speed_limit,
        target_speed_kmh=args.target_speed,
        ma_limit_m=args.ma_limit,
        distance_to_ma_m=args.distance_to_ma,
    )


def run_mock_driver_console(args: argparse.Namespace) -> None:
    config = config_from_args(args)
    publisher = None if args.print_only else ZmqPublisher(args.zmq_pub_address)
    cycle = 0
    print(
        "[MockDriverConsole] 启动 | "
        f"vehicle_id={config.vehicle_id} | "
        f"mode={config.control_mode} | "
        f"publish_ma={_format_bool(config.include_demo_ma)} | "
        f"interval={config.interval_sec}s",
        flush=True,
    )

    try:
        while args.cycles is None or cycle < args.cycles:
            messages = publish_cycle(publisher, config)
            cycle += 1
            _print_operator_logs(messages, cycle)
            if args.json_log:
                _print_cycle(messages)
            if args.cycles is None or cycle < args.cycles:
                time.sleep(config.interval_sec)
    finally:
        if publisher is not None:
            publisher.close()
        print("[MockDriverConsole] 已停止", flush=True)


def main() -> None:
    run_mock_driver_console(build_arg_parser().parse_args())


if __name__ == "__main__":
    main()
