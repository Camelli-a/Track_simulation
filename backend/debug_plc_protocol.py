"""
PLC协议调试脚本
测试不同的连接参数和握手协议
"""
import socket
import time
import struct
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def test_connection_with_params(host, port, connect_timeout=5, recv_timeout=10, send_init=False):
    """测试不同参数的PLC连接"""
    print(f"\n{'='*60}")
    print(f"测试连接: {host}:{port}")
    print(f"连接超时: {connect_timeout}s, 接收超时: {recv_timeout}s")
    print(f"发送初始化帧: {send_init}")
    print('='*60)
    
    try:
        # 创建socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(connect_timeout)
        
        # 连接
        start_time = time.time()
        sock.connect((host, port))
        connect_time = time.time() - start_time
        print(f"✅ TCP连接成功 (耗时: {connect_time:.3f}s)")
        
        # 设置接收超时（更长的超时）
        sock.settimeout(recv_timeout)
        
        # 如果需要，发送初始化帧
        if send_init:
            # 尝试发送7.2节上行帧头
            init_frame = b'\x55\xAA\x55\xAA\x00\x1C\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            print(f"发送初始化帧: {init_frame.hex()}")
            sock.send(init_frame)
        
        # 尝试接收数据
        print("等待PLC发送数据...")
        try:
            start_recv = time.time()
            data = sock.recv(1024)
            recv_time = time.time() - start_recv
            
            if data:
                print(f"✅ 收到数据 (等待: {recv_time:.3f}s)")
                print(f"   数据长度: {len(data)} 字节")
                print(f"   十六进制: {data.hex()}")
                
                # 如果是46字节，尝试解析
                if len(data) == 46:
                    print(f"   ✅ 符合46字节协议帧")
                    try:
                        # 尝试解析帧头
                        identify = struct.unpack('<I', data[0:4])[0]
                        total_len = struct.unpack('<H', data[4:6])[0]
                        data_len = struct.unpack('<H', data[6:8])[0]
                        
                        print(f"   帧头: 0x{identify:08X}")
                        print(f"   总长度: {total_len}")
                        print(f"   数据长度: {data_len}")
                        
                        if identify == 0x55AA55AA or identify == 0xAA55AA55:
                            print("   ✅ 帧头验证通过")
                        else:
                            print(f"   ⚠️  非标准帧头: 0x{identify:08X}")
                    except Exception as e:
                        print(f"   ⚠️  解析帧头失败: {e}")
                else:
                    print(f"   ⚠️  数据长度不是46字节: {len(data)}")
            else:
                print("❌ 收到空数据（连接被关闭）")
                
        except socket.timeout:
            print(f"⚠️  接收超时 ({recv_timeout}s内没有数据)")
            # 尝试发送一个测试帧，看看PLC是否响应
            print("尝试发送测试帧...")
            test_frame = b'\x55\xAA\x55\xAA\x00\x1C\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            try:
                sock.send(test_frame)
                print("测试帧发送成功，等待响应...")
                sock.settimeout(2)
                try:
                    response = sock.recv(1024)
                    if response:
                        print(f"收到响应: {len(response)}字节")
                    else:
                        print("没有响应")
                except socket.timeout:
                    print("没有收到响应")
            except Exception as e:
                print(f"发送测试帧失败: {e}")
        
        sock.close()
        print("连接已关闭")
        return True
        
    except ConnectionRefusedError:
        print("❌ 连接被拒绝 - PLC可能没开机或端口错误")
        return False
    except socket.timeout:
        print("❌ 连接超时 - 网络问题")
        return False
    except Exception as e:
        print(f"❌ 连接错误: {e}")
        return False

def test_multiple_strategies():
    """测试多种连接策略"""
    host = '192.168.100.123'
    port = 8001
    
    print("=== PLC协议连接策略测试 ===")
    
    strategies = [
        # 连接策略列表
        {"name": "默认参数", "connect_timeout": 5, "recv_timeout": 2, "send_init": False},
        {"name": "长接收超时", "connect_timeout": 5, "recv_timeout": 10, "send_init": False},
        {"name": "发送初始化帧", "connect_timeout": 5, "recv_timeout": 5, "send_init": True},
        {"name": "短连接超时", "connect_timeout": 2, "recv_timeout": 5, "send_init": True},
    ]
    
    for strategy in strategies:
        success = test_connection_with_params(
            host, port,
            connect_timeout=strategy["connect_timeout"],
            recv_timeout=strategy["recv_timeout"],
            send_init=strategy["send_init"]
        )
        
        if success:
            print(f"✅ 策略 '{strategy['name']}' 成功!")
            # 如果成功，继续测试数据流
            test_data_stream(host, port, strategy)
            break
        else:
            print(f"❌ 策略 '{strategy['name']}' 失败")
            time.sleep(2)  # 等待2秒再试下一个

def test_data_stream(host, port, strategy):
    """测试数据流连续性"""
    print(f"\n{'='*60}")
    print("测试数据流连续性...")
    print('='*60)
    
    try:
        sock = socket.socket()
        sock.settimeout(strategy["connect_timeout"])
        sock.connect((host, port))
        sock.settimeout(strategy["recv_timeout"])
        
        if strategy["send_init"]:
            init_frame = b'\x55\xAA\x55\xAA\x00\x1C\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            sock.send(init_frame)
        
        # 尝试接收多个数据包
        packets = []
        start_time = time.time()
        
        for i in range(5):  # 尝试接收5个包
            try:
                data = sock.recv(1024)
                if data:
                    packets.append(data)
                    print(f"包{i+1}: {len(data)}字节, 时间: {time.time() - start_time:.3f}s")
                    if len(data) == 46:
                        print(f"   ✅ 46字节协议帧")
                    start_time = time.time()
                else:
                    print(f"包{i+1}: 连接关闭")
                    break
            except socket.timeout:
                print(f"包{i+1}: 接收超时")
                break
        
        sock.close()
        
        if packets:
            print(f"\n✅ 成功收到 {len(packets)} 个数据包")
            # 分析包间隔
            if len(packets) > 1:
                print("数据流正常，PLC在持续发送数据")
        else:
            print("\n❌ 没有收到任何数据包")
            
    except Exception as e:
        print(f"数据流测试失败: {e}")

if __name__ == "__main__":
    print("开始PLC协议调试...")
    test_multiple_strategies()