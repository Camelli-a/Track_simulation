"""
信号屏调试工具 - 极简版
==================================

这个版本专注于基础功能，避免复杂的格式问题。

使用方式：
    python test_signal_display.py server     # 启动服务器
    python test_signal_display.py client     # 启动客户端
"""

import socket
import threading
import time
import sys
import struct
from pathlib import Path

# 创建日志目录
Path("logs").mkdir(exist_ok=True)

def start_server(host="0.0.0.0", port=9999):
    """启动TCP服务器"""
    print(f"启动信号屏服务器: {host}:{port}")
    print("等待连接...")
    
    # 创建服务器socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    server_socket.settimeout(1.0)
    
    clients = []
    recv_count = 0
    
    def handle_client(client_socket, client_address):
        """处理客户端连接"""
        nonlocal recv_count
        print(f"客户端连接: {client_address}")
        
        # 打开日志文件
        log_file = open(f"logs/signal_{int(time.time())}.bin", "wb")
        
        try:
            while True:
                try:
                    # 接收数据
                    data = client_socket.recv(1024)
                    if not data:
                        break
                    
                    recv_count += 1
                    
                    # 保存到文件
                    log_file.write(data)
                    log_file.flush()
                    
                    # 显示信息
                    print(f"[{recv_count}] 从 {client_address} 收到 {len(data)} 字节")
                    
                    # 尝试解析为66字节帧
                    if len(data) >= 66:
                        # 显示前几个字节
                        hex_str = data[:66].hex()
                        print(f"  前66字节: {hex_str[:50]}...")
                        
                        # 检查帧头
                        if len(data) >= 4:
                            header = data[:4].hex().upper()
                            if header == "55AA55AA":
                                print(f"  ✓ 有效帧头: 0x{header}")
                            else:
                                print(f"  ✗ 帧头: 0x{header}")
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"接收错误: {e}")
                    break
                    
        except Exception as e:
            print(f"客户端处理错误: {e}")
        finally:
            client_socket.close()
            log_file.close()
            print(f"客户端断开: {client_address}")
    
    try:
        while True:
            try:
                client_socket, client_address = server_socket.accept()
                client_socket.settimeout(2.0)
                
                # 启动客户端线程
                thread = threading.Thread(
                    target=handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                thread.start()
                clients.append(thread)
                
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                break
                
    except KeyboardInterrupt:
        print("\n正在停止服务器...")
    finally:
        server_socket.close()
        print(f"服务器已停止，共接收 {recv_count} 次数据")

def start_client(host="127.0.0.1", port=9999):
    """启动模拟客户端"""
    print(f"连接到服务器: {host}:{port}")
    
    sent_count = 0
    
    # 创建一个简单的66字节测试帧
    def create_test_frame():
        # 帧头: 55 AA 55 AA
        frame = bytes.fromhex("55AA55AA")
        
        # 总长度: 66 (0x0042)
        frame += (66).to_bytes(2, 'little')
        
        # 数据长度: 50 (0x0032)
        frame += (50).to_bytes(2, 'little')
        
        # 时间戳 (8字节)
        timestamp = int(time.time() * 1000)
        frame += timestamp.to_bytes(8, 'little')
        
        # 填充其他字段（简化的测试数据）
        # 时间: 2024-07-12 10:00:00
        frame += bytes.fromhex("07E8 0007 000C 000A 0000 0000".replace(" ", ""))
        
        # 站点信息
        frame += bytes([3, 4, 13])  # 当前站、下一站、终点站
        
        # 状态信息
        frame += bytes([1, 1, 1, 0, 0])  # CM, MM, CTC状态，方向，预留
        
        # 速度: 45.5 km/h (float)
        import struct
        frame += struct.pack('<f', 45.5)
        
        # 加速度: 0.2 m/s²
        frame += struct.pack('<f', 0.2)
        
        # 牵引切除: 0 (正常)
        frame += (0).to_bytes(2, 'little')
        
        # 限速: 80.0 km/h
        frame += (80).to_bytes(2, 'little')
        
        # 模式: 1 (ATO)
        frame += bytes([1])
        
        # 牵引状态: 1 (开启)
        frame += bytes([1])
        
        # 制动状态: 0 (关闭)
        frame += bytes([0])
        
        # 紧急制动: 0 (关闭)
        frame += bytes([0])
        
        # 事件ID: 0
        frame += bytes([0])
        
        # 信号状态: 0
        frame += bytes([0])
        
        # 车号: 1001
        frame += (1001).to_bytes(2, 'little')
        
        # 距下一站距离: 1250.5米
        frame += struct.pack('<f', 1250.5)
        
        # 确保长度是66字节
        if len(frame) < 66:
            frame += b'\x00' * (66 - len(frame))
        
        return frame[:66]
    
    try:
        while True:
            try:
                # 连接到服务器
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((host, port))
                
                print(f"连接成功，开始发送数据...")
                
                while True:
                    # 创建测试帧
                    frame = create_test_frame()
                    
                    # 发送数据
                    sock.sendall(frame)
                    sent_count += 1
                    
                    # 显示进度
                    if sent_count % 10 == 0:
                        print(f"已发送 {sent_count} 帧")
                    
                    # 等待0.1秒
                    time.sleep(0.1)
                    
            except ConnectionRefusedError:
                print(f"无法连接到服务器 {host}:{port}")
                print("5秒后重试...")
                time.sleep(5)
                continue
                
            except socket.timeout:
                print("连接超时，重新连接...")
                time.sleep(2)
                continue
                
            except Exception as e:
                print(f"错误: {e}")
                break
                
    except KeyboardInterrupt:
        print(f"\n已发送 {sent_count} 帧")
    finally:
        print("客户端已停止")

def parse_hex_data(hex_string):
    """解析十六进制数据"""
    hex_string = hex_string.replace(" ", "").replace("\n", "").replace("\r", "")
    
    print(f"\n解析十六进制数据 ({len(hex_string)} 字符)")
    
    if len(hex_string) < 8:
        print("数据太短")
        return
    
    # 检查帧头
    header = hex_string[:8].upper()
    print(f"帧头: 0x{header}")
    
    if header == "55AA55AA":
        print("✓ 有效帧头")
    else:
        print("✗ 无效帧头")
    
    # 显示前32字节
    print(f"前32字节: {hex_string[:64]}")
    
    # 尝试解析为字节
    try:
        data = bytes.fromhex(hex_string)
        print(f"总长度: {len(data)} 字节")
        
        # 如果长度是66，尝试解析关键字段
        if len(data) >= 66:
            # 速度字段（假设在偏移44-47）
            if len(data) >= 48:
                speed_bytes = data[44:48]
                try:
                    speed = struct.unpack('<f', speed_bytes)[0]
                    print(f"速度: {speed:.1f} km/h")
                except:
                    pass
        
    except ValueError:
        print("无效的十六进制数据")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python test_signal_display.py server [host] [port]")
        print("  python test_signal_display.py client [host] [port]")
        print("  python test_signal_display.py hex [十六进制数据]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "server":
        host = sys.argv[2] if len(sys.argv) > 2 else "0.0.0.0"
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 9999
        start_server(host, port)
        
    elif command == "client":
        host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 9999
        start_client(host, port)
        
    elif command == "hex":
        if len(sys.argv) < 3:
            print("请提供十六进制数据")
            sys.exit(1)
        parse_hex_data(sys.argv[2])
        
    else:
        print(f"未知命令: {command}")