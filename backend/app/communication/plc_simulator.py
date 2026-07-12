"""
PLC 司机台模拟器（仅用于测试，真实联调时不需要）
模拟 PLC 作为 TCP Server，以 100ms 周期发送 46 字节报文

运行方式：
    python -m app.communication.plc_simulator

然后在另一个终端启动 DriverDeskSource 进行联调。
"""
import socket
import struct
import time
import math
import random
import argparse
import logging
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# 与 driver_desk_source.py 保持一致
FRAME_LEN   = 46
FRAME_MAGIC = 0x55AA55AA
FRAME_FMT   = "<IH18sBBHBBHH12s"


def build_frame(
    speed: float,
    emergency_brake: bool = False,
    ato_active: bool = False,
    door_open_left: bool = False,
    door_open_right: bool = False,
    door_mode: int = 1,        # 0=半自动 1=手动 2=自动
) -> bytes:
    """
    构造一帧 46 字节报文

    Args:
        speed:           车速（整数，单位待确认，此处直接填入）
        emergency_brake: 是否触发紧急制动
        ato_active:      是否激活 ATO
        door_open_left:  开左门
        door_open_right: 开右门
        door_mode:       门模式（0/1/2）
    """
    # 状态字节0（第 24 字节）
    status_b0 = 0
    status_b0 |= (1 << 5)   # 门关好指示灯默认亮

    # 状态字节1（第 25 字节）
    status_b1 = 0
    if ato_active:
        status_b1 |= (1 << 0)   # bit0: 具备 ATO
        status_b1 |= (1 << 2)   # bit2: 激活 ATO

    # 制动字节（第 28 字节）
    brake_byte = 0
    if emergency_brake:
        brake_byte |= (1 << 0)

    # 车门字节（第 29 字节）
    door_byte = 0
    if door_open_left:
        door_byte |= (1 << 0)
    if door_open_right:
        door_byte |= (1 << 1)

    frame = struct.pack(
        FRAME_FMT,
        FRAME_MAGIC,            # [0:4]  帧头
        FRAME_LEN,              # [4:6]  总长度
        bytes(18),              # [6:24] 保留
        status_b0,              # [24]   状态字节0
        status_b1,              # [25]   状态字节1
        int(speed),             # [26:28] 速度
        brake_byte,             # [28]   制动
        door_byte,              # [29]   车门
        0,                      # [30:32] 保留
        door_mode,              # [32:34] 门模式
        bytes(12),              # [34:46] 保留
    )

    assert len(frame) == FRAME_LEN, f"Frame length error: {len(frame)}"
    return frame


def handle_client(conn: socket.socket, addr, interval: float):
    """处理一个客户端连接，持续发送模拟帧"""
    logger.info(f"Client connected from {addr}")
    t = 0.0
    count = 0

    try:
        while True:
            # 模拟匀速行驶，速度在 0~120 km/h 之间正弦波动
            speed = 60 + 40 * math.sin(t * 0.1)
            emergency_brake = random.random() < 0.01   # 1% 概率

            frame = build_frame(
                speed=speed,
                emergency_brake=emergency_brake,
            )
            conn.sendall(frame)

            count += 1
            if count % 50 == 0:
                logger.info(
                    f"[{addr}] Sent #{count} frames | "
                    f"speed={speed:.1f} eb={emergency_brake}"
                )

            t += interval
            time.sleep(interval)

    except (BrokenPipeError, ConnectionResetError):
        logger.info(f"Client {addr} disconnected")
    except Exception as e:
        logger.error(f"Error with client {addr}: {e}")
    finally:
        conn.close()


def run_server(host: str, port: int, interval: float):
    """启动 TCP Server，等待 DriverDeskSource 连接"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)

    logger.info(f"PLC Simulator listening on {host}:{port}")
    logger.info(f"Frame interval: {interval * 1000:.0f}ms | Frame length: {FRAME_LEN} bytes")
    logger.info("Waiting for DriverDeskSource to connect...")

    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(
                target=handle_client,
                args=(conn, addr, interval),
                daemon=True,
            )
            t.start()
    except KeyboardInterrupt:
        logger.info("PLC Simulator stopped")
    finally:
        server.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PLC 司机台模拟器（TCP Server）")
    parser.add_argument("--host",     default="127.0.0.1", help="监听地址")
    parser.add_argument("--port",     default=8001, type=int, help="监听端口")
    parser.add_argument("--interval", default=0.1, type=float, help="发帧间隔（秒）")
    args = parser.parse_args()

    run_server(args.host, args.port, args.interval)
