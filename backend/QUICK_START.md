# 司机台信号屏调试 - 快速开始

## 核心工具

我已经为你创建了以下调试工具：

### 1. `test_signal_display.py`（推荐）
极简版本，专注于基础功能。

```bash
# 启动服务器（监听所有网卡）
python test_signal_display.py server 0.0.0.0 9999

# 启动模拟客户端
python test_signal_display.py client 127.0.0.1 9999

# 解析十六进制数据
python test_signal_display.py hex "55AA55AA0042003200018E93F46C800000000000000003070C0A000000030D01010100002041C000003DCD4000A041000001010000000100000003E90000449C8000"
```

### 2. `debug_signal_display_fixed.py`
完整功能版本，支持更多参数。

```bash
# 查看帮助
python debug_signal_display_fixed.py --help

# 启动服务器
python debug_signal_display_fixed.py server --host 0.0.0.0 --port 9999

# 启动客户端（10Hz频率）
python debug_signal_display_fixed.py client --host 127.0.0.1 --port 9999 --interval 0.1
```

## 实际连接步骤

### 当你在实验室时：

1. **确保网络连接**：
   - 信号屏IP: 192.168.100.121
   - 服务器IP: 192.168.100.121（同一台机器）或你的电脑IP

2. **启动服务器**：
   ```bash
   python test_signal_display.py server 192.168.100.121 9999
   ```

3. **信号屏应该会自动连接**（作为TCP客户端）

4. **查看接收的数据**：
   - 控制台会显示接收的字节数
   - 原始数据保存在 `logs/signal_*.bin` 文件中
   - 检查帧头是否为 `0x55AA55AA`

### 当你在家测试时：

1. **本地测试**：
   ```bash
   # 终端1: 启动服务器
   python test_signal_display.py server 127.0.0.1 9999
   
   # 终端2: 启动模拟客户端
   python test_signal_display.py client 127.0.0.1 9999
   ```

2. **验证数据流**：
   - 服务器会显示接收的数据
   - 客户端会每秒发送10帧测试数据

## 现有代码状态

系统已经有了完整的 `SignalDisplayServer` 类（在 `app/communication/signal_display_server.py`），功能包括：

- ✅ TCP Server监听信号屏连接
- ✅ 66字节帧解析
- ✅ 多客户端支持
- ✅ 数据持久化
- ✅ ZMQ消息总线集成

**问题**：格式字符串可能有问题（68字节 vs 66字节），但基本功能完整。

## 关键文件

1. **`app/communication/signal_display_server.py`** - 主服务器类
2. **`test_signal_display.py`** - 极简调试工具（推荐）
3. **`debug_signal_display_fixed.py`** - 完整调试工具
4. **`信号屏调试说明.md`** - 详细文档
5. **`QUICK_START.md`** - 本快速指南

## 测试数据

示例十六进制帧（66字节）：
```
55AA55AA0042003200018E93F46C800000000000000003070C0A000000030D01010100002041C000003DCD4000A041000001010000000100000003E90000449C8000
```

字段解释：
- 帧头: `0x55AA55AA` ✓
- 速度: 10.0 km/h
- 模式: ATO
- 当前站: 丰台科技园
- 车号: 1001

## 故障排除

1. **连接失败**：
   ```bash
   # 检查端口是否被占用
   netstat -an | findstr :9999
   
   # 测试本地连接
   python test_signal_display.py client 127.0.0.1 9999
   ```

2. **数据解析错误**：
   - 检查帧长度是否为66字节
   - 检查帧头是否为 `0x55AA55AA`
   - 使用十六进制解析工具验证

3. **查看日志**：
   - 原始数据: `logs/signal_*.bin`
   - 解析日志: `logs/signal_server_*.log`

## 下一步

当你回到实验室时，只需要：

1. 启动服务器：`python test_signal_display.py server 192.168.100.121 9999`
2. 连接信号屏设备
3. 观察数据接收情况
4. 根据实际数据调整解析逻辑

所有工具都已准备就绪，可以直接使用！