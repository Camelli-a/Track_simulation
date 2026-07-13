"""
PLC 司机台模拟器（仅用于测试，真实联调时不需要）
模拟 PLC 作为 TCP Server，以 100ms 周期发送 46 字节报文

依据《司机驾驶模拟台PLC协议》7.1节完整帧格式构造报文。

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

FRAME_LEN   = 46
FRAME_MAGIC = 0x55AA55AA  # 小端 DWORD，原始字节 AA 55 AA 55

# 与 driver_desk_source.py 完全一致的 struct 格式
FRAME_FMT = "<IHHHHHHHHHHBBHBBHHBBHHHHH"


def build_frame(
    direction: int = 1,         # 0=0位 1=向前 2=向后
    main_handle: int = 0,       # 0=惰行 1=牵引 2=制动 4=快制
    traction_percent: int = 0,  # 牵引极位百分比 0~100
    brake_percent: int = 0,     # 制动极位百分比 0~100
    emergency_brake: bool = False,
    ato_active: bool = False,
    ato_capable: bool = False,
    door_mode: int = 1,         # 0=半自动 1=手动 2=自动
) -> bytes:
    """
    构造一帧完整的 46 字节 PLC 下行报文（7.1节格式）
    """
    now = time.localtime()

    # status_byte0（字节24）
    status_b0 = (1 << 5)  # 门关好指示灯默认亮

    # status_byte1（字节25）
    status_b1 = 0
    if ato_capable or ato_active:
        status_b1 |= (1 << 0)   # bit0: 具备ATO
    if ato_active:
        status_b1 |= (1 << 2)   # bit2: 激活ATO

    # speed_echo（字节26~27）：上位机上次发的速度回显，模拟器填0
    speed_echo = 0

    # brake_byte（字节28）
    brake_byte = 0
    if emergency_brake:
        brake_byte |= (1 << 0)

    # door_byte（字节29）：模拟器默认门关闭
    door_byte = 0

    # button_byte0（字节34）：模拟器默认所有按钮未按
    button_byte0 = 0

    # button_byte1（字节35）：模拟器默认钥匙开关插入
    button_byte1 = (1 << 1)  # bit1: 钥匙开关

    frame = struct.pack(
        FRAME_FMT,
        FRAME_MAGIC,        # [0]  _uIdentify
        FRAME_LEN,          # [1]  _uTotalLen
        22,                 # [2]  _uDataLen
        now.tm_year,        # [3]  _uYear
        now.tm_mon,         # [4]  _uMonth
        now.tm_mday,        # [5]  _uDay
        now.tm_hour,        # [6]  _uHour
        now.tm_min,         # [7]  _uMinute
        now.tm_sec,         # [8]  _uSecond
        0,                  # [9]  _uVerifyType
        0,                  # [10] _uVerifyCode
        status_b0,          # [11] status_byte0
        status_b1,          # [12] status_byte1
        speed_echo,         # [13] speed_echo（回显，非真实速度）
        brake_byte,         # [14] brake_byte
        door_byte,          # [15] door_byte
        0,                  # [16] light_switch
        door_mode,          # [17] door_mode
        button_byte0,       # [18] button_byte0
        button_byte1,       # [19] button_byte1
        direction,          # [20] direction_handle
        main_handle,        # [21] main_handle
        traction_percent,   # [22] traction_percent
        brake_percent,      # [23] brake_percent
        0,                  # [24] reserved_end
    )

    assert len(frame) == FRAME_LEN, f"Frame length error: {len(frame)}"
    return frame


def handle_client(conn: socket.socket, addr, interval: float):
    """处理一个客户端连接，模拟司机推手柄操作"""
    logger.info(f"Client connected from {addr}")
    t = 0.0
    count = 0

    try:
        while True:
            # 模拟司机操作序列：
            # 前30秒：牵引（手柄1=牵引，极位50%，方向向前）
            # 30~60秒：惰行
            # 60秒后：制动（手柄2=制动，极位60%）
            cycle = t % 90

            if cycle < 30:
                main_handle = 1       # 牵引
                trac_pct    = 50
                brk_pct     = 0
            elif cycle < 60:
                main_handle = 0       # 惰行
                trac_pct    = 0
                brk_pct     = 0
            else:
                main_handle = 2       # 制动
                trac_pct    = 0
                brk_pct     = 60

            # Keep the demo PLC stable by default. Random emergency frames can
            # latch the vehicle into emergency mode and make ATO联调 look broken.
            emergency_brake = False

            frame = build_frame(
                direction=1,
                main_handle=main_handle,
                traction_percent=trac_pct,
                brake_percent=brk_pct,
                emergency_brake=emergency_brake,
                ato_capable=True,
                ato_active=False,
            )
            conn.sendall(frame)

            count += 1
            if count % 50 == 0:
                logger.info(
                    f"[{addr}] #{count} "
                    f"handle={main_handle} trac={trac_pct}% brk={brk_pct}% "
                    f"eb={emergency_brake}"
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
