# 轨道交通仿真系统 - 消息格式规范

## 一、统一消息包装格式

所有通过 ZMQ 总线传递的消息，必须遵循以下包装格式：

```json
{
  "topic":     "train_state",         // 必填，消息类型（字符串）
  "timestamp": 1720000000.123,        // 必填，发送时刻（Unix 时间戳，秒，浮点数）
  "data":      { ... }                // 必填，业务数据（对象）
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `topic` | string | 是 | 消息类型，用于 ZMQ 过滤和路由 |
| `timestamp` | float | 是 | 消息发送时刻，Unix 时间戳（秒，含小数） |
| `data` | object | 是 | 业务数据，各模块自定义字段 |

### 注意事项

- **topic 命名规范**：小写字母 + 下划线，如 `train_state`、`alarm_event`
- **timestamp 精度**：建议保留 3 位小数（毫秒级）
- **data 字段**：由各模块负责定义，本规范只约束包装层

---

## 二、消息类型清单

| topic | 发送方 | 说明 |
|-------|--------|------|
| `train_state` | 车辆算法模块 | 单车运动状态 |
| `signal_state` | 信号算法模块 | 信号灯 / 区段 / 道岔状态 |
| `ma_state` | 信号算法模块 | 移动授权边界 |
| `power_state` | 供电模块 / Mock | 供电系统状态 |
| `comm_state` | 通信模块 | 通信连接状态 |
| `alarm_event` | 任意模块 | 告警事件 |

---

## 三、各消息的 data 字段定义

### 3.1 车辆状态 `train_state`

**发送方**：车辆算法同学 A

**说明**：表示某一辆车当前的运动状态

**完整消息示例**：

```json
{
  "topic": "train_state",
  "timestamp": 1720000000.123,
  "data": {
    "vehicle_id": "TRAIN-001",
    "line_id": "LINE-1",
    "position": 1234.5,
    "speed": 62.4,
    "acceleration": 0.32,
    "mode": "manual",
    "is_running": true,
    "emergency_brake": false
  }
}
```

**data 字段说明**：

| 字段 | 类型 | 必填 | 单位 | 说明 |
|------|------|------|------|------|
| `vehicle_id` | string | 是 | - | 车辆编号，如 `TRAIN-001` |
| `line_id` | string | 是 | - | 线路编号 |
| `position` | float | 是 | m | 当前位置 |
| `speed` | float | 是 | km/h | 速度 |
| `acceleration` | float | 是 | m/s² | 加速度 |
| `mode` | string | 是 | - | 驾驶模式：`manual` / `ato` / `atp` / `emergency` |
| `is_running` | bool | 是 | - | 车辆是否运行中 |
| `emergency_brake` | bool | 是 | - | 是否触发紧急制动 |

**待确认事项**：
- 车辆算法能否提供 position / speed / acceleration？
- mode 是否由车辆算法提供？
- emergency_brake 是否由 ATP 提供？
- 车辆编号是否统一用 `TRAIN-001` 格式？

---

### 3.2 信号状态 `signal_state`

**发送方**：信号算法同学 B

**说明**：表示信号灯、区段、道岔等状态

**完整消息示例**：

```json
{
  "topic": "signal_state",
  "timestamp": 1720000000.123,
  "data": {
    "system_mode": "normal",
    "signals": [
      {
        "signal_id": "SIG-01",
        "position": 500.0,
        "state": "green"
      }
    ],
    "sections": [
      {
        "section_id": "SEG-01",
        "start": 0.0,
        "end": 500.0,
        "occupied": true,
        "vehicle_id": "TRAIN-001",
        "condition": "normal"
      }
    ],
    "switches": [
      {
        "switch_id": "SW-01",
        "position": "normal",
        "locked": true,
        "related_section": "SEG-03"
      }
    ]
  }
}
```

**data 字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `system_mode` | string | 系统运行模式：`normal` / `degraded` / `emergency` |
| `signals` | array | 信号灯列表 |
| `signals[].signal_id` | string | 信号灯编号 |
| `signals[].position` | float | 里程位置（m） |
| `signals[].state` | string | 信号灯状态：`red` / `yellow` / `green` |
| `sections` | array | 闭塞区段 / 轨道区段列表 |
| `sections[].section_id` | string | 区段编号 |
| `sections[].start` | float | 起始里程（m） |
| `sections[].end` | float | 终止里程（m） |
| `sections[].occupied` | bool | 区段是否被占用 |
| `sections[].vehicle_id` | string\|null | 占用车辆编号 |
| `sections[].condition` | string | 区段状态：`normal` / `warning` / `fault` |
| `switches` | array | 道岔列表 |
| `switches[].switch_id` | string | 道岔编号 |
| `switches[].position` | string | 道岔位置：`normal` / `reverse` |
| `switches[].locked` | bool | 道岔是否锁闭 |
| `switches[].related_section` | string | 关联区段 |

**待确认事项**：
- 区段编号是否用 `SEG-01` 格式？
- 道岔是否有 `locked` 状态？
- 信号灯状态是否只需要 `red` / `yellow` / `green`？
- 区段占用由信号模块判断，还是后端根据车辆 position 推算？

---

### 3.3 移动授权 `ma_state`

**发送方**：信号算法同学 B

**说明**：表示每辆车最多能开到哪里（移动授权边界）

**完整消息示例**：

```json
{
  "topic": "ma_state",
  "timestamp": 1720000000.123,
  "data": {
    "ma_limits": [
      {
        "vehicle_id": "TRAIN-001",
        "ma_limit": 1600.0,
        "target_speed": 60.0,
        "reason": "front_train"
      }
    ]
  }
}
```

**data 字段说明**：

| 字段 | 类型 | 单位 | 说明 |
|------|------|------|------|
| `ma_limits` | array | - | 所有车辆的 MA 列表 |
| `ma_limits[].vehicle_id` | string | - | 对应车辆 |
| `ma_limits[].ma_limit` | float | m | 移动授权边界 |
| `ma_limits[].target_speed` | float | km/h | 建议目标速度（可选） |
| `ma_limits[].reason` | string | - | MA 来源原因：`front_train` / `switch_locked` / `station_stop` |

**用途**：前端会用 `ma_limit` 在大屏上画安全边界

---

### 3.4 供电状态 `power_state`

**发送方**：供电模块 / Mock 模块（暂时）

**说明**：供电系统电压、电流、功率等状态

**完整消息示例**：

```json
{
  "topic": "power_state",
  "timestamp": 1720000000.123,
  "data": {
    "substation_id": "SS-01",
    "voltage": 1500.0,
    "current": 300.0,
    "power": 450.0,
    "is_fault": false
  }
}
```

**data 字段说明**：

| 字段 | 类型 | 单位 | 说明 |
|------|------|------|------|
| `substation_id` | string | - | 变电站编号 |
| `voltage` | float | V | 网压 |
| `current` | float | A | 电流 |
| `power` | float | kW | 功率 |
| `is_fault` | bool | - | 是否供电故障 |

---

### 3.5 通信状态 `comm_state`

**发送方**：通信同学（你）

**说明**：表示司机台、UDP、ZMQ 连接是否正常

**完整消息示例**：

```json
{
  "topic": "comm_state",
  "timestamp": 1720000000.123,
  "data": {
    "source": "udp",
    "driver_console_connected": true,
    "zmq_connected": true,
    "last_message_at": 1720000000.001
  }
}
```

**data 字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | string | 数据来源：`mock` / `udp` / `zmq` |
| `driver_console_connected` | bool | 司机台是否连接 |
| `zmq_connected` | bool | ZMQ 总线是否正常 |
| `last_message_at` | float | 最后一次收到消息的时刻（Unix 时间戳） |

**待确认事项**：
- UDP 原始司机台数据是否由通信模块解析？
- 解析后是否统一转成 JSON 发给 ZMQ？
- 真实设备不可用时，是否由通信模块提供 Mock 输入？

---

### 3.6 告警事件 `alarm_event`

**发送方**：车辆、信号、供电、通信任意模块

**说明**：告警事件，后端负责缓存最近 100 条

**完整消息示例**：

```json
{
  "topic": "alarm_event",
  "timestamp": 1720000000.123,
  "data": {
    "alarm_id": "ALM-001",
    "level": "warning",
    "source": "ATP",
    "vehicle_id": "TRAIN-001",
    "message": "Train is close to MA limit"
  }
}
```

**data 字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `alarm_id` | string | 告警编号 |
| `level` | string | 告警级别：`info` / `warning` / `critical` |
| `source` | string | 告警来源：`ATP` / `ATO` / `SIGNAL` / `POWER` / `COMM` / `BACKEND` |
| `vehicle_id` | string\|null | 相关车辆编号（可为空） |
| `message` | string | 告警内容 |

---

## 四、使用 MessageBus 客户端

通信模块提供了 `MessageBus` 类，封装了 ZMQ 的发布/订阅细节。

### 4.1 发布消息

```python
from app.communication.message_bus import MessageBus

bus = MessageBus()
bus.start()

# 发布车辆状态
bus.publish("train_state", {
    "vehicle_id": "TRAIN-001",
    "speed": 80.0,
    "position": 1234.5,
    # ... 其他字段
})

bus.stop()
```

### 4.2 订阅消息

```python
from app.communication.message_bus import MessageBus

def on_train_state(topic: str, data: dict):
    print(f"收到 {topic}: {data['vehicle_id']} 速度 {data['speed']} km/h")

bus = MessageBus()
bus.start()

# 订阅车辆状态
bus.subscribe("train_state", on_train_state)

# 保持运行...
bus.stop()
```

### 4.3 注意事项

- 调用 `bus.start()` 后才能发布/订阅
- 回调函数会在**后台线程**中执行，注意线程安全
- `publish()` 会自动添加 `timestamp` 字段
- topic 必须完全匹配（ZMQ 按前缀过滤，但建议精确订阅）

---

## 五、启动流程

### 5.1 启动 ZMQ Broker

```bash
cd backend
python -m app.communication.broker
```

### 5.2 启动 Mock 数据发布器（可选）

```bash
python -m app.communication.mock_publisher
```

### 5.3 在你的模块中使用

```python
from app.communication.message_bus import MessageBus

bus = MessageBus()
bus.start()

# 发布你的消息
bus.publish("your_topic", {...})

# 订阅你需要的消息
bus.subscribe("train_state", your_callback)
```

---

## 六、FAQ

**Q：我能自定义 topic 吗？**  
A：可以，但请提前与团队沟通，并更新本文档的「消息类型清单」。

**Q：data 字段里能嵌套对象吗？**  
A：可以，JSON 支持任意深度嵌套。

**Q：消息会丢失吗？**  
A：ZMQ PUB/SUB 是**无状态**的，如果订阅者启动晚于发布者，早期的消息会丢失。如果需要可靠传输，请联系通信模块同学。

**Q：如何调试消息？**  
A：运行 Broker 和 Mock 发布器，然后写一个简单的订阅脚本，订阅所有消息（topic 设为空字符串）即可看到所有流量。

---

## 七、版本记录

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| v1.0 | 2026-07-07 | 初版，定义统一包装格式和 6 类消息 |
