# 信号屏（MMI）测试数据示例

这些是66字节帧的十六进制示例，用于测试解析功能。

## 示例1：正常运行的列车数据
```
55AA55AA0042003200018E93F46C800000000000000003070C0A000000030D01010100002041C000003DCD4000A041000001010000000100000003E90000449C8000
```

字段解释：
- Magic: 0x55AA55AA ✓
- 速度: 10.0 km/h
- 加速度: 0.0 m/s²
- 模式: ATO (模式值: 1)
- 当前站: 丰台科技园 (站ID: 3)
- 车号: 1001

## 示例2：高速运行的列车数据
```
55AA55AA0042003200018E93F46C800000000000000003070C0A000000040501010100003442000000000000005041000001010000000100000003E90000449C8000
```

字段解释：
- Magic: 0x55AA55AA ✓
- 速度: 45.0 km/h
- 加速度: 0.0 m/s²
- 限速: 80.0 km/h
- 模式: ATO (模式值: 1)
- 当前站: 科怡路 (站ID: 4)
- 车号: 1001

## 示例3：RM模式下的列车数据
```
55AA55AA0042003200018E93F46C800000000000000003070C0A000000020301010100001040000000000000000041000004010000000100000003E90000449C8000
```

字段解释：
- Magic: 0x55AA55AA ✓
- 速度: 2.0 km/h
- 加速度: 0.0 m/s²
- 模式: RM (模式值: 4)
- 当前站: 车公庄 (站ID: 2)
- 车号: 1001

## 使用方式

### 1. 启动服务器
```bash
python debug_signal_display.py server --host 0.0.0.0 --port 9999
```

### 2. 解析十六进制数据
```bash
python debug_signal_display.py hexview "55AA55AA0042003200018E93F46C800000000000000003070C0A000000030D01010100002041C000003DCD4000A041000001010000000100000003E90000449C8000"
```

### 3. 启动模拟客户端
```bash
python debug_signal_display.py client --host 127.0.0.1 --port 9999 --interval 0.1 --count 100
```

### 4. 发送测试数据
```bash
python debug_signal_display.py sendtest --host 127.0.0.1 --port 9999 --speed 60.5 --mode 1 --station 5 --train 2001
```

## 协议说明

### 帧结构（66字节）
| 字节偏移 | 类型 | 字段 | 说明 |
|---------|------|------|------|
| 0-3 | DWORD | _uIdentify | 固定数据 0x55 AA 55 AA |
| 4-5 | WORD | _uTotalLen | 报文总大小 (66) |
| 6-7 | WORD | _uDataLen | 数据长度 |
| 8-15 | DDWORD | _timestamp | 毫秒级时间戳 |
| 16-17 | WORD | _uVerifyType | 校验类型 |
| 18-19 | WORD | _uVerifyCode | 校验码 |
| 20-21 | WORD | _uProtocolID | 协议ID |
| 22-23 | WORD | _uMsgID | 消息ID |
| 24-25 | WORD | _hYear | 年 |
| 26-27 | WORD | _hMonth | 月 |
| 28-29 | WORD | _hDay | 日 |
| 30-31 | WORD | _hHour | 时 |
| 32-33 | WORD | _hMinute | 分 |
| 34-35 | WORD | _hSec | 秒 |
| 36 | BYTE | _nCurrStationID | 当前站ID |
| 37 | BYTE | _nNextStationID | 下一站ID |
| 38 | BYTE | _nEndStationID | 终点站ID |
| 39 | BYTE | _nCMState | CM状态 |
| 40 | BYTE | _nMMState | MM状态 |
| 41 | BYTE | _nCTCState | CTC状态 |
| 42 | BYTE | _nRunDir | 运行方向 |
| 43 | BYTE | _nReserve | 预留 |
| 44-47 | FLOAT | _nSpeed | 速度 (km/h) |
| 48-51 | FLOAT | _fAcceleration | 加速度 (m/s²) |
| 52-53 | WORD | _nPullSwitch | 牵引切除 |
| 54-55 | WORD | _fSpeedLimit | 限速 (km/h) |
| 56 | BYTE | _nMode | 模式 |
| 57 | BYTE | _nPullState | 牵引状态 |
| 58 | BYTE | _nBrakeState | 制动状态 |
| 59 | BYTE | _nUrgencyStopState | 紧急制动 |
| 60 | BYTE | _nEventID | 事件ID |
| 61 | BYTE | _nSigState | 信号状态 |
| 62-63 | WORD | _nTrainNo | 车号 |
| 64-67 | FLOAT | _fNextStationDist | 距下一站距离 (m) |

### 站点映射
1. 车公庄
2. 丰台科技园  
3. 科怡路
4. 丰台南路
5. 丰台东大街
6. 七里庄
7. 六里桥
8. 六里桥东
9. 北京西
10. 军事博物馆
11. 白堆子
12. 白石桥南
13. 国家图书馆

### 模式映射
- 0: DTO
- 1: ATO
- 2: AR
- 3: SM
- 4: RM
- -1: RM (默认)

## 网络抓包格式

如果你有Wireshark抓包数据，格式通常是：
```
时间戳 | 源地址 | 十六进制数据
```

例如：
```
1698220800.123456|192.168.100.121:9999|55AA55AA0042003200018E93F46C800000000000000003070C0A000000030D01010100002041C000003DCD4000A041000001010000000100000003E90000449C8000
```

使用前需要提取出纯十六进制部分。