"""
信号屏（MMI）TCP 服务器调试脚本
===================================

严格依据《司机驾驶模拟台信号屏协议》实现：
- 信号显示屏（MMI）作为 TCP Client 连接上位机（TCP Server）
- IP: 192.168.100.121 Port: 9999
- 总长: 66字节定长报文

使用方式：
    python debug_signal_display.py server      # 启动服务器
    python debug_signal_display.py client      # 启动测试客户端
    python debug_signal_display.py sendtest    # 发送测试数据到已运行的服务器
    python debug_signal_display.py hexview     # 解析十六进制数据

功能：
1. 启动TCP Server监听信号屏连接
2. 模拟信号屏客户端发送数据
3. 解析66字节帧数据并显示
4. 支持网络抓包格式数据解析
"""

import argparse
import json
import socket
import struct
import threading
import time
import sys
import logging
from pathlib import Path
from datetime import datetime

# 导入现有信号屏服务器（用于测试）
sys.path.insert(0, str(Path(__file__).parent))

# 临时定义常量，避免导入错误
SIGNAL_DISPLAY_FRAME_LEN = 66
SIGNAL_DISPLAY_MAGIC = 0x55AA55AA

# 尝试导入模块
try:
    from app.communication.signal_display_server import (
        SignalDisplayServer, 
        SIGNAL_DISPLAY_FMT,
        MODE_MAP,
        STATION_MAP,
        DIRECTION_MAP,
        STATE_MAP
    )
    print("成功导入信号屏服务器模块")
except ImportError as e:
    print(f"导入错误: {e}")
    print("使用默认值继续...")
    SIGNAL_DISPLAY_FMT = "<IHHQHHHHHHHHHHHHBBBBBBBffHHBBBBBHHf"
    MODE_MAP = {0: "DTO", 1: "ATO", 2: "AR", 3: "SM", 4: "RM", -1: "RM"}
    STATION_MAP = {
        1: "车公庄", 2: "丰台科技园", 3: "科怡路", 4: "丰台南路",
        5: "丰台东大街", 6: "七里庄", 7: "六里桥", 8: "六里桥东",
        9: "北京西", 10: "军事博物馆", 11: "白堆子", 12: "白石桥南",
        13: "国家图书馆"
    }
    DIRECTION_MAP = {-1: "非法", 0: "上行", 1: "下行"}
    STATE_MAP = {-1: "非法", 0: "关闭", 1: "开启"}
    SignalDisplayServer = None

# ------------------------------------------------------------------
# 日志配置
# ------------------------------------------------------------------

def setup_logging():
    """配置日志输出"""
    Path("logs").mkdir(exist_ok=True)
    log_file = Path("logs") / f"signal_display_debug_{time.strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    return logging.getLogger("debug_signal_display")

logger = setup_logging()

# ------------------------------------------------------------------
# 简单的TCP服务器实现（当SignalDisplayServer导入失败时使用）
# ------------------------------------------------------------------

class SimpleTCPServer:
    """简单的TCP服务器，用于接收66字节帧"""
    
    def __init__(self, host="0.0.0.0", port=9999, log_dir="logs"):
        self.host = host
        self.port = port
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self._server_socket = None
        self._running = False
        self._clients = {}
        self._clients_lock = threading.Lock()
        
        # 统计
        self._recv_count = 0
        self._last_recv_at = None
        
        # 日志文件
        ts = time.strftime("%Y%m%d_%H%M%S")
        self._log_file = open(self.log_dir / f"simple_signal_{ts}.log", "w", encoding="utf-8")
    
    def start(self):
        """启动服务器"""
        if self._running:
            return
        
        self._running = True
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(5)
        self._server_socket.settimeout(1.0)
        
        threading.Thread(target=self._accept_loop, daemon=True).start()
        logger.info(f"简单TCP服务器启动在 {self.host}:{self.port}")
    
    def stop(self):
        """停止服务器"""
        self._running = False
        if self._server_socket:
            self._server_socket.close()
        if self._log_file:
            self._log_file.close()
    
    def _accept_loop(self):
        """接受客户端连接"""
        while self._running:
            try:
                client_socket, client_address = self._server_socket.accept()
                logger.info(f"客户端连接: {client_address}")
                
                with self._clients_lock:
                    self._clients[client_socket] = {
                        "address": client_address,
                        "connected_at": time.time(),
                        "recv_count": 0
                    }
                
                threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                ).start()
                
            except socket.timeout:
                continue
            except Exception:
                if self._running:
                    break
    
    def _handle_client(self, client_socket, client_address):
        """处理客户端"""
        try:
            while self._running:
                # 接收66字节
                data = client_socket.recv(66)
                if not data:
                    break
                
                self._recv_count += 1
                self._last_recv_at = time.time()
                
                # 记录到日志
                self._log_file.write(f"{time.time():.6f}|{client_address}|{data.hex()}\n")
                self._log_file.flush()
                
                # 更新客户端统计
                with self._clients_lock:
                    if client_socket in self._clients:
                        self._clients[client_socket]["recv_count"] += 1
                
                # 尝试解析数据
                if len(data) == 66:
                    try:
                        fields = struct.unpack(SIGNAL_DISPLAY_FMT, data)
                        if fields[0] == SIGNAL_DISPLAY_MAGIC:
                            logger.debug(f"收到有效帧: 速度={fields[22]:.1f}km/h")
                    except:
                        pass
                        
        except Exception:
            pass
        finally:
            with self._clients_lock:
                if client_socket in self._clients:
                    del self._clients[client_socket]
            client_socket.close()
    
    def status(self):
        """获取状态"""
        with self._clients_lock:
            client_count = len(self._clients)
        
        return {
            "running": self._running,
            "client_count": client_count,
            "recv_count": self._recv_count,
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

# ------------------------------------------------------------------
# 命令行参数解析
# ------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="信号屏TCP服务器调试工具")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 服务器模式
    server_parser = subparsers.add_parser("server", help="启动TCP服务器")
    server_parser.add_argument("--host", default="0.0.0.0", help="服务器监听IP (默认: 0.0.0.0)")
    server_parser.add_argument("--port", type=int, default=9999, help="服务器端口 (默认: 9999)")
    server_parser.add_argument("--no-zmq", action="store_true", help="不使用ZMQ消息总线")
    server_parser.add_argument("--log-dir", default="logs", help="日志目录")
    server_parser.add_argument("--send-interval", type=float, default=1.0, 
                               help="自动发送数据到信号屏的间隔(秒)")
    
    # 客户端模式
    client_parser = subparsers.add_parser("client", help="启动模拟客户端")
    client_parser.add_argument("--host", default="127.0.0.1", help="服务器IP")
    client_parser.add_argument("--port", type=int, default=9999, help="服务器端口")
    client_parser.add_argument("--interval", type=float, default=0.1, 
                               help="发送间隔(秒, 默认: 0.1秒=10Hz)")
    client_parser.add_argument("--count", type=int, default=0, 
                               help="发送次数(0=无限, 默认: 0)")
    
    # 发送测试数据
    send_parser = subparsers.add_parser("sendtest", help="发送测试数据到运行的服务器")
    send_parser.add_argument("--host", default="127.0.0.1", help="服务器IP")
    send_parser.add_argument("--port", type=int, default=9999, help="服务器端口")
    send_parser.add_argument("--speed", type=float, default=45.5, help="速度(km/h)")
    send_parser.add_argument("--accel", type=float, default=0.2, help="加速度(m/s²)")
    send_parser.add_argument("--limit", type=float, default=80.0, help="限速(km/h)")
    send_parser.add_argument("--mode", type=int, default=1, help="模式: 0=DTO,1=ATO,2=AR,3=SM,4=RM")
    send_parser.add_argument("--station", type=int, default=3, help="当前站ID (1-13)")
    send_parser.add_argument("--train", type=int, default=1001, help="车号")
    send_parser.add_argument("--distance", type=float, default=1250.5, help="距下一站距离(米)")
    
    # 十六进制解析
    hex_parser = subparsers.add_parser("hexview", help="解析十六进制数据")
    hex_parser.add_argument("hex_string", help="66字节的十六进制字符串")
    
    return parser.parse_args()

# ------------------------------------------------------------------
# 模拟信号屏客户端
# ------------------------------------------------------------------

def create_test_frame(**kwargs):
    """创建66字节测试帧"""
    # 获取当前时间
    now = time.localtime()
    timestamp_ms = int(time.time() * 1000)
    
    # 设置默认值
    data = {
        # 帧头信息
        "uIdentify": SIGNAL_DISPLAY_MAGIC,
        "uTotalLen": SIGNAL_DISPLAY_FRAME_LEN,
        "uDataLen": SIGNAL_DISPLAY_FRAME_LEN - 16,  # 总长减去帧头部分
        "timestamp": timestamp_ms,
        
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
        
        # 站点信息
        "nCurrStationID": kwargs.get("current_station_id", 3),
        "nNextStationID": kwargs.get("next_station_id", 4),
        "nEndStationID": kwargs.get("end_station_id", 13),
        
        # 系统状态
        "nCMState": kwargs.get("cm_state", 1),   # 开启
        "nMMState": kwargs.get("mm_state", 1),   # 开启
        "nCTCState": kwargs.get("ctc_state", 1), # 开启
        "nRunDir": kwargs.get("direction", 0),   # 上行
        "nReserve": 0,
        
        # 运行状态
        "nSpeed": kwargs.get("speed", 45.5),
        "fAcceleration": kwargs.get("acceleration", 0.2),
        "nPullSwitch": kwargs.get("pull_switch", 0),  # 0:正常
        "fSpeedLimit": kwargs.get("speed_limit", 80.0),
        "nMode": kwargs.get("mode", 1),  # ATO
        
        # 车辆状态
        "nPullState": kwargs.get("pull_state", 1),  # 开启
        "nBrakeState": kwargs.get("brake_state", 0),  # 关闭
        "nUrgencyStopState": kwargs.get("urgency_stop_state", 0),  # 关闭
        
        # 其他信息
        "nEventID": kwargs.get("event_id", 0),
        "nSigState": kwargs.get("signal_state", 0),
        "nTrainNo": kwargs.get("train_no", 1001),
        "fNextStationDist": kwargs.get("next_station_distance", 1250.5),
    }
    
    # 构建帧
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

def parse_hex_frame(hex_string: str):
    """解析十六进制字符串为帧数据"""
    try:
        # 移除可能的空格和换行
        hex_string = hex_string.replace(" ", "").replace("\n", "").replace("\r", "")
        
        # 转换为字节
        if len(hex_string) != SIGNAL_DISPLAY_FRAME_LEN * 2:
            logger.error(f"十六进制长度错误: {len(hex_string)} 字符 != {SIGNAL_DISPLAY_FRAME_LEN*2}")
            return None
            
        raw = bytes.fromhex(hex_string)
        
        # 解析帧
        fields = struct.unpack(SIGNAL_DISPLAY_FMT, raw)
        
        # 显示解析结果
        print("\n" + "="*80)
        print("66字节信号屏帧解析结果")
        print("="*80)
        
        # 帧头信息
        print("\n帧头信息:")
        print(f"  Magic: 0x{fields[0]:08X} {'✓' if fields[0] == SIGNAL_DISPLAY_MAGIC else '✗'}")
        print(f"  总长度: {fields[1]} 字节")
        print(f"  数据长度: {fields[2]} 字节")
        print(f"  时间戳: {fields[3]} ms")
        print(f"  校验类型: {fields[4]}")
        print(f"  校验码: {fields[5]}")
        print(f"  协议ID: {fields[6]}")
        print(f"  消息ID: {fields[7]}")
        
        # 时间信息
        print(f"\n时间信息: {fields[8]}/{fields[9]:02d}/{fields[10]:02d} {fields[11]:02d}:{fields[12]:02d}:{fields[13]:02d}")
        
        # 站点信息
        print("\n站点信息:")
        print(f"  当前站: {STATION_MAP.get(fields[14], f'未知({fields[14]})')}")
        print(f"  下一站: {STATION_MAP.get(fields[15], f'未知({fields[15]})')}")
        print(f"  终点站: {STATION_MAP.get(fields[16], f'未知({fields[16]})')}")
        
        # 系统状态
        print("\n系统状态:")
        print(f"  CM状态: {STATE_MAP.get(fields[17], f'未知({fields[17]})')}")
        print(f"  MM状态: {STATE_MAP.get(fields[18], f'未知({fields[18]})')}")
        print(f"  CTC状态: {STATE_MAP.get(fields[19], f'未知({fields[19]})')}")
        print(f"  运行方向: {DIRECTION_MAP.get(fields[20], f'未知({fields[20]})')}")
        
        # 运行状态
        print("\n运行状态:")
        print(f"  速度: {fields[21]:.1f} km/h")
        print(f"  加速度: {fields[22]:.2f} m/s²")
        print(f"  牵引切除: {'切除' if fields[23] == 1 else '正常'}")
        print(f"  限速: {fields[24]:.1f} km/h")
        
        # 模式
        mode_value = fields[25]
        mode_str = MODE_MAP.get(mode_value, f'未知({mode_value})')
        print(f"  模式: {mode_str} (原始值: {mode_value})")
        
        # 车辆状态
        print("\n车辆状态:")
        print(f"  牵引状态: {STATE_MAP.get(fields[26], f'未知({fields[26]})')}")
        print(f"  制动状态: {STATE_MAP.get(fields[27], f'未知({fields[27]})')}")
        print(f"  紧急制动: {STATE_MAP.get(fields[28], f'未知({fields[28]})')}")
        
        # 其他信息
        print("\n其他信息:")
        print(f"  事件ID: {fields[29]}")
        print(f"  信号状态: 0x{fields[30]:02X}")
        print(f"  车号: {fields[31]}")
        print(f"  距下一站距离: {fields[32]:.1f} 米")
        
        # 十六进制显示
        print("\n十六进制格式:")
        hex_display = raw.hex()
        for i in range(0, len(hex_display), 32):
            print(f"  {hex_display[i:i+32]}")
        
        return True
        
    except ValueError as e:
        logger.error(f"十六进制转换错误: {e}")
        return None
    except struct.error as e:
        logger.error(f"帧解析错误: {e}")
        return None

# ------------------------------------------------------------------
# 服务器模式
# ------------------------------------------------------------------

def run_server_mode(args):
    """运行服务器模式"""
    logger.info(f"启动信号屏TCP服务器: {args.host}:{args.port}")
    logger.info(f"日志目录: {args.log_dir}")
    logger.info(f"发送间隔: {args.send_interval}秒")
    logger.info(f"不使用ZMQ: {args.no_zmq}")
    
    if SignalDisplayServer is None:
        logger.error("无法导入SignalDisplayServer，请检查信号屏服务器模块")
        logger.info("尝试直接启动TCP服务器...")
        # 如果导入失败，创建一个简单的TCP服务器
        server = None
        simple_server = SimpleTCPServer(args.host, args.port, args.log_dir)
        server_start_func = simple_server.start
        server_stop_func = simple_server.stop
        server_status_func = simple_server.status
        server_get_clients_func = simple_server.get_connected_clients
    else:
        server = SignalDisplayServer(
            host=args.host,
            port=args.port,
            bus=None if args.no_zmq else None,  # 使用默认总线
            record_dir=args.log_dir,
            record_raw=True,
        )
        server_start_func = server.start
        server_stop_func = server.stop
        server_status_func = server.status
        server_get_clients_func = server.get_connected_clients
    
    # 启动服务器
    server.start()
    
    print("\n" + "="*80)
    print("信号屏服务器已启动")
    print(f"监听地址: {args.host}:{args.port}")
    print("="*80)
    print("等待信号屏连接...")
    print("按 Ctrl+C 停止服务器")
    print("-"*80)
    
    last_stats_time = time.time()
    
    try:
        while True:
            time.sleep(0.5)
            
            # 显示统计信息
            current_time = time.time()
            if current_time - last_stats_time >= 1.0:
                last_stats_time = current_time
                
                status = server.status()
                clients = server.get_connected_clients()
                
                # 清屏显示
                print("\033[2J\033[H", end="")  # 清屏
                
                print(f"信号屏服务器状态 - {datetime.now().strftime('%H:%M:%S')}")
                print("="*80)
                print(f"监听地址: {args.host}:{args.port}")
                print(f"运行中: {'是' if status['running'] else '否'}")
                print(f"客户端数: {status['client_count']}")
                print(f"接收帧数: {status['recv_count']}")
                print(f"发送帧数: {status['send_count']}")
                print(f"丢弃帧数: {status['drop_count']}")
                print(f"错误数: {status['error_count']}")
                print(f"最后接收时间: {status['last_recv_at']}")
                
                # 显示连接的客户端
                if clients:
                    print(f"\n连接的客户端 ({len(clients)}):")
                    for i, client in enumerate(clients, 1):
                        print(f"  {i}. 地址: {client['address']}")
                        print(f"     连接时间: {datetime.fromtimestamp(client['connected_at']).strftime('%H:%M:%S')}")
                        print(f"     接收帧数: {client['recv_count']}")
                        print(f"     最后接收: {datetime.fromtimestamp(client['last_recv_at']).strftime('%H:%M:%S') if client['last_recv_at'] else '无'}")
                else:
                    print("\n无客户端连接")
                
                print("\n操作:")
                print("  Ctrl+C - ���止服务器")
                print("  1      - 发送测试数据到所有客户端")
                print("  2      - 查看最近接收的数据")
                print("-"*80)
            
    except KeyboardInterrupt:
        logger.info("收到停止信号")
    finally:
        server.stop()
        logger.info("服务器已停止")

# ------------------------------------------------------------------
# 客户端模式
# ------------------------------------------------------------------

def run_client_mode(args):
    """运行客户端模式（模拟信号屏）"""
    logger.info(f"启动模拟信号屏客户端")
    logger.info(f"连接服务器: {args.host}:{args.port}")
    logger.info(f"发送间隔: {args.interval}秒 (约{1/args.interval:.1f} Hz)")
    logger.info(f"发送次数: {'无限' if args.count == 0 else args.count}")
    
    # 测试参数
    test_params = {
        "speed": 45.5,
        "acceleration": 0.2,
        "speed_limit": 80.0,
        "mode": 1,  # ATO
        "current_station_id": 3,
        "next_station_id": 4,
        "end_station_id": 13,
        "next_station_distance": 1250.5,
        "train_no": 1001,
        "direction": 0,  # 上行
    }
    
    sent_count = 0
    
    try:
        while True:
            # 连接到服务器
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            
            try:
                sock.connect((args.host, args.port))
                logger.info(f"已连接到服务器 {args.host}:{args.port}")
                
                # 持续发送数据
                while True:
                    if args.count > 0 and sent_count >= args.count:
                        logger.info(f"达到发送次数限制: {sent_count}")
                        break
                    
                    # 创建测试帧
                    frame = create_test_frame(**test_params)
                    if not frame:
                        logger.error("创建测试帧失败")
                        break
                    
                    # 发送数据
                    try:
                        sock.sendall(frame)
                        sent_count += 1
                        
                        # 显示发送信息
                        if sent_count % 10 == 0:
                            logger.info(f"已发送 {sent_count} 帧 (速度: {test_params['speed']:.1f}km/h, 模式: ATO)")
                        
                        # 稍微修改测试参数，模拟变化
                        test_params["speed"] += 0.1
                        if test_params["speed"] > 80.0:
                            test_params["speed"] = 20.0
                        
                        test_params["next_station_distance"] -= 10.0
                        if test_params["next_station_distance"] < 0:
                            test_params["next_station_distance"] = 2000.0
                            test_params["current_station_id"] = (test_params["current_station_id"] % 13) + 1
                            test_params["next_station_id"] = (test_params["current_station_id"] % 13) + 1
                    
                    except (BrokenPipeError, ConnectionResetError):
                        logger.warning("连接断开，尝试重新连接")
                        break
                    
                    # 等待下一个发送周期
                    time.sleep(args.interval)
                
            except ConnectionRefusedError:
                logger.error(f"无法连接到服务器 {args.host}:{args.port}")
                logger.info(f"等待 5 秒后重试...")
                time.sleep(5)
                continue
                
            except socket.timeout:
                logger.error("连接超时")
                time.sleep(5)
                continue
                
            finally:
                sock.close()
            
            if args.count > 0 and sent_count >= args.count:
                break
                
    except KeyboardInterrupt:
        logger.info(f"用户中断，已发送 {sent_count} 帧")
    finally:
        logger.info(f"客户端已停止，总共发送 {sent_count} 帧")

# ------------------------------------------------------------------
# 发送测试模式
# ------------------------------------------------------------------

def run_sendtest_mode(args):
    """发送单次测试数据"""
    logger.info(f"发送测试数据到服务器: {args.host}:{args.port}")
    
    # 准备测试数据
    test_params = {
        "speed": args.speed,
        "acceleration": args.accel,
        "speed_limit": args.limit,
        "mode": args.mode,
        "current_station_id": args.station,
        "next_station_id": (args.station % 13) + 1,
        "end_station_id": 13,
        "next_station_distance": args.distance,
        "train_no": args.train,
    }
    
    # 创建测试帧
    frame = create_test_frame(**test_params)
    if not frame:
        logger.error("创建测试帧失败")
        return
    
    print(f"测试帧内容:")
    print(f"  速度: {args.speed:.1f} km/h")
    print(f"  加速度: {args.accel:.2f} m/s²")
    print(f"  限速: {args.limit:.1f} km/h")
    print(f"  模式: {MODE_MAP.get(args.mode, '未知')}")
    print(f"  当前站: {STATION_MAP.get(args.station, '未知')}")
    print(f"  车号: {args.train}")
    print(f"  距下一站距离: {args.distance:.1f} 米")
    
    # 连接到服务器并发送
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((args.host, args.port))
        
        sock.sendall(frame)
        logger.info("测试数据发送成功")
        
        # 也可以显示十六进制格式
        print(f"\n十六进制格式:")
        hex_str = frame.hex()
        for i in range(0, len(hex_str), 32):
            print(f"  {hex_str[i:i+32]}")
        
        sock.close()
        
    except ConnectionRefusedError:
        logger.error(f"无法连接到服务器 {args.host}:{args.port}")
    except socket.timeout:
        logger.error("连接超时")
    except Exception as e:
        logger.error(f"发送失败: {e}")

# ------------------------------------------------------------------
# 主函数
# ------------------------------------------------------------------

def main():
    args = parse_args()
    
    if not args.command:
        print("请指定命令: server | client | sendtest | hexview")
        print("使用 --help 查看详细帮助")
        return
    
    print("\n" + "="*80)
    print("信号屏（MMI）TCP 服务器调试工具")
    print("="*80)
    
    if args.command == "server":
        run_server_mode(args)
    elif args.command == "client":
        run_client_mode(args)
    elif args.command == "sendtest":
        run_sendtest_mode(args)
    elif args.command == "hexview":
        parse_hex_frame(args.hex_string)
    else:
        logger.error(f"未知命令: {args.command}")

if __name__ == "__main__":
    main()
