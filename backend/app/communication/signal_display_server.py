"""
司机台信号屏 TCP Server 模块

根据《司机驾驶模拟台信号屏协议》实现：
- 信号显示屏（MMI）作为 TCP Client 连接上位机（TCP Server）
- IP: 192.168.100.121 Port: 9999
- 总长: 66字节
- 包含时间、速度、加速度、载客率、牵引切除、限速、模式、牵引状态、制动状态、紧急制动等信息

通信方式：TCPServer
格式：66字节定长报文
"""

import json
import socket
import struct
import threading
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any
from app.communication.message_bus import MessageBus
from app.core.config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 协议常量
# ------------------------------------------------------------------
SIGNAL_DISPLAY_FRAME_LEN = 66
SIGNAL_DISPLAY_MAGIC = 0x55AA55AA  # 固定数据 0x55 AA 55 AA

# 模式映射
MODE_MAP = {
    0: "DTO",
    1: "ATO", 
    2: "AR",
    3: "SM",
    4: "RM",
    -1: "RM"  # 默认值，没有值发过来显示RM
}

# 站点信息映射
STATION_MAP = {
    1: "车公庄",
    2: "丰台科技园", 
    3: "科怡路",
    4: "丰台南路",
    5: "丰台东大街",
    6: "七里庄",
    7: "六里桥",
    8: "六里桥东",
    9: "北京西",
    10: "军事博物馆",
    11: "白堆子",
    12: "白石桥南",
    13: "国家图书馆"
}

# 方向映射
DIRECTION_MAP = {
    -1: "非法",
    0: "上行", 
    1: "下行"
}

# 状态映射 (非法、关闭、开启)
STATE_MAP = {
    -1: "非法",
    0: "关闭",
    1: "开启"
}

# ------------------------------------------------------------------
# 协议帧结构定义（66字节）
# 格式：<I H H Q H H H H H H H H H H H H B B B B B B B B f f H H B B B B B B H f
# 字节序号数据名称字节偏移变量类型变量大小描述
# 1_uIdentify0DWORD4字节固定数据0x55 AA 55 AA
# 2_uTotalLen4WORD2字节报文总大小
# 3_uDataLen6WORD2字节数据长度
# 4_timestamp8DDWORD8字节毫秒级时间戳
# 5_uVerifyType16WORD2字节校验类型
# 6_uVerifyCode18WORD2字节校验码
# 7_uProtocolID20WORD2字节协议ID
# 8_uMsgID22WORD2字节消息ID
# 9_hYear24WORD2字节年
# 10_hMonth26WORD2字节月
# 11_hDay28WORD2字节日
# 12_hHour30WORD2字节时
# 13_hMinute32WORD2字节分
# 14_hSec34WORD2字节秒
# 15_nCurrStationID36BYTE1字节当前站ID（0-16）
# _nNextStationID37BYTE1字节下一站
# _nEndStationID38BYTE1字节终点站
# _nCMState39BYTE1字节-1非法，0关闭，1 开启
# _nMMState40BYTE1字节-1非法，0关闭，1 开启
# _nCTCState41BYTE1字节-1非法，0关闭，1 开启
# _nRunDir42BYTE1字节-1非法，0 上行，1 下行
# _nReserve43BYTE1字节预留
# 16_nSpeed42FLOAT4字节速度
# 17_fAcceleration46FLOAT4字节加速度
# 18_nPullSwitch50WORD2字节牵引切除
# 19_fSpeedLimit52WORD2字节限速
# 20_nMode54BYTE1字节模式
# 21_nPullState55BYTE1字节牵引状态
# 22_nBrakeState56BYTE1字节制动状态
# 23_nUrgencyStopState57BYTE1字节紧急制动
# 24_nEventID58BYTE1字节0-255
# _nSigState59BYTE1字节BIT0-BIT3
# _nTrainNo60WORD2字节车号
# _fNextStationDist62FLOAT4字节距下一站的距离
# ------------------------------------------------------------------

# 修正格式字符串：根据协议描述重新排列字段
# I - uIdentify (4)
# H - uTotalLen (2)
# H - uDataLen (2)
# Q - timestamp (8)
# H - uVerifyType (2)
# H - uVerifyCode (2)
# H - uProtocolID (2)
# H - uMsgID (2)
# H - hYear (2)
# H - hMonth (2)
# H - hDay (2)
# H - hHour (2)
# H - hMinute (2)
# H - hSec (2)
# B - nCurrStationID (1)
# B - nNextStationID (1)
# B - nEndStationID (1)
# B - nCMState (1)
# B - nMMState (1)
# B - nCTCState (1)
# B - nRunDir (1)
# B - nReserve (1)
# f - nSpeed (4)
# f - fAcceleration (4)
# H - nPullSwitch (2)
# H - fSpeedLimit (2)
# B - nMode (1)
# B - nPullState (1)
# B - nBrakeState (1)
# B - nUrgencyStopState (1)
# B - nEventID (1)
# B - nSigState (1)
# H - nTrainNo (2)
# f - fNextStationDist (4)
# 总计: 66字节

SIGNAL_DISPLAY_FMT = "<IHHQHHHHHHHHHHHHBBBBBBBffHHBBBBBHHf"

# 验证帧长度
actual_size = struct.calcsize(SIGNAL_DISPLAY_FMT)
if actual_size != SIGNAL_DISPLAY_FRAME_LEN:
    print(f"警告: 帧格式大小不匹配: {actual_size} != {SIGNAL_DISPLAY_FRAME_LEN}")
    print(f"格式字符串: {SIGNAL_DISPLAY_FMT}")
    print("可能需要调整格式字符串。临时使用实际大小")
    SIGNAL_DISPLAY_FRAME_LEN = actual_size


class SignalDisplayServer:
    """
    司机台信号屏 TCP Server

    职责：
    1. 作为 TCP Server 监听信号显示屏的连接
    2. 接收信号显示屏发送的 66 字节定长报文
    3. 解析数据并发布到 ZMQ 总线
    4. 支持多个信号显示屏同时连接
    5. 提供发送数据到信号显示屏的功能

    注意：信号屏作为客户端主动连接我们，我们需要接收数据和发送数据
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        bus: MessageBus = None,
        record_dir: str = None,
        record_raw: bool = True,
    ):
        self.host = host or "192.168.100.121"  # 默认信号屏服务器IP
        self.port = port or 9999  # 默认信号屏服务器端口

        self._bus = bus
        self._owns_bus = bus is None

        # TCP Server 相关
        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._accept_thread: Optional[threading.Thread] = None
        
        # 客户端连接管理
        self._clients: Dict[socket.socket, Dict[str, Any]] = {}
        self._clients_lock = threading.Lock()

        # 统计
        self._recv_count = 0
        self._send_count = 0
        self._drop_count = 0
        self._error_count = 0
        self._last_recv_at: Optional[float] = None

        # 持久化
        self._record_raw = record_raw
        self._jsonl_file = None
        self._raw_file = None
        if record_dir is not None:
            base = Path(record_dir)
            base.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            self._jsonl_file = open(
                base / f"signal_display_{ts}.jsonl", "w", encoding="utf-8"
            )
            if record_raw:
                self._raw_file = open(
                    base / f"signal_display_{ts}_raw.txt", "w", encoding="utf-8"
                )
            logger.info(f"Recording signal display data to {base}")

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self):
        """启动TCP Server"""
        if self._running:
            logger.warning("SignalDisplayServer already running")
            return

        if self._owns_bus:
            self._bus = MessageBus()
            self._bus.start()

        self._running = True
        self._accept_thread = threading.Thread(
            target=self._accept_loop,
            daemon=True,
            name="SignalDisplay-Accept"
        )
        self._accept_thread.start()
        
        logger.info(f"SignalDisplayServer started, listening on {self.host}:{self.port}")

    def stop(self):
        """停止TCP Server"""
        self._running = False

        # 关闭所有客户端连接
        with self._clients_lock:
            for client_sock in list(self._clients.keys()):
                try:
                    client_sock.close()
                except:
                    pass
            self._clients.clear()

        # 关闭服务器socket
        if self._server_socket:
            try:
                self._server_socket.close()
            except:
                pass
            self._server_socket = None

        # 等待接收线程结束
        if self._accept_thread:
            self._accept_thread.join(timeout=5)
            self._accept_thread = None

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
            f"SignalDisplayServer stopped (recv={self._recv_count}, "
            f"send={self._send_count}, dropped={self._drop_count}, "
            f"errors={self._error_count})"
        )

    def status(self) -> dict:
        """获取服务器状态"""
        with self._clients_lock:
            client_count = len(self._clients)
        
        return {
            "running": self._running,
            "host": self.host,
            "port": self.port,
            "client_count": client_count,
            "recv_count": self._recv_count,
            "send_count": self._send_count,
            "drop_count": self._drop_count,
            "error_count": self._error_count,
            "last_recv_at": self._last_recv_at,
        }

    # ------------------------------------------------------------------
    # TCP Server 接收循环
    # ------------------------------------------------------------------

    def _accept_loop(self):
        """接受客户端连接的循环"""
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self.host, self.port))
            self._server_socket.listen(5)
            self._server_socket.settimeout(1.0)
            
            logger.info(f"TCP Server listening on {self.host}:{self.port}")
            
            while self._running:
                try:
                    client_socket, client_address = self._server_socket.accept()
                    logger.info(f"New signal display client connected: {client_address}")
                    
                    # 为新客户端启动接收线程
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_address),
                        daemon=True,
                        name=f"SignalDisplay-Client-{client_address}"
                    )
                    client_thread.start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self._running:
                        logger.error(f"Accept error: {e}")
                        time.sleep(1)
                        
        except Exception as e:
            logger.error(f"Server socket error: {e}")
        finally:
            if self._server_socket:
                try:
                    self._server_socket.close()
                except:
                    pass
                self._server_socket = None

    def _handle_client(self, client_socket: socket.socket, client_address: tuple):
        """处理单个客户端连接"""
        # 添加客户端到管理列表
        with self._clients_lock:
            self._clients[client_socket] = {
                "address": client_address,
                "connected_at": time.time(),
                "recv_count": 0,
                "last_recv_at": None
            }
        
        try:
            client_socket.settimeout(2.0)  # 2秒超时
            
            while self._running:
                try:
                    # 接收完整帧
                    raw = self._recv_exact(client_socket, SIGNAL_DISPLAY_FRAME_LEN)
                    if raw is None:
                        break
                    
                    self._last_recv_at = time.time()
                    self._recv_count += 1
                    
                    # 更新客户端统计
                    with self._clients_lock:
                        client_info = self._clients[client_socket]
                        client_info["recv_count"] += 1
                        client_info["last_recv_at"] = self._last_recv_at

                    # 持久化原始字节
                    if self._raw_file:
                        self._raw_file.write(
                            f"{self._last_recv_at:.6f}|{client_address}|{raw.hex()}\n"
                        )

                    # 解析帧
                    parsed = self._parse_frame(raw, client_address)
                    if parsed is None:
                        self._drop_count += 1
                        continue

                    # 持久化解析结果
                    if self._jsonl_file:
                        record = {"_ts": self._last_recv_at, "_client": client_address, **parsed}
                        self._jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")

                    # 发布到消息总线
                    self._bus.publish("signal_display_input", parsed)

                    # 发布通信状态
                    self._bus.publish("comm_state", {
                        "source": "signal_display_tcp",
                        "signal_display_connected": True,
                        "client_address": client_address,
                        "last_message_at": self._last_recv_at,
                    })

                    # 调试日志（每10帧记录一次）
                    if self._recv_count % 10 == 0:
                        logger.debug(
                            f"[{client_address}] Signal display data: "
                            f"speed={parsed.get('speed', 0):.1f}km/h "
                            f"accel={parsed.get('acceleration', 0):.2f}m/s² "
                            f"mode={parsed.get('mode', 'RM')} "
                            f"limit={parsed.get('speed_limit', 0)}km/h"
                        )

                except socket.timeout:
                    # 检查连接是否仍然活跃
                    continue
                except Exception as e:
                    logger.error(f"Client {client_address} error: {e}")
                    self._error_count += 1
                    break
                    
        except Exception as e:
            logger.error(f"Client handler error for {client_address}: {e}")
        finally:
            # 清理客户端连接
            with self._clients_lock:
                if client_socket in self._clients:
                    del self._clients[client_socket]
            
            try:
                client_socket.close()
            except:
                pass
            
            logger.info(f"Signal display client disconnected: {client_address}")

    def _recv_exact(self, sock: socket.socket, n: int) -> Optional[bytes]:
        """精确接收 n 字节"""
        buf = b""
        while len(buf) < n:
            try:
                chunk = sock.recv(n - len(buf))
                if not chunk:
                    return None
                buf += chunk
            except socket.timeout:
                raise
            except:
                return None
        return buf

    # ------------------------------------------------------------------
    # 帧解析
    # ------------------------------------------------------------------

    def _parse_frame(self, raw: bytes, client_address: tuple) -> Optional[dict]:
        """解析信号屏发送的66字节帧"""
        if len(raw) != SIGNAL_DISPLAY_FRAME_LEN:
            logger.warning(f"Bad frame length from {client_address}: {len(raw)} != {SIGNAL_DISPLAY_FRAME_LEN}")
            return None

        try:
            # 解包数据
            fields = struct.unpack(SIGNAL_DISPLAY_FMT, raw)
            
            # 提取字段
            (
                uIdentify,       # 0: 固定数据 0x55 AA 55 AA
                uTotalLen,       # 1: 报文总大小
                uDataLen,        # 2: 数据长度
                timestamp,       # 3: 毫秒级时间戳
                uVerifyType,     # 4: 校验类型
                uVerifyCode,     # 5: 校验码
                uProtocolID,     # 6: 协议ID
                uMsgID,          # 7: 消息ID
                hYear,           # 8: 年
                hMonth,          # 9: 月
                hDay,            # 10: 日
                hHour,           # 11: 时
                hMinute,         # 12: 分
                hSec,            # 13: 秒
                nCurrStationID,  # 14: 当前站ID
                nNextStationID,  # 15: 下一站
                nEndStationID,   # 16: 终点站
                nCMState,        # 17: CM状态
                nMMState,        # 18: MM状态
                nCTCState,       # 19: CTC状态
                nRunDir,         # 20: 运行方向
                nReserve,        # 21: 预留
                nSpeed,          # 22: 速度 (km/h)
                fAcceleration,   # 23: 加速度 (m/s²)
                nPullSwitch,     # 24: 牵引切除
                fSpeedLimit,     # 25: 限速 (km/h)
                nMode,           # 26: 模式
                nPullState,      # 27: 牵引状态
                nBrakeState,     # 28: 制动状态
                nUrgencyStopState, # 29: 紧急制动
                nEventID,        # 30: 事件ID
                nSigState,       # 31: 信号状态
                nTrainNo,        # 32: 车号
                fNextStationDist, # 33: 距下一站的距离 (m)
            ) = fields

            # 验证帧头
            if uIdentify != SIGNAL_DISPLAY_MAGIC:
                logger.warning(
                    f"Bad magic from {client_address}: 0x{uIdentify:08X} "
                    f"(expected 0x{SIGNAL_DISPLAY_MAGIC:08X})"
                )
                return None

            # 验证帧长度
            if uTotalLen != SIGNAL_DISPLAY_FRAME_LEN:
                logger.warning(
                    f"Bad total length from {client_address}: {uTotalLen} "
                    f"(expected {SIGNAL_DISPLAY_FRAME_LEN})"
                )

            # 处理默认值（根据协议，没有值发过来显示0或默认值）
            speed = nSpeed if nSpeed >= 0 else 0.0
            acceleration = fAcceleration if fAcceleration >= 0 else 0.0
            speed_limit = fSpeedLimit if fSpeedLimit >= 0 else 0.0
            
            # 模式处理
            mode_value = nMode
            if nMode < 0 or nMode > 4:
                mode_value = -1  # 非法值使用默认RM
            mode = MODE_MAP.get(mode_value, "RM")
            
            # 站点名称映射
            current_station = STATION_MAP.get(nCurrStationID, f"未知{nCurrStationID}")
            next_station = STATION_MAP.get(nNextStationID, f"未知{nNextStationID}")
            end_station = STATION_MAP.get(nEndStationID, f"未知{nEndStationID}")
            
            # 方向映射
            direction = DIRECTION_MAP.get(nRunDir, "未知")
            
            # 状态映射
            cm_state = STATE_MAP.get(nCMState, "未知")
            mm_state = STATE_MAP.get(nMMState, "未知")
            ctc_state = STATE_MAP.get(nCTCState, "未知")
            
            # 牵引切除状态（0: 正常, 1: 切除）
            pull_switch_status = "切除" if nPullSwitch == 1 else "正常"
            
            # 构建解析结果
            result = {
                # 帧头信息
                "magic": f"0x{uIdentify:08X}",
                "total_length": uTotalLen,
                "data_length": uDataLen,
                "timestamp": timestamp,
                "verify_type": uVerifyType,
                "verify_code": uVerifyCode,
                "protocol_id": uProtocolID,
                "msg_id": uMsgID,
                
                # 时间信息
                "year": hYear,
                "month": hMonth,
                "day": hDay,
                "hour": hHour,
                "minute": hMinute,
                "second": hSec,
                
                # 站点信息
                "current_station_id": nCurrStationID,
                "current_station_name": current_station,
                "next_station_id": nNextStationID,
                "next_station_name": next_station,
                "end_station_id": nEndStationID,
                "end_station_name": end_station,
                "next_station_distance": fNextStationDist,
                
                # 系统状态
                "cm_state": cm_state,
                "mm_state": mm_state,
                "ctc_state": ctc_state,
                "direction": direction,
                
                # 车辆运行状态
                "speed": speed,  # km/h
                "acceleration": acceleration,  # m/s²
                "speed_limit": speed_limit,  # km/h
                "mode": mode,
                
                # 车辆控制状态
                "pull_switch": pull_switch_status,
                "pull_state": STATE_MAP.get(nPullState, "未知"),
                "brake_state": STATE_MAP.get(nBrakeState, "未知"),
                "urgency_stop_state": STATE_MAP.get(nUrgencyStopState, "未知"),
                
                # 其他信息
                "event_id": nEventID,
                "signal_state": nSigState,
                "train_no": nTrainNo,
                
                # 原始值（用于调试）
                "_raw": {
                    "nMode": nMode,
                    "nRunDir": nRunDir,
                    "nCMState": nCMState,
                    "nMMState": nMMState,
                    "nCTCState": nCTCState,
                    "nPullState": nPullState,
                    "nBrakeState": nBrakeState,
                    "nUrgencyStopState": nUrgencyStopState,
                }
            }
            
            return result
            
        except struct.error as e:
            logger.warning(f"Unpack failed from {client_address}: {e}")
            return None
        except Exception as e:
            logger.error(f"Parse error from {client_address}: {e}")
            return None

    # ------------------------------------------------------------------
    # 发送数据到信号显示屏
    # ------------------------------------------------------------------

    def send_to_display(self, client_address: tuple = None, **kwargs):
        """
        发送数据到指定的信号显示屏
        
        参数说明：
        - client_address: 客户端地址，如果为None则发送给所有连接的客户端
        - kwargs: 要发送的数据字段
        
        可发送的字段：
        - speed: 速度 (km/h)
        - acceleration: 加速度 (m/s²)
        - speed_limit: 限速 (km/h)
        - mode: 模式 (0-4 对应 DTO/ATO/AR/SM/RM)
        - pull_switch: 牵引切除 (0:正常, 1:切除)
        - pull_state: 牵引状态 (-1/0/1)
        - brake_state: 制动状态 (-1/0/1)
        - urgency_stop_state: 紧急制动状态 (-1/0/1)
        - current_station_id: 当前站ID
        - next_station_id: 下一站ID
        - end_station_id: 终点站ID
        - next_station_distance: 距下一站距离
        - train_no: 车号
        """
        try:
            # 获取要发送的客户端列表
            clients_to_send = []
            with self._clients_lock:
                if client_address:
                    # 查找特定客户端
                    for sock, info in self._clients.items():
                        if info["address"] == client_address:
                            clients_to_send.append(sock)
                            break
                else:
                    # 发送给所有客户端
                    clients_to_send = list(self._clients.keys())
            
            if not clients_to_send:
                logger.warning("No signal display clients connected")
                return
            
            # 构建发送帧
            send_data = self._build_send_frame(**kwargs)
            
            # 发送给每个客户端
            for client_sock in clients_to_send:
                try:
                    client_sock.sendall(send_data)
                    self._send_count += 1
                    
                    # 记录发送
                    with self._clients_lock:
                        if client_sock in self._clients:
                            client_info = self._clients[client_sock]
                            logger.debug(
                                f"Sent to signal display {client_info['address']}: "
                                f"speed={kwargs.get('speed', 0):.1f}km/h "
                                f"mode={kwargs.get('mode', 'RM')}"
                            )
                            
                except Exception as e:
                    logger.error(f"Send to client failed: {e}")
                    
        except Exception as e:
            logger.error(f"send_to_display error: {e}")

    def _build_send_frame(self, **kwargs) -> bytes:
        """构建发送给信号显示屏的帧"""
        # 获取当前时间
        now = time.localtime()
        
        # 设置默认值
        data = {
            # 帧头信息
            "uIdentify": SIGNAL_DISPLAY_MAGIC,
            "uTotalLen": SIGNAL_DISPLAY_FRAME_LEN,
            "uDataLen": SIGNAL_DISPLAY_FRAME_LEN - 16,  # 总长减去帧头部分
            "timestamp": int(time.time() * 1000),  # 毫秒级时间戳
            
            # 校验信息（暂不使用）
            "uVerifyType": 0,
            "uVerifyCode": 0,
            "uProtocolID": 1,
            "uMsgID": 1,
            
            # 时间信息
            "hYear": now.tm_year,
            "hMonth": now.tm_mon,
            "hDay": now.tm_mday,
            "hHour": now.tm_hour,
            "hMinute": now.tm_min,
            "hSec": now.tm_sec,
            
            # 站点信息（默认值）
            "nCurrStationID": kwargs.get("current_station_id", 0),
            "nNextStationID": kwargs.get("next_station_id", 0),
            "nEndStationID": kwargs.get("end_station_id", 0),
            
            # 系统状态（默认正常）
            "nCMState": 1,  # 开启
            "nMMState": 1,  # 开启
            "nCTCState": 1,  # 开启
            "nRunDir": kwargs.get("direction", 0),  # 默认上行
            
            # 预留
            "nReserve": 0,
            
            # 运行状态
            "nSpeed": kwargs.get("speed", 0.0),
            "fAcceleration": kwargs.get("acceleration", 0.0),
            "nPullSwitch": kwargs.get("pull_switch", 0),  # 0:正常
            "fSpeedLimit": kwargs.get("speed_limit", 0.0),
            "nMode": kwargs.get("mode", 4),  # 默认RM
            
            # 车辆状态
            "nPullState": kwargs.get("pull_state", 1),  # 默认开启
            "nBrakeState": kwargs.get("brake_state", 0),  # 默认关闭
            "nUrgencyStopState": kwargs.get("urgency_stop_state", 0),  # 默认关闭
            
            # 其他信息
            "nEventID": kwargs.get("event_id", 0),
            "nSigState": kwargs.get("signal_state", 0),
            "nTrainNo": kwargs.get("train_no", 1),
            "fNextStationDist": kwargs.get("next_station_distance", 0.0),
        }
        
        # 构建帧
        frame = struct.pack(
            SIGNAL_DISPLAY_FMT,
            data["uIdentify"],
            data["uTotalLen"],
            data["uDataLen"],
            data["timestamp"],
            data["uVerifyType"],
            data["uVerifyCode"],
            data["uProtocolID"],
            data["uMsgID"],
            data["hYear"],
            data["hMonth"],
            data["hDay"],
            data["hHour"],
            data["hMinute"],
            data["hSec"],
            data["nCurrStationID"],
            data["nNextStationID"],
            data["nEndStationID"],
            data["nCMState"],
            data["nMMState"],
            data["nCTCState"],
            data["nRunDir"],
            data["nReserve"],
            data["nSpeed"],
            data["fAcceleration"],
            data["nPullSwitch"],
            data["fSpeedLimit"],
            data["nMode"],
            data["nPullState"],
            data["nBrakeState"],
            data["nUrgencyStopState"],
            data["nEventID"],
            data["nSigState"],
            data["nTrainNo"],
            data["fNextStationDist"]
        )
        
        return frame

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def get_connected_clients(self) -> list:
        """获取已连接的客户端列表"""
        with self._clients_lock:
            return [
                {
                    "address": info["address"],
                    "connected_at": info["connected_at"],
                    "recv_count": info["recv_count"],
                    "last_recv_at": info["last_recv_at"]
                }
                for info in self._clients.values()
            ]


# ------------------------------------------------------------------
# 调试和测试
# ------------------------------------------------------------------

def test_signal_display_server():
    """测试信号屏服务器"""
    import sys
    from pathlib import Path
    
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    # 创建服务器
    server = SignalDisplayServer(
        host="192.168.100.121",
        port=9999,
        record_dir="logs"
    )
    
    # 启动服务器
    server.start()
    
    print("Signal display server started")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(1)
            # 定期发送测试数据
            server.send_to_display(
                speed=45.5,
                acceleration=0.2,
                speed_limit=80.0,
                mode=1,  # ATO模式
                current_station_id=3,
                next_station_id=4,
                next_station_distance=1250.5,
                train_no=1001
            )
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.stop()


if __name__ == "__main__":
    test_signal_display_server()