"""
司机台数据源（TCP 客户端）

严格依据《司机驾驶模拟台PLC协议》7.1节定义帧结构。

协议说明：
    - PLC 作为 TCP Server，本模块作为 Client 主动连接
    - PLC 以 100ms 周期持续推送 46 字节定长报文
    - 字节序：小端（Little Endian）
    - 帧头：原始字节 AA 55 AA 55，小端 DWORD 解析后 = 0x55AA55AA

帧结构（46字节，7.1节完整定义）：
    序号  字节偏移  位偏移  类型   字段名/说明
     1    0        0      DWORD  _uIdentify       AA 55 AA 55
     2    4        0      WORD   _uTotalLen       00 2E = 46
     3    6        0      WORD   _uDataLen        00 16 = 22
     4    8        0      WORD   _uYear
     5    10       0      WORD   _uMonth
     6    12       0      WORD   _uDay
     7    14       0      WORD   _uHour
     8    16       0      WORD   _uMinute
     9    18       0      WORD   _uSecond
    10    20       0      WORD   _uVerifyType
    11    22       0      WORD   _uVerifyCode
    12    24       0      BOOL   预留
    13    24       1      BOOL   高断合指示灯状态
    14    24       2      BOOL   制动缓解不良指示灯状态
    15    24       3      BOOL   预留
    16    24       4      BOOL   预留
    17    24       5      BOOL   门关好指示灯状态
    18    24       6      BOOL   网络故障指示灯状态
    19    24       7      BOOL   具备自动折返模式标志
    20    25       0      BOOL   具备ATO模式标志
    21    25       1      BOOL   进入洗车模式标志（状态）
    22    25       2      BOOL   激活ATO模式标志
    23    25       3      BOOL   激活自动折返模式标志
    24    25       4      BOOL   预留
    25    25       5      BOOL   预留
    26    25       6      BOOL   预留
    27    25       7      BOOL   预留
    28    26       0      WORD   车辆速度（上位机回显）
    29    28       0      BOOL   紧急制动按钮状态
    30    28       1      BOOL   母线控制按钮状态
    31    28       2      BOOL   强迫缓解标志
    32    28       3      BOOL   强迫泵风标志
    33    28       4      BOOL   应急指挥按钮状态
    34    28       5      BOOL   停放制动施加标志
    35    28       6      BOOL   停放制动缓解标志
    36    28       7      BOOL   电笛标志
    37    29       0      BOOL   开左门标志
    38    29       1      BOOL   开右门标志
    39    29       2      BOOL   关左门标志
    40    29       3      BOOL   关右门标志
    41    29       4      BOOL   预留
    42    29       5      BOOL   预留
    43    29       6      BOOL   预留
    44    29       7      BOOL   预留
    45    30       0      WORD   外部照明开关状态  0=停止 1=自动 2=近光 4=远光
    46    32       0      WORD   门模式开关状态    0=半自动 1=手动 2=自动
    47    34       0      BOOL   高加速按钮状态
    48    34       1      BOOL   司机室照明开关状态
    49    34       2      BOOL   模式升级确认标志
    50    34       3      BOOL   模式降级确认标志
    51    34       4      BOOL   确认标志
    52    34       5      BOOL   自动折返标志
    53    34       6      BOOL   牵引辅助复位标志
    54    34       7      BOOL   ATO启动标志
    55    35       0      BOOL   洗车模式开关状态
    56    35       1      BOOL   钥匙开关状态
    57    35       2      BOOL   警惕标志
    58    35       3      BOOL   警惕允许解除标志
    59    35       4      BOOL   预留
    60    35       5      BOOL   预留
    61    35       6      BOOL   预留
    62    35       7      BOOL   预留
    63    36       0      WORD   方向手柄状态  0=0位 1=向前 2=向后
    64    38       0      WORD   主手柄状态    0=0位 1=牵引 2=制动 4=快制
    65    40       0      WORD   牵引极位      最大牵引力百分比
    66    42       0      WORD   制动极位      最大制动力百分比
    67    44       0      WORD   预留
"""
import json
import socket
import struct
import threading
import logging
import time
from pathlib import Path
from typing import Optional
from app.communication.message_bus import MessageBus
from app.core.config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 协议常量
# ------------------------------------------------------------------
FRAME_LEN   = 46
# PLC 下行帧头：原始字节 AA 55 AA 55，小端 DWORD = 0x55AA55AA
FRAME_MAGIC = 0x55AA55AA

# 主手柄状态（序号64）
MAIN_HANDLE_COAST = 0   # 0位（惰行/无操作）
MAIN_HANDLE_TRAC  = 1   # 牵引
MAIN_HANDLE_BRAKE = 2   # 制动
MAIN_HANDLE_FAST  = 4   # 快制

# 方向手柄状态（序号63）
DIR_NEUTRAL = 0
DIR_FORWARD = 1
DIR_REVERSE = 2
DIR_MAP = {DIR_NEUTRAL: "neutral", DIR_FORWARD: "forward", DIR_REVERSE: "backward"}

# 门模式（序号46）
DOOR_MODE_MAP = {0: "semi_auto", 1: "manual", 2: "auto"}

# 外部照明（序号45）
LIGHT_MAP = {0: "off", 1: "auto", 2: "low_beam", 4: "high_beam"}

# ------------------------------------------------------------------
# struct 格式（小端 <），25个字段，合计 46 字节
#
#  偏移  格式  字节数  f[]索引  字段
#   0    I     4       [0]    _uIdentify
#   4    H     2       [1]    _uTotalLen
#   6    H     2       [2]    _uDataLen
#   8    H     2       [3]    _uYear
#  10    H     2       [4]    _uMonth
#  12    H     2       [5]    _uDay
#  14    H     2       [6]    _uHour
#  16    H     2       [7]    _uMinute
#  18    H     2       [8]    _uSecond
#  20    H     2       [9]    _uVerifyType
#  22    H     2      [10]    _uVerifyCode
#  24    B     1      [11]    byte24（序号12~19，指示灯+折返）
#  25    B     1      [12]    byte25（序号20~27，ATO/洗车模式）
#  26    H     2      [13]    _uVehicleSpeed（序号28，上位机回显速度）
#  28    B     1      [14]    byte28（序号29~36，制动控制）
#  29    B     1      [15]    byte29（序号37~44，车门控制）
#  30    H     2      [16]    _uLightSwitch（序号45，外部照明）
#  32    H     2      [17]    _uDoorMode（序号46，门模式）
#  34    B     1      [18]    byte34（序号47~54，按钮/ATO启动）
#  35    B     1      [19]    byte35（序号55~62，洗车/钥匙/警惕）
#  36    H     2      [20]    _uDirection（序号63，方向手柄）
#  38    H     2      [21]    _uMainHandle（序号64，主手柄）
#  40    H     2      [22]    _uTractionPercent（序号65，牵引极位）
#  42    H     2      [23]    _uBrakePercent（序号66，制动极位）
#  44    H     2      [24]    _uReservedEnd（序号67，预留）
# ------------------------------------------------------------------
FRAME_FMT = "<IHHHHHHHHHHBBHBBHHBBHHHHH"

assert struct.calcsize(FRAME_FMT) == FRAME_LEN, (
    f"FRAME_FMT size mismatch: {struct.calcsize(FRAME_FMT)} != {FRAME_LEN}"
)


class DriverDeskSource:
    """
    司机台 TCP 数据接收器

    职责：
    1. 作为 TCP 客户端连接 PLC（Server）
    2. 持续接收 46 字节定长报文
    3. 校验帧头 → 解析字段 → 发布到 ZMQ 总线
       - 发布 driver_input：司机操作意图（手柄、方向、制动按钮）
    4. 断线自动重连，不影响系统其他部分
    """

    def __init__(
        self,
        vehicle_id: str,
        plc_host: str = None,
        plc_port: int = None,
        bus: MessageBus = None,
        reconnect_interval: float = 3.0,
        record_dir: str = None,          # 传路径则开启持久化，None = 不记录
        record_raw: bool = True,         # 同时保存原始十六进制（用于 Wireshark 对比）
    ):
        self.vehicle_id         = vehicle_id
        self.plc_host           = plc_host or settings.PLC_HOST
        self.plc_port           = plc_port or settings.PLC_PORT
        self.reconnect_interval = reconnect_interval

        self._bus      = bus
        self._owns_bus = bus is None

        self._sock: Optional[socket.socket] = None
        self._running    = False
        self._connected  = False
        self._recv_thread: Optional[threading.Thread] = None

        # 统计
        self._recv_count  = 0
        self._drop_count  = 0
        self._error_count = 0
        self._last_recv_at: Optional[float] = None

        # 持久化
        self._record_raw  = record_raw
        self._jsonl_file  = None   # 解析结果：每行一个 JSON
        self._raw_file    = None   # 原始字节：每行 timestamp|hex
        if record_dir is not None:
            base = Path(record_dir)
            base.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            self._jsonl_file = open(
                base / f"driver_{vehicle_id}_{ts}.jsonl", "w", encoding="utf-8"
            )
            if record_raw:
                self._raw_file = open(
                    base / f"driver_{vehicle_id}_{ts}_raw.txt", "w", encoding="utf-8"
                )
            logger.info(
                f"[{vehicle_id}] Recording to {base / f'driver_{vehicle_id}_{ts}.jsonl'}"
            )

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self):
        if self._running:
            logger.warning(f"[{self.vehicle_id}] DriverDeskSource already running")
            return

        if self._owns_bus:
            self._bus = MessageBus()
            self._bus.start()

        self._running = True
        self._recv_thread = threading.Thread(
            target=self._connect_and_receive,
            daemon=True,
            name=f"DriverDesk-{self.vehicle_id}",
        )
        self._recv_thread.start()
        logger.info(
            f"[{self.vehicle_id}] DriverDeskSource started, "
            f"connecting to PLC {self.plc_host}:{self.plc_port}"
        )

    def stop(self):
        self._running = False
        self._connected = False

        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

        if self._recv_thread:
            self._recv_thread.join(timeout=5)
            self._recv_thread = None

        if self._owns_bus and self._bus:
            self._bus.stop()

        # 关闭持久化文件
        if self._jsonl_file:
            self._jsonl_file.flush()
            self._jsonl_file.close()
            self._jsonl_file = None
        if self._raw_file:
            self._raw_file.flush()
            self._raw_file.close()
            self._raw_file = None

        logger.info(
            f"[{self.vehicle_id}] DriverDeskSource stopped "
            f"(recv={self._recv_count}, dropped={self._drop_count}, "
            f"errors={self._error_count})"
        )

    def status(self) -> dict:
        return {
            "vehicle_id":   self.vehicle_id,
            "running":      self._running,
            "connected":    self._connected,
            "plc":          f"{self.plc_host}:{self.plc_port}",
            "recv_count":   self._recv_count,
            "drop_count":   self._drop_count,
            "error_count":  self._error_count,
            "last_recv_at": self._last_recv_at,
        }

    # ------------------------------------------------------------------
    # 连接 + 接收循环（后台线程）
    # ------------------------------------------------------------------

    def _connect_and_receive(self):
        while self._running:
            try:
                self._do_connect()
                self._receive_loop()
            except Exception as e:
                if self._running:
                    logger.error(
                        f"[{self.vehicle_id}] Connection error: {e}. "
                        f"Reconnecting in {self.reconnect_interval}s..."
                    )
                    self._error_count += 1
            finally:
                self._connected = False
                if self._sock:
                    try:
                        self._sock.close()
                    except OSError:
                        pass
                    self._sock = None

            if self._running:
                time.sleep(self.reconnect_interval)

        logger.info(f"[{self.vehicle_id}] Connect loop exited")

    def _do_connect(self):
        logger.info(f"[{self.vehicle_id}] Connecting to PLC {self.plc_host}:{self.plc_port}...")
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(5.0)
        self._sock.connect((self.plc_host, self.plc_port))
        self._sock.settimeout(2.0)  # PLC 100ms 周期，2秒无数据视为断线
        self._connected = True
        logger.info(f"[{self.vehicle_id}] Connected to PLC")

    def _receive_loop(self):
        logger.info(f"[{self.vehicle_id}] Receive loop started")

        while self._running and self._connected:
            try:
                raw = self._recv_exact(FRAME_LEN)
                if raw is None:
                    break

                self._last_recv_at = time.time()
                self._recv_count += 1

                # ── 持久化原始字节 ─────────────────────────────────────
                if self._raw_file:
                    self._raw_file.write(
                        f"{self._last_recv_at:.6f}|{raw.hex()}\n"
                    )

                parsed = self._parse(raw)
                if parsed is None:
                    self._drop_count += 1
                    continue

                driver_input = parsed

                # ── 持久化解析结果 ─────────────────────────────────────
                if self._jsonl_file:
                    record = {"_ts": self._last_recv_at, **driver_input}
                    self._jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")

                self._bus.publish("driver_input", driver_input)

                self._bus.publish("comm_state", {
                    "source":                   "driver_tcp",
                    "driver_console_connected": True,
                    "zmq_connected":            True,
                    "last_message_at":          self._last_recv_at,
                })

                logger.debug(
                    f"[{self.vehicle_id}] "
                    f"dir={driver_input['direction']} "
                    f"main_handle={driver_input['main_handle_raw']} "
                    f"trac={driver_input['traction_percent']}% "
                    f"brk={driver_input['brake_percent']}% "
                    f"mode={driver_input['control_mode']} "
                    f"eb={driver_input['emergency_button']}"
                )

            except socket.timeout:
                logger.warning(f"[{self.vehicle_id}] Receive timeout, reconnecting...")
                break
            except OSError as e:
                if self._running:
                    logger.error(f"[{self.vehicle_id}] Socket error: {e}")
                break

        logger.info(f"[{self.vehicle_id}] Receive loop stopped")

    def _recv_exact(self, n: int) -> Optional[bytes]:
        """精确接收 n 字节，处理 TCP 粘包/分包"""
        buf = b""
        while len(buf) < n:
            try:
                chunk = self._sock.recv(n - len(buf))
                if not chunk:
                    logger.warning(f"[{self.vehicle_id}] PLC closed the connection")
                    return None
                buf += chunk
            except socket.timeout:
                raise
        return buf

    # ------------------------------------------------------------------
    # 帧解析（严格按 7.1 节）
    # ------------------------------------------------------------------

    def _parse(self, raw: bytes) -> Optional[dict]:
        """
        解析 46 字节下行帧（PLC → 上位机）

        严格按 7.1 节逐位提取，所有字段均有对应说明。

        Returns:
            driver_input dict  解析成功
            None               帧头校验失败，丢弃
        """
        if len(raw) != FRAME_LEN:
            logger.warning(f"[{self.vehicle_id}] Bad frame length: {len(raw)}")
            return None

        try:
            f = struct.unpack(FRAME_FMT, raw)
        except struct.error as e:
            logger.warning(f"[{self.vehicle_id}] unpack failed: {e}")
            return None

        # f 索引见文件头 FRAME_FMT 注释表
        identify       = f[0]
        # f[1] = _uTotalLen，f[2] = _uDataLen（不做强制校验，只记录）
        # f[3..8] = 年月日时分秒（不使用 PLC 时间，以本机时间为准）
        verify_type    = f[9]
        verify_code    = f[10]
        byte24         = f[11]   # 序号12~19：指示灯状态 + 具备自动折返模式标志
        byte25         = f[12]   # 序号20~27：ATO/洗车模式标志
        speed_echo     = f[13]   # 序号28：上位机回显速度（非真实车速）
        byte28         = f[14]   # 序号29~36：制动控制按钮
        byte29         = f[15]   # 序号37~44：车门控制标志
        light_switch   = f[16]   # 序号45：外部照明开关状态
        door_mode_raw  = f[17]   # 序号46：门模式开关状态
        byte34         = f[18]   # 序号47~54：按钮/ATO启动
        byte35         = f[19]   # 序号55~62：洗车/钥匙/警惕
        direction_raw  = f[20]   # 序号63：方向手柄状态
        main_handle    = f[21]   # 序号64：主手柄状态
        traction_pct   = f[22]   # 序号65：牵引极位百分比
        brake_pct      = f[23]   # 序号66：制动极位百分比
        # f[24] = _uReservedEnd（序号67，预留，忽略）

        # ── 帧头校验 ──────────────────────────────────────────────────
        # 7.1节定义下行帧头为 AA 55 AA 55（小端 DWORD = 0x55AA55AA）
        # 实测发现 PLC 发来的是 55 AA 55 AA（小端 DWORD = 0xAA55AA55），
        # 即 7.2节上行帧头的字节序——两种帧头都接受，记录差异供排查。
        FRAME_MAGIC_ALT = 0xAA55AA55   # 实测 PLC 实际使用的帧头
        if identify == FRAME_MAGIC_ALT:
            logger.debug(
                f"[{self.vehicle_id}] Note: received alt magic 0x{identify:08X} "
                f"(PLC using uplink header format, still parsing)"
            )
        elif identify != FRAME_MAGIC:
            logger.warning(
                f"[{self.vehicle_id}] Bad magic: 0x{identify:08X} "
                f"(expected 0x{FRAME_MAGIC:08X} or 0x{FRAME_MAGIC_ALT:08X})"
            )
            return None

        # ── 校验值（_uVerifyCode）：目前仅记录，不做强制校验 ──────────
        if verify_type != 0:
            logger.debug(
                f"[{self.vehicle_id}] verify_type={verify_type} verify_code={verify_code}"
            )

        # ── byte24（字节偏移24）：序号12~19 ───────────────────────────
        # bit0（24.0）预留
        high_voltage_light  = bool((byte24 >> 1) & 1)  # 序号13：高断合指示灯
        brake_bad_light     = bool((byte24 >> 2) & 1)  # 序号14：制动缓解不良指示灯
        # bit3（24.3）预留
        # bit4（24.4）预留
        door_closed_light   = bool((byte24 >> 5) & 1)  # 序号17：门关好指示灯
        network_fault_light = bool((byte24 >> 6) & 1)  # 序号18：网络故障指示灯
        auto_reverse_cap    = bool((byte24 >> 7) & 1)  # 序号19：具备自动折返模式标志

        # ── byte25（字节偏移25）：序号20~27 ───────────────────────────
        ato_capable         = bool((byte25 >> 0) & 1)  # 序号20：具备ATO模式标志
        wash_mode_status    = bool((byte25 >> 1) & 1)  # 序号21：进入洗车模式标志（状态）
        ato_active          = bool((byte25 >> 2) & 1)  # 序号22：激活ATO模式标志
        auto_reverse_active = bool((byte25 >> 3) & 1)  # 序号23：激活自动折返模式标志
        # bit4~7（25.4~25.7）预留

        # ── byte28（字节偏移28）：序号29~36 ───────────────────────────
        emergency_brake  = bool((byte28 >> 0) & 1)  # 序号29：紧急制动按钮状态
        bus_ctrl_btn     = bool((byte28 >> 1) & 1)  # 序号30：母线控制按钮状态
        forced_release   = bool((byte28 >> 2) & 1)  # 序号31：强迫缓解标志
        forced_pump      = bool((byte28 >> 3) & 1)  # 序号32：强迫泵风标志
        emergency_cmd    = bool((byte28 >> 4) & 1)  # 序号33：应急指挥按钮状态
        parking_apply    = bool((byte28 >> 5) & 1)  # 序号34：停放制动施加标志
        parking_release  = bool((byte28 >> 6) & 1)  # 序号35：停放制动缓解标志
        horn             = bool((byte28 >> 7) & 1)  # 序号36：电笛标志

        # ── byte29（字节偏移29）：序号37~44 ───────────────────────────
        open_left_door   = bool((byte29 >> 0) & 1)  # 序号37：开左门标志
        open_right_door  = bool((byte29 >> 1) & 1)  # 序号38：开右门标志
        close_left_door  = bool((byte29 >> 2) & 1)  # 序号39：关左门标志
        close_right_door = bool((byte29 >> 3) & 1)  # 序号40：关右门标志
        # bit4~7（29.4~29.7）预留

        # ── byte34（字节偏移34）：序号47~54 ───────────────────────────
        high_accel_btn   = bool((byte34 >> 0) & 1)  # 序号47：高加速按钮状态
        cab_light_switch = bool((byte34 >> 1) & 1)  # 序号48：司机室照明开关状态
        mode_up_confirm  = bool((byte34 >> 2) & 1)  # 序号49：模式升级确认标志
        mode_dn_confirm  = bool((byte34 >> 3) & 1)  # 序号50：模式降级确认标志
        confirm_flag     = bool((byte34 >> 4) & 1)  # 序号51：确认标志
        auto_rev_flag    = bool((byte34 >> 5) & 1)  # 序号52：自动折返标志
        trac_aux_reset   = bool((byte34 >> 6) & 1)  # 序号53：牵引辅助复位标志
        ato_start_btn    = bool((byte34 >> 7) & 1)  # 序号54：ATO启动标志

        # ── byte35（字节偏移35）：序号55~62 ───────────────────────────
        wash_mode_switch = bool((byte35 >> 0) & 1)  # 序号55：洗车模式开关状态
        key_switch       = bool((byte35 >> 1) & 1)  # 序号56：钥匙开关状态
        vigilance        = bool((byte35 >> 2) & 1)  # 序号57：警惕标志
        vigilance_allow  = bool((byte35 >> 3) & 1)  # 序号58：警惕允许解除标志
        # bit4~7（35.4~35.7）预留

        # ── 方向手柄（序号63） ─────────────────────────────────────────
        direction = DIR_MAP.get(direction_raw, "neutral")

        # ── 主手柄 + 极位百分比 → 牵引/制动级位（序号64~66） ──────────
        # traction_level 0~4，brake_level 0~7
        traction_level = 0
        brake_level    = 0

        if main_handle == MAIN_HANDLE_TRAC:
            traction_level = max(1, round(traction_pct / 100 * 4)) if traction_pct > 0 else 1
        elif main_handle == MAIN_HANDLE_BRAKE:
            brake_level = max(1, round(brake_pct / 100 * 7)) if brake_pct > 0 else 1
        elif main_handle == MAIN_HANDLE_FAST:
            brake_level = 7  # 快制：最大制动

        # ── 控制模式推断 ───────────────────────────────────────────────
        # 激活 ATO 模式（序号22）才算 ATO，否则 manual
        control_mode = "ato" if ato_active else "manual"

        # ── 外部照明、门模式字符串化 ───────────────────────────────────
        light_switch_str = LIGHT_MAP.get(light_switch, f"unknown({light_switch})")
        door_mode_str    = DOOR_MODE_MAP.get(door_mode_raw, f"unknown({door_mode_raw})")

        # ── driver_input：发布给车辆算法模块 ──────────────────────────
        driver_input = {
            "vehicle_id":           self.vehicle_id,
            # 手柄操作
            "direction":            direction,           # "forward"/"backward"/"neutral"
            "main_handle_raw":      main_handle,         # 原始值，便于调试
            "traction_level":       traction_level,      # 牵引档位 0~4
            "brake_level":          brake_level,         # 制动档位 0~7
            "traction_percent":     int(traction_pct),   # 序号65：牵引极位百分比
            "brake_percent":        int(brake_pct),      # 序号66：制动极位百分比
            # 控制模式
            "control_mode":         control_mode,        # "manual"/"ato"
            # 指示灯状态（byte24）
            "high_voltage_light":   high_voltage_light,  # 序号13：高断合指示灯
            "brake_bad_light":      brake_bad_light,     # 序号14：制动缓解不良指示灯
            "door_closed_light":    door_closed_light,   # 序号17：门关好指示灯
            "network_fault_light":  network_fault_light, # 序号18：网络故障指示灯
            # ATO/折返模式标志（byte24/25）
            "auto_reverse_cap":     auto_reverse_cap,    # 序号19：具备自动折返模式
            "ato_capable":          ato_capable,         # 序号20：具备ATO模式
            "wash_mode_status":     wash_mode_status,    # 序号21：进入洗车模式（状态）
            "ato_active":           ato_active,          # 序号22：激活ATO模式
            "auto_reverse_active":  auto_reverse_active, # 序号23：激活自动折返模式
            # 制动控制（byte28）
            "emergency_button":     emergency_brake,     # 序号29：紧急制动按钮
            "bus_ctrl_btn":         bus_ctrl_btn,        # 序号30：母线控制按钮
            "forced_release":       forced_release,      # 序号31：强迫缓解
            "forced_pump":          forced_pump,         # 序号32：强迫泵风
            "emergency_cmd":        emergency_cmd,       # 序号33：应急指挥按钮
            "parking_apply":        parking_apply,       # 序号34：停放制动施加
            "parking_release":      parking_release,     # 序号35：停放制动缓解
            "horn":                 horn,                # 序号36：电笛
            # 车门控制（byte29）
            "open_left_door":       open_left_door,      # 序号37
            "open_right_door":      open_right_door,     # 序号38
            "close_left_door":      close_left_door,     # 序号39
            "close_right_door":     close_right_door,    # 序号40
            # 照明/门模式（序号45~46）
            "light_switch":         light_switch_str,    # 序号45：外部照明
            "door_mode":            door_mode_str,       # 序号46：门模式
            # 按钮/开关（byte34）
            "high_accel_btn":       high_accel_btn,      # 序号47：高加速按钮
            "cab_light_switch":     cab_light_switch,    # 序号48：司机室照明
            "mode_up_confirm":      mode_up_confirm,     # 序号49：模式升级确认
            "mode_dn_confirm":      mode_dn_confirm,     # 序号50：模式降级确认
            "confirm_flag":         confirm_flag,        # 序号51：确认标志
            "auto_rev_flag":        auto_rev_flag,       # 序号52：自动折返标志
            "trac_aux_reset":       trac_aux_reset,      # 序号53：牵引辅助复位
            "ato_start_btn":        ato_start_btn,       # 序号54：ATO启动标志
            # 开关状态（byte35）
            "wash_mode_switch":     wash_mode_switch,    # 序号55：洗车模式开关
            "key_switch":           key_switch,          # 序号56：钥匙开关
            "vigilance":            vigilance,           # 序号57：警惕标志
            "vigilance_allow":      vigilance_allow,     # 序号58：警惕允许解除
        }

        return driver_input

    # ------------------------------------------------------------------
    # 向司机台发送数据（上位机 → PLC，7.2节）
    # ------------------------------------------------------------------

    def send_to_plc(
        self,
        vehicle_speed_kmh: float = 0.0,
        high_voltage_on: bool = False,
        brake_bad_light: bool = False,
        door_open_light: bool = False,
        door_closed_light: bool = False,
        network_fault: bool = False,
        auto_reverse_cap: bool = False,
        ato_capable: bool = False,
        wash_mode_status: bool = False,
        ato_active: bool = False,
        auto_reverse_active: bool = False,
    ):
        """
        向司机台 PLC 发送上行帧（7.2节，28字节）

        作用：
          1. 把车辆算法算出的实时速度回传给司机台，驱动速度表显示
          2. 控制司机台上各指示灯/模式标志的亮灭

        参数严格对应 7.2 节字段：
            vehicle_speed_kmh:  序号28 车辆速度（km/h）
            high_voltage_on:    序号13 高断合指示灯（byte24.1）
            brake_bad_light:    序号14 制动缓解不良指示灯（byte24.2）
            door_open_light:    序号16 开门灯状态（byte24.4）
            door_closed_light:  序号17 门关好指示灯（byte24.5）
            network_fault:      序号18 网络故障指示灯（byte24.6）
            auto_reverse_cap:   序号19 具备自动折返模式标志（byte24.7）
            ato_capable:        序号20 具备ATO模式标志（byte25.0）
            wash_mode_status:   序号21 进入洗车模式标志（byte25.1）
            ato_active:         序号22 激活ATO模式标志（byte25.2）
            auto_reverse_active:序号23 激活自动折返模式标志（byte25.3）
        """
        if not self._connected or self._sock is None:
            logger.warning(f"[{self.vehicle_id}] send_to_plc() called but not connected")
            return

        now = time.localtime()

        # 上行帧头：55 AA 55 AA（小端 DWORD = 0xAA55AA55）
        identify    = 0xAA55AA55
        verify_type = 0
        verify_code = 0

        # 数据区字节0（byte24，7.2节序号12~19）
        # bit0（24.0）预留
        # bit1（24.1）高断合指示灯
        # bit2（24.2）制动缓解不良指示灯
        # bit3（24.3）预留
        # bit4（24.4）开门灯状态  ← 7.2节序号16，7.1节此位为预留
        # bit5（24.5）门关好指示灯
        # bit6（24.6）网络故障指示灯
        # bit7（24.7）具备自动折返模式标志
        ctrl_b0 = 0
        if high_voltage_on:    ctrl_b0 |= (1 << 1)  # 序号13：高断合指示灯
        if brake_bad_light:    ctrl_b0 |= (1 << 2)  # 序号14：制动缓解不良指示灯
        if door_open_light:    ctrl_b0 |= (1 << 4)  # 序号16：开门灯状态
        if door_closed_light:  ctrl_b0 |= (1 << 5)  # 序号17：门关好指示灯
        if network_fault:      ctrl_b0 |= (1 << 6)  # 序号18：网络故障指示灯
        if auto_reverse_cap:   ctrl_b0 |= (1 << 7)  # 序号19：具备自动折返模式

        # 数据区字节1（byte25，7.2节序号20~27）
        # bit0（25.0）具备ATO模式标志
        # bit1（25.1）进入洗车模式标志
        # bit2（25.2）激活ATO模式标志
        # bit3（25.3）激活自动折返模式标志
        # bit4~7 预留
        ctrl_b1 = 0
        if ato_capable:          ctrl_b1 |= (1 << 0)  # 序号20：具备ATO
        if wash_mode_status:     ctrl_b1 |= (1 << 1)  # 序号21：进入洗车模式
        if ato_active:           ctrl_b1 |= (1 << 2)  # 序号22：激活ATO
        if auto_reverse_active:  ctrl_b1 |= (1 << 3)  # 序号23：激活自动折返模式

        # 速度：km/h，WORD，小端
        speed_word = int(round(vehicle_speed_kmh)) & 0xFFFF

        # 上行帧格式（7.2节，严格按协议）：
        #   序号1  DWORD identify       [0:4]   = 55 AA 55 AA（小端 0xAA55AA55）
        #   序号2  WORD  _uTotalLen     [4:6]   = 28（整帧总字节）
        #   序号3  WORD  _uDataLen      [6:8]   = 2（数据区：ctrl_b0 + ctrl_b1）
        #   序号4  WORD  year           [8:10]
        #   序号5  WORD  month          [10:12]
        #   序号6  WORD  day            [12:14]
        #   序号7  WORD  hour           [14:16]
        #   序号8  WORD  minute         [16:18]
        #   序号9  WORD  second         [18:20]
        #   序号10 WORD  verify_type    [20:22]
        #   序号11 WORD  verify_code    [22:24]
        #   序号12~19 BYTE ctrl_b0      [24]    指示灯+折返标志
        #   序号20~27 BYTE ctrl_b1      [25]    ATO/洗车模式标志
        #   序号28 WORD  vehicle_speed  [26:28] 车辆速度 km/h
        #   合计：I(4)+H×10(20)+B×2(2)+H(2) = 28 字节
        UP_FRAME_FMT = "<IHHHHHHHHHHBBH"
        UP_FRAME_LEN = struct.calcsize(UP_FRAME_FMT)  # 必须 = 28
        assert UP_FRAME_LEN == 28, f"UP_FRAME_LEN={UP_FRAME_LEN}"

        total_len = 28   # 整帧总字节数
        data_len  = 2    # 数据区字节数（ctrl_b0 + ctrl_b1，速度单独列为序号28）

        payload = struct.pack(
            UP_FRAME_FMT,
            identify,
            total_len,
            data_len,
            now.tm_year,
            now.tm_mon,
            now.tm_mday,
            now.tm_hour,
            now.tm_min,
            now.tm_sec,
            verify_type,
            verify_code,
            ctrl_b0,
            ctrl_b1,
            speed_word,
        )

        assert len(payload) == UP_FRAME_LEN, (
            f"uplink frame length error: {len(payload)} != {UP_FRAME_LEN}"
        )

        try:
            self._sock.sendall(payload)
            logger.debug(
                f"[{self.vehicle_id}] Sent to PLC: "
                f"speed={vehicle_speed_kmh:.1f}km/h "
                f"ato_active={ato_active} door_closed={door_closed_light}"
            )
        except OSError as e:
            logger.error(f"[{self.vehicle_id}] sendall failed: {e}")
