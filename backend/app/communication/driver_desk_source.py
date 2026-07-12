"""
司机台数据源（TCP 客户端）

协议说明：
    - PLC 作为 TCP Server，本模块作为 Client 主动连接
    - PLC 以 100ms 周期持续推送 46 字节定长报文
    - 字节序：小端（Little Endian）
    - 帧头校验：0x55AA55AA（第 0~3 字节）

使用方式：
    source = DriverDeskSource(vehicle_id="TRAIN-001")
    source.start()
    # ...
    source.stop()
"""
import socket
import struct
import threading
import logging
import time
from typing import Optional
from app.communication.message_bus import MessageBus
from app.core.config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 协议常量
# ------------------------------------------------------------------
FRAME_LEN      = 46           # 固定帧长（字节）
FRAME_MAGIC    = 0x55AA55AA   # 帧头标识

# struct 格式字符串（小端 <）
# 只解析我们关心的字段，整帧 46 字节全部读入后按偏移取值
# 格式说明：
#   偏移 0~3   : DWORD  _uIdentify    帧头 0x55AA55AA
#   偏移 4~5   : WORD   _uTotalLen    报文总长度（固定 46）
#   偏移 6~23  : 18字节  （保留/其他字段，暂不解析）
#   偏移 24    : BYTE   status_byte0  状态标志字节0
#   偏移 25    : BYTE   status_byte1  状态标志字节1
#   偏移 26~27 : WORD   speed         车辆速度
#   偏移 28    : BYTE   brake_byte    制动控制字节
#   偏移 29    : BYTE   door_byte     车门控制字节
#   偏移 30~31 : WORD   （保留）
#   偏移 32~33 : WORD   door_mode     门模式
#   偏移 34~45 : 12字节 （保留）
#
# struct.unpack('<IH18sBBHBBHH12s', frame)
# 索引:          0 1  2  3 4 5 6 7 8  9  10
FRAME_FMT = "<IH18sBBHBBHH12s"


class DriverDeskSource:
    """
    司机台 TCP 数据接收器

    职责：
    1. 作为 TCP 客户端连接 PLC（Server）
    2. 持续接收 46 字节定长报文
    3. 校验帧头 → 解析字段 → 发布到 ZMQ 总线（train_state）
    4. 断线自动重连，不影响系统其他部分
    """

    def __init__(
        self,
        vehicle_id: str,
        plc_host: str = None,
        plc_port: int = None,
        bus: MessageBus = None,
        reconnect_interval: float = 3.0,
    ):
        """
        Args:
            vehicle_id:          对应车辆编号，如 "TRAIN-001"
            plc_host:            PLC 的 IP 地址，默认读取 .env
            plc_port:            PLC 的 TCP 端口，默认读取 .env
            bus:                 MessageBus 实例，不传则内部自动创建
            reconnect_interval:  断线后重连间隔（秒）
        """
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
        self._drop_count  = 0   # 帧头校验失败丢弃数
        self._error_count = 0
        self._last_recv_at: Optional[float] = None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self):
        """启动 TCP 连接和接收线程"""
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
        """停止接收"""
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

        logger.info(
            f"[{self.vehicle_id}] DriverDeskSource stopped "
            f"(recv={self._recv_count}, dropped={self._drop_count}, "
            f"errors={self._error_count})"
        )

    def status(self) -> dict:
        """返回当前运行状态"""
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
        """带自动重连的 TCP 接收循环"""
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
        """建立 TCP 连接"""
        logger.info(
            f"[{self.vehicle_id}] Connecting to PLC "
            f"{self.plc_host}:{self.plc_port}..."
        )
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(5.0)   # 连接超时 5 秒
        self._sock.connect((self.plc_host, self.plc_port))
        self._sock.settimeout(2.0)   # 接收超时 2 秒（PLC 100ms 周期，2秒没数据视为断线）
        self._connected = True
        logger.info(f"[{self.vehicle_id}] Connected to PLC")

    def _receive_loop(self):
        """持续接收定长帧"""
        logger.info(f"[{self.vehicle_id}] Receive loop started")

        while self._running and self._connected:
            try:
                raw = self._recv_exact(FRAME_LEN)
                if raw is None:
                    break

                self._last_recv_at = time.time()
                self._recv_count += 1

                data = self._parse(raw)
                if data is None:
                    self._drop_count += 1
                    continue

                data["vehicle_id"] = self.vehicle_id
                self._bus.publish("train_state", data)

            except socket.timeout:
                # PLC 100ms 发一帧，2秒没数据说明连接有问题
                logger.warning(f"[{self.vehicle_id}] Receive timeout, reconnecting...")
                break
            except OSError as e:
                if self._running:
                    logger.error(f"[{self.vehicle_id}] Socket error: {e}")
                break

        logger.info(f"[{self.vehicle_id}] Receive loop stopped")

    def _recv_exact(self, n: int) -> Optional[bytes]:
        """
        精确接收 n 字节（TCP 流式协议需要自己处理粘包/分包）
        Returns None 如果连接断开
        """
        buf = b""
        while len(buf) < n:
            try:
                chunk = self._sock.recv(n - len(buf))
                if not chunk:
                    logger.warning(f"[{self.vehicle_id}] PLC closed the connection")
                    return None
                buf += chunk
            except socket.timeout:
                raise  # 向上抛出，由 _receive_loop 处理
        return buf

    # ------------------------------------------------------------------
    # 帧解析
    # ------------------------------------------------------------------

    def _parse(self, raw: bytes) -> Optional[dict]:
        """
        解析 46 字节定长报文

        帧结构（小端）：
            [0:4]   DWORD  _uIdentify   帧头，固定 0x55AA55AA
            [4:6]   WORD   _uTotalLen   报文总长度，固定 46
            [6:24]  18B    (保留)
            [24]    BYTE   status_byte0 状态标志0
            [25]    BYTE   status_byte1 状态标志1
            [26:28] WORD   speed        车速
            [28]    BYTE   brake_byte   制动控制
            [29]    BYTE   door_byte    车门控制
            [30:32] WORD   (保留)
            [32:34] WORD   door_mode    门模式
            [34:46] 12B    (保留)

        Returns:
            dict: 解析后的数据（符合 train_state.data 格式）
            None: 帧头校验失败，丢弃该帧
        """
        if len(raw) != FRAME_LEN:
            logger.warning(
                f"[{self.vehicle_id}] Invalid frame length: "
                f"expected {FRAME_LEN}, got {len(raw)}"
            )
            return None

        try:
            fields = struct.unpack(FRAME_FMT, raw)
        except struct.error as e:
            logger.warning(f"[{self.vehicle_id}] struct.unpack failed: {e}")
            return None

        # fields 索引对应：
        # 0: _uIdentify, 1: _uTotalLen, 2: reserved_18b,
        # 3: status_byte0, 4: status_byte1,
        # 5: speed,
        # 6: brake_byte, 7: door_byte,
        # 8: reserved_word, 9: door_mode,
        # 10: reserved_12b

        identify    = fields[0]
        total_len   = fields[1]
        status_b0   = fields[3]   # 第 24 字节
        status_b1   = fields[4]   # 第 25 字节
        speed_raw   = fields[5]   # 第 26~27 字节，单位待确认
        brake_byte  = fields[6]   # 第 28 字节
        door_byte   = fields[7]   # 第 29 字节
        door_mode   = fields[9]   # 第 32~33 字节

        # ----------------------------------------------------------------
        # 帧头校验
        # ----------------------------------------------------------------
        if identify != FRAME_MAGIC:
            logger.warning(
                f"[{self.vehicle_id}] Bad frame magic: "
                f"0x{identify:08X} (expected 0x{FRAME_MAGIC:08X})"
            )
            return None

        if total_len != FRAME_LEN:
            logger.warning(
                f"[{self.vehicle_id}] Bad frame length field: {total_len}"
            )
            return None

        # ----------------------------------------------------------------
        # 状态字节0（第 24 字节）按位解析
        # ----------------------------------------------------------------
        door_closed_light = bool((status_b0 >> 5) & 1)   # bit5: 门关好指示灯

        # ----------------------------------------------------------------
        # 状态字节1（第 25 字节）按位解析
        # ----------------------------------------------------------------
        ato_capable  = bool((status_b1 >> 0) & 1)   # bit0: 具备 ATO
        ato_active   = bool((status_b1 >> 2) & 1)   # bit2: 激活 ATO
        auto_reverse = bool((status_b1 >> 7) & 1)   # bit7: 自动折返模式

        # 驾驶模式推断
        if ato_active:
            mode = "ato"
        elif ato_capable:
            mode = "atp"
        else:
            mode = "manual"

        # ----------------------------------------------------------------
        # 制动控制字节（第 28 字节）按位解析
        # ----------------------------------------------------------------
        emergency_brake   = bool((brake_byte >> 0) & 1)  # bit0: 紧急制动锁定
        forced_release    = bool((brake_byte >> 2) & 1)  # bit2: 强迫缓解
        forced_pump       = bool((brake_byte >> 3) & 1)  # bit3: 强迫泵风
        parking_apply     = bool((brake_byte >> 5) & 1)  # bit5: 停放制动施加
        parking_release   = bool((brake_byte >> 6) & 1)  # bit6: 停放制动缓解

        # ----------------------------------------------------------------
        # 车门控制字节（第 29 字节）按位解析
        # ----------------------------------------------------------------
        open_left_door    = bool((door_byte >> 0) & 1)   # bit0: 开左门
        open_right_door   = bool((door_byte >> 1) & 1)   # bit1: 开右门
        close_left_door   = bool((door_byte >> 2) & 1)   # bit2: 关左门
        close_right_door  = bool((door_byte >> 3) & 1)   # bit3: 关右门

        # ----------------------------------------------------------------
        # 门模式（第 32~33 字节）
        # 0x0000 = 半自动，0x0001 = 手动，0x0002 = 自动
        # ----------------------------------------------------------------
        door_mode_map = {0: "semi_auto", 1: "manual", 2: "auto"}
        door_mode_str = door_mode_map.get(door_mode, f"unknown({door_mode})")

        # ----------------------------------------------------------------
        # 速度：单位待确认（文档未说明，暂按 km/h 处理，如有误在此修改）
        # ----------------------------------------------------------------
        speed = float(speed_raw)  # TODO: 确认单位和换算系数

        return {
            # 运动状态
            "line_id":          "LINE-1",   # TODO: 如果协议里有线路信息再改
            "position":         0.0,        # PLC 不提供位置，由车辆算法模块计算
            "speed":            speed,
            "acceleration":     0.0,        # PLC 不提供加速度，由车辆算法模块计算
            "mode":             mode,
            "is_running":       True,

            # 制动
            "emergency_brake":  emergency_brake,
            "forced_release":   forced_release,
            "forced_pump":      forced_pump,
            "parking_apply":    parking_apply,
            "parking_release":  parking_release,

            # 车门
            "door_closed_light":  door_closed_light,
            "open_left_door":     open_left_door,
            "open_right_door":    open_right_door,
            "close_left_door":    close_left_door,
            "close_right_door":   close_right_door,
            "door_mode":          door_mode_str,

            # ATO/ATP
            "ato_capable":    ato_capable,
            "ato_active":     ato_active,
            "auto_reverse":   auto_reverse,
        }

    # ------------------------------------------------------------------
    # 向司机台发送数据（预留，双向通信）
    # ------------------------------------------------------------------

    def send(self, data: dict):
        """
        向司机台（PLC）发送数据，如允许速度、MA 限制、信号状态等

        ⚠️  TODO: 等老师提供上行协议格式后实现
            - 需要知道发送帧的格式（字段、长度、帧头）
            - 直接复用 self._sock（同一个 TCP 连接）发送即可

        Args:
            data: 需要发送给司机台的数据字典
        """
        if not self._connected or self._sock is None:
            logger.warning(f"[{self.vehicle_id}] send() called but not connected")
            return

        # TODO: 实现上行帧打包
        # payload = self._pack_uplink(data)
        # self._sock.sendall(payload)
        logger.debug(f"[{self.vehicle_id}] send() not implemented yet: {data}")
