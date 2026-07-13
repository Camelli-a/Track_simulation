"""
视景系统 UDP 调试脚本
======================
用途：明天硬件联调时验证视景通信，不依赖完整后端。

使用方式：
    python debug_scenery.py
    python debug_scenery.py --host 18.32.115.28 --port 8303

启动后进入交互模式，手动输入命令控制发送内容，观察视景系统响应。

命令列表见启动后的 help 输出。
"""
import argparse
import logging
import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.communication.scenery_source import (
    ScenerySource,
    SIG_OFF, SIG_RED, SIG_GREEN, SIG_WHITE, SIG_YELLOW, SIG_BLUE, SIG_RED_YELLOW,
    SW_NORMAL, SW_REVERSE,
    RUN_TRACTION, RUN_BRAKING, RUN_COASTING,
    HEAD_LIGHT_OFF, HEAD_LIGHT_LOW, HEAD_LIGHT_HIGH,
    SIGNAL_COUNT, SWITCH_COUNT,
)

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            Path("logs") / f"scenery_{time.strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("debug_scenery")

HELP = """
命令列表：
  speed <mm/s>              本车车速，毫米/秒（≤33333有效）例：speed 8333
  pos <mm> <edge> <dir>     本车位置，例：pos 12000 101 1
  run <traction|braking|coasting|light_off|light_low|light_high>
  accel <0-127>             加速度百分比
  dwell <秒>                发车时间

  sig <index> <状态>        设置信号机，index从1开始，状态：off/red/green/white/yellow/blue/redyellow
  sig_all <状态>            所有信号机设成同一状态
  sw <index> <normal|reverse>  设置道岔，index从1开始
  sw_all <normal|reverse>   所有道岔设成同一状态

  auto <on|off>             开关自动发送（默认已开启）
  interval <秒>             修改发送间隔，例：interval 0.1
  status                    显示当前状态
  help                      显示此帮助
  quit / q                  退出
"""

SIG_MAP = {
    "off": SIG_OFF, "red": SIG_RED, "green": SIG_GREEN,
    "white": SIG_WHITE, "yellow": SIG_YELLOW, "blue": SIG_BLUE,
    "redyellow": SIG_RED_YELLOW,
}
RUN_MAP = {
    "traction": RUN_TRACTION, "braking": RUN_BRAKING, "coasting": RUN_COASTING,
    "light_off": HEAD_LIGHT_OFF, "light_low": HEAD_LIGHT_LOW, "light_high": HEAD_LIGHT_HIGH,
}


def main():
    parser = argparse.ArgumentParser(description="视景系统 UDP 调试脚本")
    parser.add_argument("--host",  default=None, help="视景控制机 IP")
    parser.add_argument("--port",  default=None, type=int, help="视景控制机接收端口")
    parser.add_argument("--local-port", default=8302, type=int, help="本机发送端口")
    args = parser.parse_args()

    source = ScenerySource(
        scenery_host=args.host,
        scenery_port=args.port,
        local_port=args.local_port,
    )
    source.start()

    # 统计线程——只写日志文件，不打控制台，避免遮挡输入提示符
    console_handler = None
    for h in logging.getLogger().handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            console_handler = h
            break
    if console_handler:
        console_handler.setLevel(logging.WARNING)

    def _stats():
        while True:
            time.sleep(10)
            s = source.status()
            logger.info(f"[统计] sent={s['send_count']} errors={s['error_count']} counter={s['live_counter']}")

    threading.Thread(target=_stats, daemon=True).start()

    print(HELP)
    print(f"目标：{source.scenery_host}:{source.scenery_port}  本机发送端口：{source.local_port}")
    print("已开始每 100ms 自动发送，输入命令修改发送内容")

    try:
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            parts = line.split()
            cmd = parts[0].lower()

            try:
                if cmd in ("quit", "q"):
                    break
                elif cmd == "help":
                    print(HELP)
                elif cmd == "status":
                    s = source.status()
                    for k, v in s.items():
                        print(f"  {k} = {v}")
                elif cmd == "speed":
                    v = int(parts[1])
                    st = source.get_state()
                    source.update_own_train(
                        speed_mmps=v,
                        section_distance_mm=st["section_dist"],
                        edge_id=st["edge_id"],
                        direction=st["direction"],
                    )
                    print(f"  speed → {v} mm/s  ({v/1000*3.6:.1f} km/h)")
                elif cmd == "pos":
                    mm, edge, d = int(parts[1]), int(parts[2]), int(parts[3])
                    st = source.get_state()
                    source.update_own_train(
                        speed_mmps=st["speed_mmps"],
                        section_distance_mm=mm,
                        edge_id=edge,
                        direction=d,
                    )
                    print(f"  pos → dist={mm}mm  edge={edge}  dir={d}")
                elif cmd == "run":
                    rs = RUN_MAP.get(parts[1].lower())
                    if rs is None:
                        print(f"  未知工况：{parts[1]}，可选：{list(RUN_MAP)}")
                    else:
                        st = source.get_state()
                        source.update_own_train(
                            speed_mmps=st["speed_mmps"],
                            section_distance_mm=st["section_dist"],
                            edge_id=st["edge_id"],
                            direction=st["direction"],
                            run_state=rs,
                        )
                        print(f"  run_state → 0x{rs:02X} ({parts[1]})")
                elif cmd == "accel":
                    st = source.get_state()
                    source.update_own_train(
                        speed_mmps=st["speed_mmps"],
                        section_distance_mm=st["section_dist"],
                        edge_id=st["edge_id"],
                        direction=st["direction"],
                        accel=int(parts[1]),
                    )
                    print(f"  accel → {parts[1]}")
                elif cmd == "dwell":
                    st = source.get_state()
                    source.update_own_train(
                        speed_mmps=st["speed_mmps"],
                        section_distance_mm=st["section_dist"],
                        edge_id=st["edge_id"],
                        direction=st["direction"],
                        dwell_time=int(parts[1]),
                    )
                    print(f"  dwell_time → {parts[1]}s")
                elif cmd == "sig":
                    idx  = int(parts[1]) - 1   # 用户输入1-based，内部0-based
                    st   = SIG_MAP.get(parts[2].lower())
                    if st is None:
                        print(f"  未知状态：{parts[2]}，可选：{list(SIG_MAP)}")
                    else:
                        source.update_signal(idx, st)
                        print(f"  signal[{idx+1}] → 0x{st:02X} ({parts[2]})")
                elif cmd == "sig_all":
                    st = SIG_MAP.get(parts[1].lower())
                    if st is None:
                        print(f"  未知状态：{parts[1]}，可选：{list(SIG_MAP)}")
                    else:
                        source.update_signals_batch([st] * SIGNAL_COUNT)
                        print(f"  all {SIGNAL_COUNT} signals → 0x{st:02X} ({parts[1]})")
                elif cmd == "sw":
                    idx = int(parts[1]) - 1
                    st  = SW_NORMAL if parts[2].lower() == "normal" else SW_REVERSE
                    source.update_switch(idx, st)
                    print(f"  switch[{idx+1}] → {'定位' if st == SW_NORMAL else '反位'}")
                elif cmd == "sw_all":
                    st = SW_NORMAL if parts[1].lower() == "normal" else SW_REVERSE
                    source.update_switches_batch([st] * SWITCH_COUNT)
                    print(f"  all {SWITCH_COUNT} switches → {'定位' if st == SW_NORMAL else '反位'}")
                elif cmd == "interval":
                    source.send_interval = float(parts[1])
                    print(f"  send_interval → {source.send_interval}s")
                else:
                    print(f"未知命令：{cmd}，输入 help 查看帮助")
            except (IndexError, ValueError) as e:
                print(f"参数错误：{e}")

    except KeyboardInterrupt:
        pass
    finally:
        source.stop()
        logger.info("已停止")


if __name__ == "__main__":
    main()
