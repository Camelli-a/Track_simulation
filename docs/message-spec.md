# 轨道交通仿真系统 - 消息格式规范

本文档定义当前 ZMQ `MessageBus` 中使用的消息包装格式和主要 topic 的 `data` 字段。字段命名统一使用小写下划线。

## 一、统一消息包装格式

所有通过 ZMQ 总线传递的消息都使用以下包装格式：

```json
{
  "topic": "train_state",
  "timestamp": 1720000000.123,
  "data": {}
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `topic` | string | 是 | 消息类型，用于 ZMQ 过滤和路由 |
| `timestamp` | float | 是 | 消息发送时刻，Unix 时间戳，单位 s |
| `data` | object | 是 | 业务数据，由各模块定义 |

注意：

- `MessageBus.publish(topic, data)` 会自动生成外层 `topic` 和 `timestamp`。
- 各模块只需要传业务 `data`。
- `data` 内不要再放 `type` 或 `timestamp`，避免双层包装。

正确示例：

```json
{
  "topic": "ma_state",
  "timestamp": 1720000000.123,
  "data": {
    "ma_limits": []
  }
}
```

错误示例：

```json
{
  "topic": "ma_state",
  "timestamp": 1720000000.123,
  "data": {
    "type": "ma_state",
    "timestamp": 1720000000.123,
    "ma_limits": []
  }
}
```

## 二、topic 清单

| topic | 发送方 | 说明 |
|-------|--------|------|
| `train_state` | 车辆算法模块 / Mock | 单车运行状态 |
| `signal_state` | 信号模块 / Mock | 信号、区段、道岔、进路冲突状态 |
| `ma_state` | 信号模块 / Mock | 移动授权和速度约束 |
| `power_state` | 供电模块 / Mock | 供电系统状态 |
| `comm_state` | 通信模块 | 通信连接状态 |
| `alarm_event` | 任意模块 | 告警事件 |

## 三、train_state

发送方：车辆算法模块 / Mock。

说明：表示某一辆车当前的运行状态。信号模块的 `signal_worker` 会订阅该 topic，并缓存所有车辆状态用于计算 MA 和信号约束。

完整消息示例：

```json
{
  "topic": "train_state",
  "timestamp": 1720000000.123,
  "data": {
    "vehicle_id": "TRAIN-001",
    "position": 300.0,
    "speed": 40.0,
    "route_id": "R_MAIN",
    "train_length": 120.0
  }
}
```

`data` 字段：

| 字段 | 类型 | 必填 | 单位 | 说明 |
|------|------|------|------|------|
| `vehicle_id` | string | 是 | - | 列车编号 |
| `position` | float | 是 | m | 线路一维坐标 |
| `speed` | float | 是 | km/h | 当前速度 |
| `route_id` | string | 否 | - | 当前进路，缺失时信号模块默认 `R_MAIN` |
| `train_length` | float | 否 | m | 列车长度，缺失时信号模块默认 `DEFAULT_TRAIN_LENGTH` |

其他车辆字段如 `line_id`、`acceleration`、`mode`、`is_running`、`emergency_brake` 可以由车辆模块继续携带；当前信号模块只依赖上表字段。

## 四、signal_state

发送方：信号模块 / Mock。

说明：表示当前信号机、区段、道岔和进路申请结果。

完整消息示例：

```json
{
  "topic": "signal_state",
  "timestamp": 1720000000.123,
  "data": {
    "system_mode": "normal",
    "signals": [
      {
        "signal_id": "SIG-01",
        "position": 300.0,
        "state": "yellow",
        "signal_state": "yellow",
        "route_id": "R_MAIN",
        "permission": "restricted"
      }
    ],
    "sections": [
      {
        "section_id": "JZ1",
        "start": 0.0,
        "end": 758.0,
        "occupied": true,
        "vehicle_id": "TRAIN-001",
        "locked": false,
        "locked_by_route_id": null,
        "condition": "normal"
      }
    ],
    "switches": [
      {
        "switch_id": "SW-01",
        "position": "normal",
        "locked": true,
        "locked_by_route_id": "R_MAIN",
        "related_section": "JZ4",
        "reason": "route_locked"
      }
    ],
    "route_results": [
      {
        "vehicle_id": "TRAIN-003",
        "route_id": "R_BRANCH",
        "allowed": false,
        "reason": "switch_locked_conflict",
        "required_switch_id": "SW-01",
        "required_position": "reverse",
        "current_position": "normal",
        "locked_by_route_id": "R_MAIN"
      }
    ]
  }
}
```

顶层 `data` 字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `system_mode` | string | 系统模式，当前为 `normal` |
| `signals` | array | 信号显示状态 |
| `sections` | array | 区段占用状态 |
| `switches` | array | 道岔位置与锁闭状态 |
| `route_results` | array | 临时进路申请结果 |

常用子字段：

| 字段 | 说明 |
|------|------|
| `signals[].signal_id` | 信号机编号 |
| `signals[].position` | 信号机近似位置，单位 m |
| `signals[].state` | 旧前端兼容字段，值同 `signal_state` |
| `signals[].signal_state` | `red` / `yellow` / `green` |
| `signals[].permission` | `stop` / `restricted` / `allow` |
| `sections[].section_id` | 区段编号 |
| `sections[].occupied` | 是否被占用 |
| `sections[].vehicle_id` | 占用车辆编号，没有时为 `null` |
| `sections[].locked` | 区段是否锁闭 |
| `sections[].locked_by_route_id` | 锁闭该区段的进路 |
| `switches[].switch_id` | 道岔编号 |
| `switches[].position` | `normal` / `reverse` |
| `switches[].locked` | 是否锁闭 |
| `switches[].locked_by_route_id` | 锁闭该道岔的进路 |
| `route_results[].allowed` | 进路申请是否允许 |
| `route_results[].reason` | 申请结果原因，例如 `switch_locked_conflict` |

## 五、ma_state

发送方：信号模块 / Mock。

说明：表示每辆车的移动授权边界、信号约束和简化 ATP 制动曲线计算结果。

完整消息示例：

```json
{
  "topic": "ma_state",
  "timestamp": 1720000000.123,
  "data": {
    "ma_limits": [
      {
        "vehicle_id": "TRAIN-001",
        "position": 300.0,
        "route_id": "R_MAIN",
        "ma_limit": 455.0,
        "distance_to_ma": 155.0,
        "permission": "restricted",
        "signal_state": "yellow",
        "speed_limit": 51.8,
        "target_speed": 51.8,
        "reason": "front_vehicle_protection",
        "front_vehicle_id": "TRAIN-002",
        "front_train_length": 120.0,
        "location_uncertainty": 5.0,
        "communication_margin": 10.0,
        "safety_margin": 30.0,
        "front_protection_point": 455.0,
        "current_speed": 40.0,
        "route_speed_limit": 80.0,
        "static_speed_limit": 60.0,
        "static_speed_limit_id": "SL-001",
        "fault_speed_limit": null,
        "required_stop_distance": 108.4,
        "emergency_stop_distance": 98.1,
        "warning_distance": 158.4,
        "braking_curve_speed_limit": 51.8,
        "speed_limit_reason": "braking_curve",
        "braking_model": "simplified_atp_braking_curve"
      }
    ]
  }
}
```

`data` 字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `ma_limits` | array | 所有车辆的 MA 列表 |

`ma_limits[]` 字段：

| 字段 | 类型 | 单位 | 说明 |
|------|------|------|------|
| `vehicle_id` | string | - | 列车编号 |
| `position` | float | m | 当前列车位置 |
| `route_id` | string | - | 当前进路 |
| `ma_limit` | float | m | 移动授权终点 |
| `distance_to_ma` | float | m | 当前车到 MA 的距离 |
| `permission` | string | - | `allow` / `restricted` / `stop` |
| `signal_state` | string | - | `green` / `yellow` / `red` |
| `speed_limit` | float | km/h | 当前约束限速 |
| `target_speed` | float | km/h | 建议目标速度 |
| `reason` | string | - | `front_vehicle_protection` / `route_end` 等 |
| `front_vehicle_id` | string\|null | - | 前车编号，没有前车时为 `null` |
| `front_protection_point` | float\|null | m | 前车安全包络边界点 |
| `front_train_length` | float\|null | m | 前车长度 |
| `location_uncertainty` | float | m | 定位误差裕量 |
| `communication_margin` | float | m | 通信 / 计算延迟折算裕量 |
| `safety_margin` | float | m | 固定安全裕量 |
| `current_speed` | float | km/h | 当前速度 |
| `route_speed_limit` | float | km/h | 进路限速 |
| `required_stop_distance` | float | m | 常用制动停车距离 |
| `emergency_stop_distance` | float | m | 紧急制动停车距离 |
| `warning_distance` | float | m | restricted/yellow 预警距离 |
| `braking_curve_speed_limit` | float | km/h | 制动曲线反推限速 |
| `braking_model` | string | - | 当前为 `simplified_atp_braking_curve` |

## 六、MA 与制动曲线说明

信号模块当前使用简化前车安全包络计算 MA：

```text
front_protection_point =
  front_vehicle.position
  - front_train_length
  - location_uncertainty
  - communication_margin
  - safety_margin

ma_limit = min(front_protection_point, route_end)
```

没有前车时：

```text
ma_limit = route_end
```

信号状态和限速不再使用固定 `80m / 200m` 阈值作为主逻辑，而是使用简化 ATP 制动距离：

```text
speed_mps = speed_kmh / 3.6

required_stop_distance =
  speed_mps * REACTION_TIME
  + speed_mps ** 2 / (2 * SERVICE_BRAKE_DECELERATION)
  + BRAKING_SAFETY_MARGIN

emergency_stop_distance =
  speed_mps * REACTION_TIME
  + speed_mps ** 2 / (2 * EMERGENCY_BRAKE_DECELERATION)
  + BRAKING_SAFETY_MARGIN

warning_distance =
  required_stop_distance + WARNING_MARGIN
```

判断规则：

- `distance_to_ma <= emergency_stop_distance`：`stop / red / speed_limit=0`
- `distance_to_ma <= warning_distance`：`restricted / yellow / speed_limit=制动曲线反推限速`
- 其他：`allow / green / speed_limit=route_speed_limit`

## 七、其他 topic 简表

### power_state

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

### comm_state

```json
{
  "topic": "comm_state",
  "timestamp": 1720000000.123,
  "data": {
    "source": "zmq",
    "driver_console_connected": true,
    "zmq_connected": true,
    "last_message_at": 1720000000.001
  }
}
```

### alarm_event

```json
{
  "topic": "alarm_event",
  "timestamp": 1720000000.123,
  "data": {
    "alarm_id": "ALM-001",
    "level": "warning",
    "source": "SIGNAL",
    "vehicle_id": "TRAIN-001",
    "message": "Train is close to MA limit"
  }
}
```

## 八、MessageBus 使用示例

发布：

```python
from app.communication.message_bus import MessageBus

bus = MessageBus()
bus.start()

bus.publish("train_state", {
    "vehicle_id": "TRAIN-001",
    "position": 300.0,
    "speed": 40.0,
})

bus.stop()
```

订阅：

```python
from app.communication.message_bus import MessageBus

def on_train_state(topic: str, data: dict):
    print(topic, data)

bus = MessageBus()
bus.start()
bus.subscribe("train_state", on_train_state)
```

## 静态限速与安全速度上限补充

`ma_state.data.ma_limits[]` 现在会同时输出并合成以下限速来源：

| 字段 | 类型 | 单位 | 说明 |
|------|------|------|------|
| `route_speed_limit` | float | km/h | 进路限速 |
| `static_speed_limit` | float\|null | km/h | 静态线路限速 |
| `static_speed_limit_id` | string\|null | - | 命中的静态限速区间 ID |
| `fault_speed_limit` | float\|null | km/h | 车辆/系统故障限速 |
| `braking_curve_speed_limit` | float\|null | km/h | ATP 制动曲线反推限速 |
| `speed_limit` | float | km/h | 最终安全速度上限 |
| `speed_limit_reason` | string | - | 主导限速原因 |

`speed_limit_reason` 可取：

- `route_limit`
- `static_limit`
- `fault_limit`
- `braking_curve`
- `stop`
- `emergency_brake`
- `no_valid_limit`

ATO/车辆控制模块应把 `ma_state.speed_limit` 作为安全速度上限，在该上限内做牵引、惰行、制动控制；不应绕过信号模块重新判断联锁安全。

## ATO command

信号/ATO 模块会周期发布智能驾驶建议：

```json
{
  "topic": "ato_command",
  "timestamp": 1720000000.123,
  "data": {
    "commands": [
      {
        "vehicle_id": "TRAIN-001",
        "control_mode": "ATO",
        "ato_state": "braking_to_stop",
        "target_speed": 18.5,
        "safe_speed_limit": 40.0,
        "stop_curve_speed_limit": 18.5,
        "current_speed": 35.0,
        "target_position": 1200.0,
        "distance_to_target": 150.0,
        "station_id": "ST-01",
        "stop_window": {
          "lower": 1199.5,
          "upper": 1200.5
        },
        "traction_level": 0,
        "brake_level": 2,
        "holding_brake": false,
        "selected_strategy": "pid_basic",
        "score": null,
        "reason": "stop_curve_braking",
        "speed_limit_reason": "static_limit"
      }
    ]
  }
}
```

`MessageBus` 会自动包装 `topic` / `timestamp` / `data`，业务 `data` 内不要再放 `type` 或 `timestamp`。

ATO 第一版只输出目标速度、停车曲线和牵引/制动级位建议，不直接更新车辆速度、位置、加速度。车辆模块订阅 `ato_command` 后自行执行动力学。`target_speed` 必须始终小于等于 `safe_speed_limit`，其中 `safe_speed_limit` 来自 `ma_state.speed_limit`。

回调函数会在后台线程中执行，模块内部如维护共享状态，需要做好线程安全处理。
