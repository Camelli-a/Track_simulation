"""
视景系统 UDP 发送模块（ATS → 视景控制机）

协议依据：北京地铁9号线 TCMS2VIEW 通信包 Version 1.3

角色说明：
    - 本模块是发送方（ATS 仿真机），视景控制机是接收方
    - 视景控制机无回包，单向发送
    - 发送周期：100ms
    - 协议层：UDP 单播

网络配置（来自协议文档）：
    ATS 仿真机    IP: 18.32.115.27  发送端口: 8302  接收端口: 8303
    视景控制机    IP: 18.32.115.28  发送端口: 8302  接收端口: 8303
    → 本模块从 ATS 仿真机的 8302 端口发送，目标是 18.32.115.28:8303

帧结构（strTCMS2VIEW）：
    字段                类型        字节数      说明
    LiveCounter         int32       4           数据报计数，每发一包自增1
    Signal_num          int8        1           信号机数量，固定 SIGNAL_COUNT=77
    SignalStates[77]    uint8×77    77          信号机状态，按表2顺序排列
    Switch_num          int8        1           道岔数量，固定 SWITCH_COUNT=29
    SwitchStates[29]    uint8×29    29          道岔状态，按表3顺序排列
    Speed               int32       4           本车车速，毫米/秒（≤33333有效）
    DwellTime           int16       2           发车时间，0~XXX秒
    RunState            int8        1           运行工况/头灯控制
    Accel               int8        1           加速度 0~64(百分比)，100对应1.1m/s²
    SectionDistance     int32       4           本车车头位置，mm，相对起点道岔
    EdgeID              int16       2           本车车头边号（区段号）
    SectionDirection    int8        1           本车运行方向，+1=正，-1=反
    conTrain_num        int8        1           他车数量 L
    conSectionDistance  int32×128   512         他车距离，mm
    conEdgeID           int16×128   256         他车边号
    conSectionDirection int8×128    128         他车方向
    conSpeed            int16×128   256         他车车速，厘米/秒

    合计固定部分：4+1+77+1+29+4+2+1+1+4+2+1+1 = 128 字节
    他车部分：512+256+128+256 = 1152 字节（FXTrain_MAX=128 项，全量打包）
    总计：128 + 1152 = 1280 字节

信号机状态编码（协议表2 说明）：
    0x00 = 灭灯
    0x01 = 红灯
    0x02 = 绿灯
    0x04 = 白灯
    0x10 = 黄灯
    0x40 = 蓝灯
    0x11 = 红黄（引导）

道岔状态编码：
    0x01 = 定位
    0x02 = 反位
    其他 = 无效，视景默认显示定位

运行工况/头灯（RunState）：
    0x11 = 牵引
    0x12 = 制动
    0x13 = 惰行
    0x00 = 头灯关
    0x01 = 头灯低亮
    0x02 = 头灯高亮

使用方式：
    source = ScenerySource()
    source.start()
    # 其他模块更新状态：
    source.update_own_train(speed_mmps=8333, section_distance_mm=12000, edge_id=101, direction=1)
    source.update_signal(index=0, state=0x02)   # 第1个信号机绿灯
    source.update_switch(index=0, state=0x01)   # 第1个道岔定位
    source.stop()
"""

import socket
import struct
import threading
import logging
import time
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 协议常量（北京地铁9号线 Version 1.3）
# ------------------------------------------------------------------
SIGNAL_COUNT  = 77     # 正线信号机数量（表2）
SWITCH_COUNT  = 29     # 正线道岔数量（表3）
TRAIN_MAX     = 128    # 他车数组最大容量（FXTrain_MAX）

MAX_SPEED_MMPS = 33333  # 超过此值视景系统认为无效

# 信号机状态
SIG_OFF       = 0x00
SIG_RED       = 0x01
SIG_GREEN     = 0x02
SIG_WHITE     = 0x04
SIG_YELLOW    = 0x10
SIG_BLUE      = 0x40
SIG_RED_YELLOW = 0x11   # 引导

# 道岔状态
SW_NORMAL  = 0x01   # 定位
SW_REVERSE = 0x02   # 反位

# 运行工况/头灯
RUN_TRACTION  = 0x11
RUN_BRAKING   = 0x12
RUN_COASTING  = 0x13
HEAD_LIGHT_OFF   = 0x00
HEAD_LIGHT_LOW   = 0x01
HEAD_LIGHT_HIGH  = 0x02

# ------------------------------------------------------------------
# struct 格式（小端 <）
#
# 固定头部（128字节）：
#   i  = int32  LiveCounter        [0:4]
#   b  = int8   Signal_num         [4]
#   77s= bytes  SignalStates[77]   [5:82]
#   b  = int8   Switch_num         [82]
#   29s= bytes  SwitchStates[29]   [83:112]
#   i  = int32  Speed              [112:116]
#   h  = int16  DwellTime          [116:118]
#   b  = int8   RunState           [118]
#   b  = int8   Accel              [119]
#   i  = int32  SectionDistance    [120:124]
#   h  = int16  EdgeID             [124:126]
#   b  = int8   SectionDirection   [126]
#   b  = int8   conTrain_num       [127]
#
# 他车部分（1152字节，TRAIN_MAX=128）：
#   128i = int32×128  conSectionDistance  [128:640]
#   128h = int16×128  conEdgeID           [640:896]
#   128b = int8×128   conSectionDirection [896:1024]
#   128h = int16×128  conSpeed            [1024:1280]
# ------------------------------------------------------------------
_HEADER_FMT  = "<ib77sb29sihbbihbb"
_TRAIN_FMT   = f"128i{TRAIN_MAX}h{TRAIN_MAX}b{TRAIN_MAX}h"

# 最小帧长（L=0，无他车）
FRAME_MIN_LEN = (
    4               # LiveCounter
    + 1 + SIGNAL_COUNT   # Signal_num + SignalStates
    + 1 + SWITCH_COUNT   # Switch_num + SwitchStates
    + 4              # Speed
    + 2              # DwellTime
    + 1              # RunState
    + 1              # Accel
    + 4              # SectionDistance
    + 2              # EdgeID
    + 1              # SectionDirection
    + 1              # conTrain_num
)  # = 128 字节
assert FRAME_MIN_LEN == 128, f"FRAME_MIN_LEN={FRAME_MIN_LEN}"


class ScenerySource:
    """
    视景系统 UDP 发送器

    职责：
    1. 每 100ms 组装一帧 strTCMS2VIEW（1280字节）
    2. 通过 UDP 发送给视景控制机
    3. 对外暴露 update_* 方法，供其他模块（车辆算法、信号模块）更新状态

    线程安全：所有 update_* 方法可从任意线程调用，内部用锁保护状态。
    """

    def __init__(
        self,
        scenery_host: str = None,
        scenery_port: int = None,
        local_host:   str = "0.0.0.0",
        local_port:   int = None,
        send_interval: float = 0.1,       # 100ms
    ):
        self.scenery_host   = scenery_host or getattr(settings, "SCENERY_HOST", "18.32.115.28")
        self.scenery_port   = scenery_port or getattr(settings, "SCENERY_PORT", 8303)
        self.local_host     = local_host
        self.local_port     = local_port   or getattr(settings, "SCENERY_LOCAL_PORT", 8302)
        self.send_interval  = send_interval

        self._lock = threading.Lock()

        # ── 状态缓存（所有 update_* 方法写这里，发送循环读这里）──────
        self._live_counter    = 0

        # 信号机状态：按表2序号排列，默认全灭
        self._signal_states   = bytearray(SIGNAL_COUNT)   # index 0..76

        # 道岔状态：按表3序号排列，默认定位
        self._switch_states   = bytearray([SW_NORMAL] * SWITCH_COUNT)  # index 0..28

        # 本车状态
        self._speed_mmps      = 0          # 毫米/秒
        self._dwell_time      = 0          # 发车时间（秒）
        self._run_state       = RUN_COASTING  # 默认惰行
        self._accel           = 50         # 0~64(百分比)，50=约50%
        self._section_dist    = 0          # 车头位置，mm
        self._edge_id         = 0          # 边号/区段号
        self._direction       = 1          # +1=正方向

        # 他车列表（最多 TRAIN_MAX 辆）
        # 每辆：{"dist_mm": int, "edge_id": int, "direction": int, "speed_cmps": int}
        self._other_trains: list[dict] = []

        # 运行控制
        self._running     = False
        self._sock: Optional[socket.socket] = None
        self._send_thread: Optional[threading.Thread] = None

        # 统计
        self._send_count  = 0
        self._error_count = 0

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self):
        if self._running:
            logger.warning("ScenerySource already running")
            return

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.local_host, self.local_port))
        self._running = True

        self._send_thread = threading.Thread(
            target=self._send_loop,
            daemon=True,
            name="ScenerySource",
        )
        self._send_thread.start()
        logger.info(
            f"ScenerySource started: "
            f"{self.local_host}:{self.local_port} → "
            f"{self.scenery_host}:{self.scenery_port}  "
            f"interval={self.send_interval*1000:.0f}ms"
        )

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._send_thread:
            self._send_thread.join(timeout=3)
            self._send_thread = None
        logger.info(
            f"ScenerySource stopped "
            f"(sent={self._send_count}, errors={self._error_count})"
        )

    def status(self) -> dict:
        return {
            "running":      self._running,
            "target":       f"{self.scenery_host}:{self.scenery_port}",
            "send_count":   self._send_count,
            "error_count":  self._error_count,
            "live_counter": self._live_counter,
        }

    def get_state(self) -> dict:
        """返回当前发送状态快照，供调试脚本读取当前值"""
        with self._lock:
            return {
                "speed_mmps":    self._speed_mmps,
                "section_dist":  self._section_dist,
                "edge_id":       self._edge_id,
                "direction":     self._direction,
                "run_state":     self._run_state,
                "accel":         self._accel,
                "dwell_time":    self._dwell_time,
                "other_trains":  len(self._other_trains),
            }

    # ------------------------------------------------------------------
    # 状态更新接口（供车辆算法、信号模块调用，线程安全）
    # ------------------------------------------------------------------

    def update_own_train(
        self,
        speed_mmps: int,
        section_distance_mm: int,
        edge_id: int,
        direction: int,
        run_state: int = None,
        accel: int = None,
        dwell_time: int = 0,
    ):
        """
        更新本车状态

        Args:
            speed_mmps:          车速，毫米/秒（协议要求 ≤33333 有效）
            section_distance_mm: 车头位置，mm，相对起点道岔
            edge_id:             边号/区段号
            direction:           运行方向，+1=正，-1=反
            run_state:           运行工况，使用模块常量 RUN_TRACTION/RUN_BRAKING/RUN_COASTING
            accel:               加速度百分比 0~64（100对应1.1m/s²）
            dwell_time:          发车时间（秒），0=无效
        """
        with self._lock:
            self._speed_mmps   = max(0, min(speed_mmps, MAX_SPEED_MMPS))
            self._section_dist = section_distance_mm
            self._edge_id      = edge_id
            self._direction    = direction
            if run_state is not None:
                self._run_state = run_state
            if accel is not None:
                self._accel = max(0, min(accel, 127))
            self._dwell_time = dwell_time

    def update_signal(self, index: int, state: int):
        """
        更新单个信号机状态

        Args:
            index: 信号机序号（0-based，对应协议表2的序号-1）
            state: 信号状态，使用模块常量 SIG_RED/SIG_GREEN 等
        """
        if not (0 <= index < SIGNAL_COUNT):
            logger.warning(f"update_signal: index {index} out of range [0, {SIGNAL_COUNT})")
            return
        with self._lock:
            self._signal_states[index] = state & 0xFF

    def update_signals_batch(self, states: list[int]):
        """
        批量更新所有信号机状态

        Args:
            states: 长度为 SIGNAL_COUNT(77) 的列表，按表2序号排列
        """
        if len(states) != SIGNAL_COUNT:
            logger.warning(f"update_signals_batch: expected {SIGNAL_COUNT} items, got {len(states)}")
            return
        with self._lock:
            for i, s in enumerate(states):
                self._signal_states[i] = s & 0xFF

    def update_switch(self, index: int, state: int):
        """
        更新单个道岔状态

        Args:
            index: 道岔序号（0-based，对应协议表3的序号-1）
            state: SW_NORMAL(0x01)=定位 或 SW_REVERSE(0x02)=反位
        """
        if not (0 <= index < SWITCH_COUNT):
            logger.warning(f"update_switch: index {index} out of range [0, {SWITCH_COUNT})")
            return
        with self._lock:
            self._switch_states[index] = state & 0xFF

    def update_switches_batch(self, states: list[int]):
        """
        批量更新所有道岔状态

        Args:
            states: 长度为 SWITCH_COUNT(29) 的列表，按表3序号排列
        """
        if len(states) != SWITCH_COUNT:
            logger.warning(f"update_switches_batch: expected {SWITCH_COUNT} items, got {len(states)}")
            return
        with self._lock:
            for i, s in enumerate(states):
                self._switch_states[i] = s & 0xFF

    def update_other_trains(self, trains: list[dict]):
        """
        更新他车列表

        Args:
            trains: 他车信息列表，每项为：
                {
                    "dist_mm":    int,  # 位置距离，mm
                    "edge_id":    int,  # 边号
                    "direction":  int,  # 方向 +1/-1
                    "speed_cmps": int,  # 车速，厘米/秒
                }
                最多 TRAIN_MAX(128) 辆，超出部分忽略
        """
        with self._lock:
            self._other_trains = trains[:TRAIN_MAX]

    # ------------------------------------------------------------------
    # 发送循环（后台线程）
    # ------------------------------------------------------------------

    def _send_loop(self):
        logger.info("ScenerySource send loop started")
        next_send = time.monotonic()

        while self._running:
            now = time.monotonic()
            if now >= next_send:
                self._send_once()
                next_send += self.send_interval
                # 如果发送耗时超过周期，避免补发堆积
                if time.monotonic() > next_send:
                    next_send = time.monotonic() + self.send_interval
            else:
                time.sleep(max(0, next_send - time.monotonic()))

        logger.info("ScenerySource send loop stopped")

    def _send_once(self):
        """组装并发送一帧（变长，按协议表1实际字段顺序打包）"""
        with self._lock:
            live_counter   = self._live_counter
            signal_states  = bytes(self._signal_states)
            switch_states  = bytes(self._switch_states)
            speed          = self._speed_mmps
            dwell_time     = self._dwell_time
            run_state      = self._run_state
            accel          = self._accel
            section_dist   = self._section_dist
            edge_id        = self._edge_id
            direction      = self._direction
            other_trains   = list(self._other_trains)
            self._live_counter += 1

        n = len(other_trains)   # 实际他车数量，决定帧长

        # ── 按协议表1顺序逐段打包，变长 ──────────────────────────────
        try:
            buf = bytearray()

            # 序号1：数据报计数（4字节 int32）
            buf += struct.pack("<i", live_counter)

            # 序号2：信号机个数 + N个状态
            buf += struct.pack("b", SIGNAL_COUNT)
            buf += signal_states                    # 77字节

            # 序号3：道岔个数 + M个状态
            buf += struct.pack("b", SWITCH_COUNT)
            buf += switch_states                    # 29字节

            # 序号4：本车车速（4字节 int32，mm/s）
            buf += struct.pack("<i", speed)

            # 序号5：发车时间（2字节 int16）
            buf += struct.pack("<h", dwell_time)

            # 序号6：运行工况/头灯（1字节）
            buf += struct.pack("b", run_state)

            # 序号7：加速度（1字节）
            buf += struct.pack("b", accel)

            # 序号8：车头位置（4字节 int32，mm）
            buf += struct.pack("<i", section_dist)

            # 序号9：车头边号（2字节 int16）
            buf += struct.pack("<h", edge_id)

            # 序号10：本车方向（1字节，+1=正，-1=反）
            buf += struct.pack("b", direction)

            # 序号11：他车数量（1字节）
            buf += struct.pack("b", n)

            # 序号12：他车信息（变长，4*L + 2*L + 1*L + 2*L 字节）
            for t in other_trains:
                buf += struct.pack("<i", t.get("dist_mm", 0))       # 4字节 距离
            for t in other_trains:
                buf += struct.pack("<h", t.get("edge_id", 0))       # 2字节 边号
            for t in other_trains:
                buf += struct.pack("b",  t.get("direction", 0))     # 1字节 方向
            for t in other_trains:
                buf += struct.pack("<h", t.get("speed_cmps", 0))    # 2字节 车速cm/s

            payload = bytes(buf)

        except struct.error as e:
            logger.error(f"ScenerySource pack error: {e}")
            self._error_count += 1
            return

        # L=0 时帧长应为 128 字节
        expected_min = 4 + 1 + SIGNAL_COUNT + 1 + SWITCH_COUNT + 4 + 2 + 1 + 1 + 4 + 2 + 1 + 1
        logger.debug(
            f"[Scenery] sent #{live_counter}  "
            f"speed={speed}mm/s  dist={section_dist}mm  "
            f"edge={edge_id}  dir={direction}  "
            f"trains={n}  frame={len(payload)}B (min={expected_min})"
        )

        try:
            self._sock.sendto(payload, (self.scenery_host, self.scenery_port))
            self._send_count += 1
        except OSError as e:
            logger.error(f"ScenerySource sendto error: {e}")
            self._error_count += 1
