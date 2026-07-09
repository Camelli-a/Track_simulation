"""
UDP 数据源
负责接收司机台发来的 UDP 数据包，解析后发布到 ZMQ 总线

使用方式：
    source = UDPSource(vehicle_id="TRAIN-001")
    source.start()
    # ...
    source.stop()
"""
import socket
import threading
import logging
import time
from typing import Optional
from app.communication.message_bus import MessageBus
from app.core.config import settings

logger = logging.getLogger(__name__)


class UDPSource:
    """
    司机台 UDP 数据接收器

    职责：
    1. 监听指定 UDP 端口
    2. 收到数据包 → 调用 _parse() 解析
    3. 解析结果 → 发布到 ZMQ 总线（train_state）
    4. 连接异常时自动处理，不影响系统其他部分
    """

    def __init__(
        self,
        vehicle_id: str,
        listen_host: str = None,
        listen_port: int = None,
        bus: MessageBus = None,
    ):
        """
        Args:
            vehicle_id:   该 UDP 源对应的车辆编号，如 "TRAIN-001"
            listen_host:  监听地址，默认读取 .env 配置
            listen_port:  监听端口，默认读取 .env 配置
            bus:          MessageBus 实例，不传则内部自动创建
        """
        self.vehicle_id = vehicle_id
        self.listen_host = listen_host or settings.UDP_HOST
        self.listen_port = listen_port or settings.UDP_PORT

        # 允许外部注入 bus，方便多个 UDPSource 共用同一个 bus
        self._bus = bus
        self._owns_bus = bus is None  # 是否由自己管理 bus 生命周期

        self._sock: Optional[socket.socket] = None
        self._running = False
        self._recv_thread: Optional[threading.Thread] = None

        # 统计信息
        self._recv_count = 0
        self._last_recv_at: Optional[float] = None
        self._error_count = 0

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self):
        """启动 UDP 监听"""
        if self._running:
            logger.warning(f"[{self.vehicle_id}] UDPSource already running")
            return

        # 初始化 MessageBus
        if self._owns_bus:
            self._bus = MessageBus()
            self._bus.start()

        # 创建 UDP socket
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.settimeout(1.0)  # 1秒超时，用于检查 _running 标志
        self._sock.bind((self.listen_host, self.listen_port))

        self._running = True

        # 启动后台接收线程
        self._recv_thread = threading.Thread(
            target=self._receive_loop,
            daemon=True,
            name=f"UDPSource-{self.vehicle_id}",
        )
        self._recv_thread.start()

        logger.info(
            f"[{self.vehicle_id}] UDPSource started, "
            f"listening on {self.listen_host}:{self.listen_port}"
        )

    def stop(self):
        """停止 UDP 监听"""
        self._running = False

        if self._sock:
            self._sock.close()
            self._sock = None

        if self._recv_thread:
            self._recv_thread.join(timeout=3)
            self._recv_thread = None

        if self._owns_bus and self._bus:
            self._bus.stop()

        logger.info(f"[{self.vehicle_id}] UDPSource stopped "
                    f"(received {self._recv_count} packets, "
                    f"errors {self._error_count})")

    def status(self) -> dict:
        """返回当前运行状态（供外部查询）"""
        return {
            "vehicle_id":    self.vehicle_id,
            "running":       self._running,
            "listen":        f"{self.listen_host}:{self.listen_port}",
            "recv_count":    self._recv_count,
            "error_count":   self._error_count,
            "last_recv_at":  self._last_recv_at,
        }

    # ------------------------------------------------------------------
    # 接收循环（后台线程）
    # ------------------------------------------------------------------

    def _receive_loop(self):
        """持续接收 UDP 数据包并处理"""
        logger.info(f"[{self.vehicle_id}] Receive loop started")

        while self._running:
            try:
                raw, addr = self._sock.recvfrom(4096)
                self._last_recv_at = time.time()
                self._recv_count += 1

                logger.debug(
                    f"[{self.vehicle_id}] Received {len(raw)} bytes from {addr}"
                )

                # 解析原始数据
                data = self._parse(raw)
                if data is None:
                    logger.warning(
                        f"[{self.vehicle_id}] _parse() returned None, skipping"
                    )
                    continue

                # 补充车辆编号（确保一定有这个字段）
                data["vehicle_id"] = self.vehicle_id

                # 发布到 ZMQ 总线
                self._bus.publish("train_state", data)

            except socket.timeout:
                # 正常超时，用于周期性检查 _running 标志，不算错误
                continue

            except OSError as e:
                # socket 被关闭（通常是 stop() 调用导致）
                if self._running:
                    logger.error(f"[{self.vehicle_id}] Socket error: {e}")
                    self._error_count += 1
                break

            except Exception as e:
                logger.error(
                    f"[{self.vehicle_id}] Unexpected error: {e}",
                    exc_info=True,
                )
                self._error_count += 1

        logger.info(f"[{self.vehicle_id}] Receive loop stopped")

    # ------------------------------------------------------------------
    # 数据解析（等老师给格式后填这里）
    # ------------------------------------------------------------------

    def _parse(self, raw: bytes) -> dict | None:
        """
        解析司机台发来的 UDP 原始数据，返回 train_state 的 data 字段

        ⚠️  TODO: 等老师提供司机台协议格式后，在此实现真实解析逻辑

        Args:
            raw: UDP 原始字节数据

        Returns:
            dict: 符合 train_state.data 格式的字典
            None: 解析失败时返回 None，该包会被丢弃

        协议格式（待填写）：
            - 数据类型：未知（二进制 / JSON / 自定义帧）
            - 字段列表：未知
            - 字节序：  未知
        """
        # ----------------------------------------------------------------
        # 尝试作为 JSON 解析（如果司机台发 JSON 格式）
        # ----------------------------------------------------------------
        try:
            import json
            obj = json.loads(raw.decode("utf-8"))
            return self._map_json(obj)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        # ----------------------------------------------------------------
        # 尝试作为二进制帧解析（如果司机台发二进制格式）
        # ----------------------------------------------------------------
        # TODO: 等格式文档后填写
        # import struct
        # fmt = ">HHf..."   # 大端，字段格式待定
        # fields = struct.unpack(fmt, raw)
        # return self._map_binary(fields)

        # ----------------------------------------------------------------
        # 格式未知时：记录原始数据，返回占位结果，让流程能跑通
        # ----------------------------------------------------------------
        logger.debug(
            f"[{self.vehicle_id}] Raw bytes (hex): {raw.hex()} | "
            f"text: {raw!r}"
        )
        return self._placeholder()

    def _map_json(self, obj: dict) -> dict:
        """
        将司机台 JSON 格式映射到 train_state 格式

        TODO: 等格式文档后，把司机台的字段名映射到系统字段名
        例如：司机台叫 "brake_level"，系统叫 "emergency_brake"

        现在直接透传，字段名有差异时在这里做转换
        """
        return {
            # 直接透传已知字段，字段名不同时在这里映射
            "line_id":         obj.get("line_id", "LINE-1"),
            "position":        obj.get("position", 0.0),
            "speed":           obj.get("speed", 0.0),
            "acceleration":    obj.get("acceleration", 0.0),
            "mode":            obj.get("mode", "manual"),
            "is_running":      obj.get("is_running", True),
            "emergency_brake": obj.get("emergency_brake", False),
            # TODO: 补充司机台特有字段，如手柄位置、制动级位等
        }

    def _placeholder(self) -> dict:
        """
        格式未知时的占位数据
        让整个流程能跑通，便于测试 ZMQ 总线是否正常
        """
        return {
            "line_id":         "LINE-1",
            "position":        0.0,
            "speed":           0.0,
            "acceleration":    0.0,
            "mode":            "manual",
            "is_running":      True,
            "emergency_brake": False,
            "_source":         "udp_placeholder",  # 标记这是占位数据
        }

    # ------------------------------------------------------------------
    # 发送数据给司机台（预留，双向通信）
    # ------------------------------------------------------------------

    def send(self, data: dict):
        """
        向司机台发送数据（如允许速度、信号状态、MA 限制等）

        ⚠️  TODO: 等老师提供协议格式后实现
            - 需要知道司机台的 IP 和接收端口
            - 需要知道发送数据的格式（JSON / 二进制）

        Args:
            data: 需要发送给司机台的数据字典
        """
        # TODO: 实现向司机台发送数据
        # target_ip = settings.DRIVER_CONSOLE_IP
        # target_port = settings.DRIVER_CONSOLE_SEND_PORT
        #
        # import json
        # payload = json.dumps(data).encode("utf-8")
        # self._sock.sendto(payload, (target_ip, target_port))
        logger.debug(f"[{self.vehicle_id}] send() not implemented yet: {data}")
