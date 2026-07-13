"""
信号屏（MMI）TCP 服务器调试脚本 - 简化版
==========================================

这个版本不使用现有的SignalDisplayServer，完全独立。

使用方式：
    python debug_signal_display_fixed.py server      # 启动服务器
    python debug_signal_display_fixed.py client      # 启动测试客户端
    python debug_signal_display_fixed.py hexview     # 解析十六进制数据

功能：
1. 启动TCP Server监听信号屏连接
2. 模拟信号屏客户端发送数据
3. 解析66字节帧数据并显示
"""

import argparse
import socket
import struct
import threading
import time
import sys
import logging
from pathlib import Path
from datetime import datetime

# ------------------------------------------------------------------
# 协议常量
# ------------------------------------------------------------------

SIGNAL_DISPLAY_FRAME_LEN = 66
SIGNAL_DISPLAY_MAGIC = 0x55AA55AA

# 模式映射
MODE_MAP = {
    0: "DTO",
    1: "ATO", 
    2: "AR",
    3: "SM",
    4: "RM",
    -1: "RM"
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

# 状态映射
STATE_MAP = {
    -1: "非法",
    0: "关闭",
    1: "开启"
}

# 格式字符串
SIGNAL_DISPLAY_FMT = "<IHHQHHHHHHHHHHHHBBBBBBBffHHBBBBBHHf"

# ------------------------------------------------------------------
# 日志配置
# ------------------------------------------------------------------

def setup_logging():
    """配置日志输出"""
    Path("logs").mkdir(exist_ok=True)
    log_file = Path("logs") / f"signal_display_{time.strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    return logging.getLogger("signal_display_debug")

logger = setup_logging()

# ------------------------------------------------------------------
# 简单的TCP服务器实现
# ------------------------------------------------------------------

class SimpleSignalDisplayServer:
    """简单的TCP服务器，用于接收66字节帧"""
    
    def __init__(self, host="0.0.0.0", port=9999, log_dir="logs"):
        self.host = host
        self.port = port
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self._server_socket = None
        self._running = False
        self._accept_thread = None
        self._clients = {}
        self._clients_lock = threading.Lock()
        
        # 统计
        self._recv_count = 0
        self._send_count = 0
        self._drop_count = 0
        self._error_count = 0
        self._last_recv_at = None
        
        # 日志文件
        ts = time.strftime("%Y%m%d_%H%M%S")
        self._log_file = open(self.log_dir / f"signal_server_{ts}.log", "w", encoding="utf-8")
        self._hex_file = open(self.log_dir / f"signal_server_{ts}_hex.txt", "w", encoding="utf-8")
    
    def start(self):
        """启动服务器"""
        if self._running:
            logger.warning("服务器已在运行")
            return
        
        self._running = True
        self._accept_thread = threading.Thread(
            target=self._accept_loop,
            daemon=True,
            name="SignalDisplay-Accept"
        )
        self._accept_thread.start()
        
        logger.info(f"信号屏服务器启动在 {self.host}:{self.port}")
    
    def stop(self):
        """停止服务器"""
        self._running = False
        
        # 关闭所有客户端
        with self._clients_lock:
            for sock in list(self._clients.keys()):
                try:
                    sock.close()
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
        
        # 关闭文件
        if self._log_file:
            self._log_file.close()
        if self._hex_file:
            self._hex_file.close()
        
        logger.info(f"服务器已停止 (接收: {self._recv_count}, 发送: {self._send_count})")
    
    def status(self):
        """获取状态"""
        with self._clients_lock:
            client_count = len(self._clients)
        
        return {
            "running": self._running,
            "client_count": client_count,
            "recv_count": self._recv_count,
            "send_count": self._send_count,
            "drop_count": self._drop_count,
            "error_count": self._error_count,
            "last_recv_at": self._last_recv_at,
        }
    
    def get_connected_clients(self):
        """获取客户端列表"""
        with self._clients_lock:
            return [
                {
                    "address": info["address"],
                    "connected_at": info["connected_at"],
                    "recv_count": info["recv_count"],
                    "last_recv_at": info.get("last_recv_at")
                }
                for info in self._clients.values()
            ]
    
    def _accept_loop(self):
        """接受客户端连接"""
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self.host, self.port))
            self._server_socket.listen(5)
            self._server_socket.settimeout(1.0)
            
            logger.info(f"TCP Server监听在 {self.host}:{self.port}")
            
            while self._running:
                try:
                    client_socket, client_address = self._server_socket.accept()
                    logger.info(f"客户端连接: {client_address}")
                    
                    # 添加客户端到管理列表
                    with self._clients_lock:
                        self._clients[client_socket] = {
                            "address": client_address,
                            "connected_at": time.time(),
                            "recv_count": 0,
                            "last_recv_at": None
                        }
                    
                    # 启动客户端处理线程
                    threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_address),
                        daemon=True
                    ).start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self._running:
                        logger.error(f"接受连接错误: {e}")
                        time.sleep(1)
                        
        except Exception as e:
            logger.error(f"服务器socket错误: {e}")
        finally:
            if self._server_socket:
                try:
                    self._server_socket.close()
                except:
                    pass
                self._server_socket = None
    
    def _handle_client(self, client_socket, client_address):
        """处理客户端连接"""
        try:
            client_socket.settimeout(2.0)
            
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
                        if client_socket in self._clients:
                            client_info = self._clients[client_socket]
                            client_info["recv_count"] += 1
                            client_info["last_recv_at"] = self._last_recv_at
                    
                    # 记录原始数据
                    hex_str = raw.hex()
                    self._hex_file.write(f"{self._last_recv_at:.6f}|{client_address}|{hex_str}\n")
                    self._hex_file.flush()
                    
                    # 解析帧
                    parsed = self._parse_frame(raw, client_address)
                    
                    # 记录解析结果
                    if parsed:
                        log_entry = {
                            "timestamp": self._last_recv_at,
                            "client": str(client_address),
                            "speed": parsed.get("speed", 0),
                            "acceleration": parsed.get("acceleration", 0),
                            "mode": parsed.get("mode", "RM"),
                            "current_station": parsed.get("current_station_name", "未知"),
                            "train_no": parsed.get("train_no", 0),
                        }
                        self._log_file.write(f"{log_entry}\n")
                        self._log_file.flush()
                        
                        # 每10帧显示一次
                        if self._recv_count % 10 == 0:
                            logger.info(
                                f"[{client_address}] 速度: {parsed.get('speed', 0):.1f}km/h "
                                f"模式: {parsed.get('mode', 'RM')} "
                                f"当前站: {parsed.get('current_station_name', '未知')}"
                            )
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"处理客户端 {client_address} 错误: {e}")
                    self._error_count += 1
                    break
                    
        except Exception as e:
            logger.error(f"客户端处理器错误 {client_address}: {e}")
        finally:
            with self._clients_lock:
                if client_socket in self._clients:
                    del self._clients[client_socket]
            
            try:
                client_socket.close()
            except:
                pass
            
            logger.info(f"客户端断开: {client_address}")
    
    def _recv_exact(self, sock, n):
        """精确接收n字节"""
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
    
    def _parse_frame(self, raw, client_address):
        """解析66字节帧"""
        if len(raw) != SIGNAL_DISPLAY_FRAME_LEN:
            logger.warning(f"帧长度错误: {len(raw)} != {SIGNAL_DISPLAY_FRAME_LEN}")
            return None
        
        try:
            fields = struct.unpack(SIGNAL_DISPLAY_FMT, raw)
            
            # 验证帧头
            if fields[0] != SIGNAL_DISPLAY_MAGIC:
                logger.warning(f"Magic错误: 0x{fields[0]:08X} != 0x{SIGNAL_DISPLAY_MAGIC:08X}")
                return None
            
            # 提取关键字段
            speed = fields[22]  # 速度
            acceleration = fields[23]  # 加速度
            speed_limit = fields[25]  # 限速
            
            # 模式
            mode_value = fields[26]
            mode = MODE_MAP.get(mode_value, f"未知({mode_value})")
            
            # 站点
            current_station_id = fields[14]
            current_station = STATION_MAP.get(current_station_id, f"未知({current_station_id})")
            
            # 车号
            train_no = fields[32]
            
            return {
                "speed": speed,
                "acceleration": acceleration,
                "speed_limit": speed_limit,
                "mode": mode,
                "current_station_id": current_station_id,
                "current_station_name": current_station,
                "train_no": train_no,
            }
            
        except struct.error as e:
            logger.warning(f"解析帧错误: {e}")
            return None

# ------------------------------------------------------------------
# 模拟客户端
# ------------------------------------------------------------------

def create_test_frame(**kwargs):
    """创建66字节测试帧"""
    now = time.localtime()
    timestamp_ms = int(time.time() * 1000)
    
    data = {
        "uIdentify": SIGNAL_DISPLAY_MAGIC,
        "uTotalLen": SIGNAL_DISPLAY_FRAME_LEN,
        "uDataLen": 50,
        "timestamp": timestamp_ms,
        "uVerifyType": 0,
        "uVerifyCode": 0,
        "uProtocolID": 1,
        "uMsgID": 1,
        "hYear": now.tm_year,
        "hMonth": now.tm_mon,
        "hDay": now.tm_mday,
        "hHour": now.tm_hour,
        "hMinute": now.tm_min,
        "hSec": now.tm_sec,
        "nCurrStationID": kwargs.get("current_station_id", 3),
        "nNextStationID": kwargs.get("next_station_id", 4),
        "nEndStationID": kwargs.get("end_station_id", 13),
        "nCMState": 1,
        "nMMState": 1,
        "nCTCState": 1,
        "nRunDir": kwargs.get("direction", 0),
        "nReserve": 0,
        "nSpeed": kwargs.get("speed", 45.5),
        "fAcceleration": kwargs.get("acceleration", 0.2),
        "nPullSwitch": 0,
        "fSpeedLimit": kwargs.get("speed_limit", 80.0),
        "nMode": kwargs.get("mode", 1),
        "nPullState": 1,
        "nBrakeState": 0,
        "nUrgencyStopState": 0,
        "nEventID": 0,
        "nSigState": 0,
        "nTrainNo": kwargs.get("train_no", 1001),
        "fNextStationDist": kwargs.get("next_station_distance", 1250.5),
    }
    
    try:
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
        
        if len(frame) != SIGNAL_DISPLAY_FRAME_LEN:
            logger.error(f"帧长度错误: {len(frame)} != {SIGNAL_DISPLAY_FRAME_LEN}")
            return None
            
        return frame
        
    except struct.error as e:
        logger.error(f"打包帧错误: {e}")
        return None

# ------------------------------------------------------------------
# 命令行接口
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="信号屏TCP服务器调试工具")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 服务器模式
    server_parser = subparsers.add_parser("server", help="启动TCP服务器")
    server_parser.add_argument("--host", default="0.0.0.0", help="监听IP (默认: 0.0.0.0)")
    server_parser.add_argument("--port", type=int, default=9999, help="端口 (默认: 9999)")
    server_parser.add_argument("--log-dir", default="logs", help="日志目录")
    
    # 客户端模式
    client_parser = subparsers.add_parser("client", help="启动模拟客户端")
    client_parser.add_argument("--host", default="127.0.0.1", help="服务器IP")
    client_parser.add_argument("--port", type=int, default=9999, help="服务器端口")
    client_parser.add_argument("--interval", type=float, default=0.1, help="发送间隔(秒)")
    client_parser.add_argument("--count", type=int, default=0, help="发送次数(0=无限)")
    
    # 十六进制解析
    hex_parser = subparsers.add_parser("hexview", help="解析十六进制数据")
    hex_parser.add_argument("hex_string", help="66字节的十六进制字符串")
    
    args = parser.parse_args()
    
    if not args.command:
        print("请指定命令: server | client | hexview")
        print("使用 --help 查看详细帮助")
        return
    
    print("\n" + "="*80)
    print("信号屏（MMI）TCP 服务器调试工具")
    print("="*80)
    
    if args.command == "server":
        run_server(args)
    elif args.command == "client":
        run_client(args)
    elif args.command == "hexview":
        parse_hex(args.hex_string)

def run_server(args):
    """运行服务器"""
    logger.info(f"启动信号屏服务器: {args.host}:{args.port}")
    
    server = SimpleSignalDisplayServer(
        host=args.host,
        port=args.port,
        log_dir=args.log_dir
    )
    
    server.start()
    
    print(f"\n服务器已启动在 {args.host}:{args.port}")
    print("等待信号屏连接...")
    print("按 Ctrl+C 停止\n")
    
    try:
        while True:
            time.sleep(1)
            status = server.status()
            clients = server.get_connected_clients()
            
            print(f"\r状态: 运行中 | 客户端: {status['client_count']} | "
                  f"接收帧: {status['recv_count']} | "
                  f"最后接收: {datetime.fromtimestamp(status['last_recv_at']).strftime('%H:%M:%S') if status['last_recv_at'] else '无'}",
                  end="")
                  
    except KeyboardInterrupt:
        print("\n\n正在停止服务器...")
    finally:
        server.stop()

def run_client(args):
    """运行客户端"""
    logger.info(f"启动模拟客户端连接到 {args.host}:{args.port}")
    
    sent_count = 0
    speed = 30.0
    
    try:
        while True:
            if args.count > 0 and sent_count >= args.count:
                break
                
            # 连接到服务器
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            
            try:
                sock.connect((args.host, args.port))
                
                while True:
                    if args.count > 0 and sent_count >= args.count:
                        break
                    
                    # 创建测试帧
                    frame = create_test_frame(
                        speed=speed,
                        acceleration=0.1,
                        speed_limit=80.0,
                        mode=1,
                        current_station_id=3,
                        train_no=1001,
                        next_station_distance=1500.0
                    )
                    
                    if frame:
                        sock.sendall(frame)
                        sent_count += 1
                        
                        if sent_count % 10 == 0:
                            logger.info(f"已发送 {sent_count} 帧, 当前速度: {speed:.1f}km/h")
                        
                        # 模拟速度变化
                        speed += 0.5
                        if speed > 80.0:
                            speed = 20.0
                    
                    time.sleep(args.interval)
                    
            except ConnectionRefusedError:
                logger.error(f"无法连接到服务器 {args.host}:{args.port}")
                logger.info("5秒后重试...")
                time.sleep(5)
                continue
                
            except socket.timeout:
                logger.error("连接超时")
                time.sleep(5)
                continue
                
            finally:
                sock.close()
                
    except KeyboardInterrupt:
        logger.info(f"用户中断，已发送 {sent_count} 帧")
    finally:
        logger.info(f"客户端停止，总共发送 {sent_count} 帧")

def parse_hex(hex_string):
    """解析十六进制数据"""
    hex_string = hex_string.replace(" ", "").replace("\n", "").replace("\r", "")
    
    if len(hex_string) != SIGNAL_DISPLAY_FRAME_LEN * 2:
        print(f"错误: 十六进制长度应为 {SIGNAL_DISPLAY_FRAME_LEN*2} 字符，实际为 {len(hex_string)}")
        return
    
    try:
        raw = bytes.fromhex(hex_string)
        fields = struct.unpack(SIGNAL_DISPLAY_FMT, raw)
        
        print("\n" + "="*80)
        print("66字节信号屏帧解析结果")
        print("="*80)
        
        print(f"Magic: 0x{fields[0]:08X} {'✓' if fields[0] == SIGNAL_DISPLAY_MAGIC else '✗'}")
        print(f"时间戳: {fields[3]} ms")
        print(f"时间: {fields[8]}/{fields[9]:02d}/{fields[10]:02d} {fields[11]:02d}:{fields[12]:02d}:{fields[13]:02d}")
        print(f"当前站: {STATION_MAP.get(fields[14], f'未知({fields[14]})')}")
        print(f"速度: {fields[22]:.1f} km/h")
        print(f"加速度: {fields[23]:.2f} m/s²")
        print(f"限速: {fields[25]:.1f} km/h")
        print(f"模式: {MODE_MAP.get(fields[26], f'未知({fields[26]})')}")
        print(f"车号: {fields[32]}")
        print(f"距下一站距离: {fields[33]:.1f} 米")
        
        print(f"\n十六进制: {hex_string}")
        
    except ValueError as e:
        print(f"十六进制转换错误: {e}")
    except struct.error as e:
        print(f"帧解析错误: {e}")

if __name__ == "__main__":
    main()