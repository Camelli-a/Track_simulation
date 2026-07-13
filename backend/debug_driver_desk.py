"""
司机台 TCP 调试脚本
====================
用途：明天硬件联调时独立运行，不依赖完整后端。
      连接 PLC 司机台，接收报文，持久化到 logs/，同时打印关键字段。

使用方式（在 backend 目录下）：
    python debug_driver_desk.py
    python debug_driver_desk.py --host 192.168.100.123 --port 8001
    python debug_driver_desk.py --host 192.168.100.123 --port 8001 --no-zmq

参数说明：
    --host      PLC IP，默认读 .env 中 PLC_HOST
    --port      PLC 端口，默认读 .env 中 PLC_PORT
    --no-zmq    不启动 ZMQ Broker，只看日志和文件，适合单机快速验证
    --log-dir   日志目录，默认 logs/
"""
import argparse
import logging
import sys
import time
import threading
from pathlib import Path

# ── 确保在 backend 目录下运行 ──────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from app.communication.driver_desk_source import DriverDeskSource
from app.communication.message_bus import MessageBus
from app.core.config import settings

# ── 日志配置：同时输出到控制台和文件 ──────────────────────────────────
Path("logs").mkdir(exist_ok=True)
log_file = Path("logs") / f"debug_{time.strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)
logger = logging.getLogger("debug_driver_desk")


# ── 订阅回调：打印关键字段，方便现场观察 ──────────────────────────────
_last_print_at = 0.0
_silent_mode   = False   # --send 时置 True，关闭接收侧 print，避免刷屏

def on_driver_input(topic: str, data: dict):
    """
    每秒打印一次摘要。
    --send 模式下 _silent_mode=True，接收摘要只写文件，不打印到控制台，
    避免和交互式发送提示符混乱。
    """
    global _last_print_at
    if _silent_mode:
        return                      # 发送模式：接收侧静默，数据已写 .jsonl
    now = time.time()
    if now - _last_print_at < 1.0:
        return
    _last_print_at = now

    print(
        f"\n[driver_input] "
        f"dir={data.get('direction'):<8} "
        f"handle={data.get('main_handle_raw')} "
        f"trac={data.get('traction_percent'):>3}% "
        f"brk={data.get('brake_percent'):>3}%  "
        f"mode={data.get('control_mode'):<6} "
        f"EB={int(data.get('emergency_button', 0))} "
        f"ATO_active={int(data.get('ato_active', 0))} "
        f"key={int(data.get('key_switch', 0))} "
        f"door_closed={int(data.get('door_closed_light', 0))}"
    )

def on_comm_state(topic: str, data: dict):
    pass  # 心跳太频繁，不打印


def main():
    parser = argparse.ArgumentParser(description="司机台 TCP 调试脚本")
    parser.add_argument("--host",    default=None,   help="PLC IP")
    parser.add_argument("--port",    default=None,   type=int, help="PLC TCP 端口")
    parser.add_argument("--no-zmq",  action="store_true", help="不启动 ZMQ Broker")
    parser.add_argument("--send",    action="store_true", help="启用交互式发送模式")
    parser.add_argument("--log-dir", default="logs", help="日志目录")
    args = parser.parse_args()

    host = args.host or settings.PLC_HOST
    port = args.port or settings.PLC_PORT
    logger.info(f"目标 PLC: {host}:{port}")
    logger.info(f"日志目录: {args.log_dir}")
    logger.info(f"日志文件: {log_file}")

    # ── 启动 MessageBus ────────────────────────────────────────────────
    # --no-zmq 模式下也创建 MessageBus，但不连接 ZMQ Broker（本地内存总线）
    # 这样 DriverDeskSource 内部调用 bus.publish() 不会崩，
    # 我们在这里订阅回调来打印摘要
    bus = MessageBus()
    bus.start()
    bus.subscribe("driver_input", on_driver_input)
    bus.subscribe("comm_state",   on_comm_state)
    if not args.no_zmq:
        logger.info("ZMQ MessageBus 已启动（含 ZMQ 连接）")
    else:
        logger.info("--no-zmq 模式：MessageBus 本地运行，不连接 ZMQ Broker，仅写文件+打印")

    # ── 启动 DriverDeskSource ──────────────────────────────────────────
    source = DriverDeskSource(
        vehicle_id="TRAIN-001",
        plc_host=host,
        plc_port=port,
        bus=bus,
        record_dir=args.log_dir,
        record_raw=True,
    )
    source.start()

    logger.info("=" * 60)
    logger.info("调试脚本已启动，按 Ctrl+C 停止")
    logger.info(f"  解析日志 → logs/driver_TRAIN-001_*.jsonl")
    logger.info(f"  原始字节 → logs/driver_TRAIN-001_*_raw.txt")
    logger.info("=" * 60)

    # ── 定时打印统计 ───────────────────────────────────────────────────
    def print_stats():
        while True:
            time.sleep(10)
            s = source.status()
            msg = (
                f"[统计] recv={s['recv_count']} "
                f"dropped={s['drop_count']} "
                f"errors={s['error_count']} "
                f"connected={s['connected']}"
            )
            if _silent_mode:
                # --send 模式：统计只写日志文件，不打印到控制台
                logger.info(msg)
            else:
                logger.info(msg)   # 普通模式：同时打控制台和文件

    stats_thread = threading.Thread(target=print_stats, daemon=True)
    stats_thread.start()

    # ── 交互式发送（在独立线程里读 stdin，不阻塞接收） ─────────────────
    if args.send:
        global _silent_mode
        _silent_mode = True   # 接收侧不再 print，控制台留给发送交互

        # 把控制台 handler 调成 WARNING 级，INFO/DEBUG 只写文件，不刷屏
        for h in logging.getLogger().handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
                h.setLevel(logging.WARNING)

        logger.info("--send 模式：控制台已静默（WARNING 以下只写文件），专用于发送命令交互")
        send_thread = threading.Thread(
            target=_send_loop, args=(source,), daemon=True
        )
        send_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到 Ctrl+C，正在停止...")
    finally:
        source.stop()
        bus.stop()
        logger.info("已停止，日志已保存")


# ── 交互式发送命令循环 ─────────────────────────────────────────────────
SEND_HELP = """
发送命令（回车执行）：
  speed <值>          设置车辆速度 km/h，例：speed 45.5
  ato <on|off>        激活/关闭 ATO 标志
  ato_cap <on|off>    具备/不具备 ATO 标志
  door_close <on|off> 门关好指示灯
  door_open <on|off>  开门灯
  net_fault <on|off>  网络故障指示灯
  high_v <on|off>     高断合指示灯
  brake_bad <on|off>  制动缓解不良指示灯
  auto_rev <on|off>   具备自动折返模式标志
  auto_rev_act<on|off>激活自动折返模式标志
  wash <on|off>       进入洗车模式标志
  send                按当前参数立即发送一帧
  auto <秒>           自动每隔 N 秒发送一帧（例：auto 0.5）
  auto off            停止自动发送
  status              显示当前待发参数
  help                显示此帮助
  quit / q            退出
"""

def _send_loop(source: DriverDeskSource):
    """在独立线程里接受用户输入，手动触发 send_to_plc()"""
    # 当前待发参数（每次 send 都用这组值）
    params = {
        "vehicle_speed_kmh":   0.0,
        "high_voltage_on":     False,
        "brake_bad_light":     False,
        "door_open_light":     False,
        "door_closed_light":   False,
        "network_fault":       False,
        "auto_reverse_cap":    False,
        "ato_capable":         False,
        "wash_mode_status":    False,
        "ato_active":          False,
        "auto_reverse_active": False,
    }

    auto_interval = None          # None = 不自动发
    auto_stop     = threading.Event()

    def start_auto(interval: float):
        nonlocal auto_interval
        auto_stop.clear()
        auto_interval = interval

        def _auto():
            while not auto_stop.is_set():
                _do_send()
                auto_stop.wait(interval)

        threading.Thread(target=_auto, daemon=True, name="AutoSend").start()
        print(f"[发送] 自动发送已启动，间隔 {interval}s")

    def stop_auto():
        auto_stop.set()
        print("[发送] 自动发送已停止")

    def _do_send():
        source.send_to_plc(**params)
        print(
            f"[发送→PLC] speed={params['vehicle_speed_kmh']:.1f}km/h "
            f"ato={int(params['ato_active'])} "
            f"ato_cap={int(params['ato_capable'])} "
            f"door_closed={int(params['door_closed_light'])} "
            f"door_open={int(params['door_open_light'])} "
            f"net_fault={int(params['network_fault'])} "
            f"high_v={int(params['high_voltage_on'])} "
            f"brake_bad={int(params['brake_bad_light'])} "
            f"auto_rev={int(params['auto_reverse_cap'])} "
            f"auto_rev_act={int(params['auto_reverse_active'])} "
            f"wash={int(params['wash_mode_status'])}"
        )

    def _parse_bool(s: str) -> bool:
        return s.lower() in ("on", "1", "true", "yes")

    print(SEND_HELP)
    print("[发送模式已启用] 等待 PLC 连接后再发送...")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue

        parts = line.split()
        cmd   = parts[0].lower()

        try:
            if cmd == "help":
                print(SEND_HELP)
            elif cmd in ("quit", "q"):
                break
            elif cmd == "status":
                print("[当前发送参数]")
                for k, v in params.items():
                    print(f"  {k} = {v}")
            elif cmd == "send":
                if not source._connected:
                    print("[警告] PLC 未连接，发送无效")
                else:
                    _do_send()
            elif cmd == "auto":
                if len(parts) < 2:
                    print("用法：auto <秒> 或 auto off")
                elif parts[1].lower() == "off":
                    stop_auto()
                else:
                    start_auto(float(parts[1]))
            elif cmd == "speed":
                params["vehicle_speed_kmh"] = float(parts[1])
                print(f"  speed → {params['vehicle_speed_kmh']} km/h")
            elif cmd == "ato":
                params["ato_active"] = _parse_bool(parts[1])
                print(f"  ato_active → {params['ato_active']}")
            elif cmd == "ato_cap":
                params["ato_capable"] = _parse_bool(parts[1])
                print(f"  ato_capable → {params['ato_capable']}")
            elif cmd == "door_close":
                params["door_closed_light"] = _parse_bool(parts[1])
                print(f"  door_closed_light → {params['door_closed_light']}")
            elif cmd == "door_open":
                params["door_open_light"] = _parse_bool(parts[1])
                print(f"  door_open_light → {params['door_open_light']}")
            elif cmd == "net_fault":
                params["network_fault"] = _parse_bool(parts[1])
                print(f"  network_fault → {params['network_fault']}")
            elif cmd == "high_v":
                params["high_voltage_on"] = _parse_bool(parts[1])
                print(f"  high_voltage_on → {params['high_voltage_on']}")
            elif cmd == "brake_bad":
                params["brake_bad_light"] = _parse_bool(parts[1])
                print(f"  brake_bad_light → {params['brake_bad_light']}")
            elif cmd == "auto_rev":
                params["auto_reverse_cap"] = _parse_bool(parts[1])
                print(f"  auto_reverse_cap → {params['auto_reverse_cap']}")
            elif cmd == "auto_rev_act":
                params["auto_reverse_active"] = _parse_bool(parts[1])
                print(f"  auto_reverse_active → {params['auto_reverse_active']}")
            elif cmd == "wash":
                params["wash_mode_status"] = _parse_bool(parts[1])
                print(f"  wash_mode_status → {params['wash_mode_status']}")
            else:
                print(f"未知命令：{cmd}，输入 help 查看帮助")
        except (IndexError, ValueError) as e:
            print(f"参数错误：{e}")


if __name__ == "__main__":
    main()
