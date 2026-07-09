"""
司机台模拟器（仅用于测试）
在真实司机台接入之前，用这个脚本模拟司机台发送 UDP 数据

运行方式：
    python -m app.communication.udp_simulator

支持两种模式：
    --mode json    发送 JSON 格式数据（默认）
    --mode binary  发送二进制格式数据（等格式文档后启用）
"""
import socket
import json
import time
import random
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def simulate_json(host: str, port: int, interval: float):
    """模拟司机台发送 JSON 格式数据"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    logger.info(f"UDP Simulator (JSON) → {host}:{port}, interval={interval}s")
    logger.info("Press Ctrl+C to stop")

    position = 0.0
    count = 0

    try:
        while True:
            # 模拟司机台操作：随机速度，位置累加
            speed = round(random.uniform(0, 120), 1)
            position += speed / 3.6 * interval  # 换算成 m
            position = position % 5000           # 循环跑

            data = {
                "line_id":         "LINE-1",
                "position":        round(position, 1),
                "speed":           speed,
                "acceleration":    round(random.uniform(-1.5, 1.5), 2),
                "mode":            "manual",
                "is_running":      True,
                "emergency_brake": random.random() < 0.02,  # 2% 概率触发紧急制动
            }

            payload = json.dumps(data).encode("utf-8")
            sock.sendto(payload, (host, port))

            count += 1
            logger.info(f"[#{count}] Sent → speed={data['speed']} km/h, "
                        f"position={data['position']} m, "
                        f"emergency_brake={data['emergency_brake']}")

            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info(f"Simulator stopped. Sent {count} packets total.")
    finally:
        sock.close()


def simulate_binary(host: str, port: int, interval: float):
    """
    模拟司机台发送二进制格式数据
    TODO: 等老师给格式后，在这里实现 struct.pack(...)
    """
    logger.warning("Binary mode not implemented yet. Use --mode json instead.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="司机台 UDP 模拟器")
    parser.add_argument("--host",     default="127.0.0.1", help="目标地址")
    parser.add_argument("--port",     default=9000, type=int, help="目标端口")
    parser.add_argument("--interval", default=0.1,  type=float, help="发送间隔（秒）")
    parser.add_argument("--mode",     default="json",
                        choices=["json", "binary"], help="数据格式")
    args = parser.parse_args()

    if args.mode == "json":
        simulate_json(args.host, args.port, args.interval)
    else:
        simulate_binary(args.host, args.port, args.interval)
