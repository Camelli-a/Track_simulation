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
    "train_length": 118.0
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
        "front_train_length": 118.0,
        "location_uncertainty": 5.0,
        "communication_margin": 10.0,
        "safety_margin": 30.0,
        "front_protection_point": 455.0,
        "current_speed": 40.0,
        "route_speed_limit": 80.0,
        "required_stop_distance": 108.4,
        "emergency_stop_distance": 98.1,
        "warning_distance": 158.4,
        "braking_curve_speed_limit": 51.8,
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

`STATIC_SPEED_LIMITS` 当前来自老师 Excel 的静态限速表，原始限速值按 `cm/s * 0.036` 统一转换为 `km/h`，`start` / `end` 为当前一维累计坐标，单位 `m`。本阶段只接入静态线路限速，道岔侧向限速后续单独接入。

| 字段 | 类型 | 单位 | 说明 |
|------|------|------|------|
| `route_speed_limit` | float | km/h | 进路限速 |
| `static_speed_limit` | float\|null | km/h | 静态线路限速 |
| `static_speed_limit_id` | string\|null | - | 命中的静态限速区间 ID |
| `static_speed_limit_source` | string\|null | - | 静态限速来源，当前为老师静态限速表 |
| `static_speed_limit_related_switch_id` | string\|null | - | 老师表中的关联道岔编号，缺失时为 null |
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

## Driver input

`driver_input` 是 SM 模式司机请求。动力学以 `traction_percent` / `brake_percent` 为唯一控制量；`traction_level`（0～4）和 `brake_level`（0～7）仅作显示、日志及兼容输入。制动与牵引同时非零时制动优先。

```json
{
  "type": "driver_input",
  "timestamp": 1720000000.123,
  "vehicle_id": "TRAIN-001",
  "direction": "forward",
  "direction_code": 1,
  "main_handle_raw": 2,
  "traction_percent": 0.0,
  "brake_percent": 50.0,
  "traction_level": 0,
  "brake_level": 4,
  "key_switch": true,
  "emergency_button": false,
  "ato_start_btn": false,
  "ato_capable": true,
  "ato_active": false,
  "parking_apply": false,
  "parking_release": false,
  "forced_release": false,
  "vigilance": false,
  "vigilance_allow": false,
  "brake_bad_light": false,
  "network_fault_light": false,
  "high_voltage_light": true,
  "open_left_door": false,
  "open_right_door": false,
  "close_left_door": false,
  "close_right_door": false,
  "door_mode": "auto",
  "door_closed_light": true
}
```

`main_handle_raw=4` 是最大常用制动，映射为 `brake_level=7`、`brake_percent=100`，不触发紧急制动。`ato_start_btn` 是请求，PLC 的 `ato_active` 是显示回读；车辆 ATO 状态机拥有实际激活状态。诊断灯不得代替控制命令或 `comm_state`。

车门按钮字段是瞬时操作请求。`Train` 独立维护物理 `door_state`，输入的 `door_closed_light` 只保存为司机台硬件回读，不能覆盖物理车门状态。列车停车且位置进入停车点 ±0.5m 窗口后自动开门，默认保持 5 秒后关闭；`door_mode=left/right/both` 可选择开门侧，缺少站台侧数据时 `auto` 暂按左侧处理。任一侧车门未关闭时车辆最终控制层禁止施加牵引。

`train_state` 增加：

- `door_state`: `closed/open`
- `left_door_open` / `right_door_open`
- `doors_all_closed`: 物理车门是否全部关闭
- `door_mode`
- `door_closed_light`: 由物理车门状态生成的仿真指示灯

四个指示灯字段在 `driver_input` 中均视为 PLC 硬件回读：`high_voltage_light`、`brake_bad_light`、`door_closed_light`、`network_fault_light`。车辆分别保存为 `hardware_*_light`，只用于检查回传灯态是否与系统命令一致。车辆 `train_state` 只输出自身拥有的灯命令，来源如下：

- `high_voltage_light`：由 `PowerState` 的电压及故障状态决定；
- `brake_bad_light`：由车辆制动故障业务状态决定；
- `door_closed_light`：由物理 `DoorState.all_closed` 决定；
- `network_fault` / `network_fault_light`：由通信模块根据连接和时效自行生成，不属于车辆 `train_state`。

禁止用 PLC 灯回读修改 `power_fault`、`brake_fault`、物理车门状态或 `comm_ok`。`Train.get_indicator_feedback_mismatches()` 仅输出命令值与回读值不一致的项目。

## Communication supervision and transient inputs

车辆必须订阅 `comm_state`，并同时检查 `driver_console_connected`、`zmq_connected` 和 `last_message_at`。当前 MVP 集中配置为：

- `DRIVER_WARNING_TIMEOUT_SEC = 0.3`：进入 `communication_delayed` 告警，但不紧急制动；
- `DRIVER_EMERGENCY_TIMEOUT_SEC = 0.5`：进入 `communication_lost` 并由 ATP 紧急制动。

PLC 的 100ms 输入帧可以由 20ms 动力学周期重复使用约 5 次，不要求每个动力学 tick 都收到新帧。阈值后续可根据联调结果调整。

以下字段按上升沿生成一次性事件：`ato_start_btn`、`forced_release`、`forced_pump`、`parking_apply`、`parking_release`、`horn`、左右门开关请求、`mode_up_confirm`、`mode_dn_confirm`、`confirm_flag`、`auto_rev_flag`、`trac_aux_reset`、`vigilance`。事件在一个 `step_tick()` 后消费；按钮必须先回到 false，下一次 true 才会再次触发。

`key_switch`、`direction`、`emergency_button`、`wash_mode_switch`、`ato_active`、`door_mode` 按持续电平处理，不做上升沿检测。可选 `frame_seq` 或 `message_id` 用于整帧去重；相同标识的重复帧只处理一次。

## Vehicle train_state output contract

车辆内部和 `train_state` 的规范字段保持 SI 单位，仪表速度额外提供 km/h：

- `position_m`、`speed_mps`、`speed_kmh`、`vehicle_speed_kmh`、`acceleration_mps2`
- `direction`、`control_mode`、`driving_mode`、`control_source`
- 最终实际施加的 `traction_level`、`brake_level`、`traction_percent`、`brake_percent`
- `actual_traction_force_n`、`actual_brake_force_n`
- `emergency_brake`、`atp_intervention`
- `ato_active`、`ato_capable`、`auto_reverse_cap`、`auto_reverse_active`、`recommended_speed_kmh`
- `door_state`、`door_open_light`、`door_closed_light`、`parking_brake`
- `high_voltage_on`、`brake_bad_light`

旧的 `position`、`speed`、`acceleration`、`mode` 字段暂时保留用于兼容既有模块，其中旧 `speed` 为 km/h。车辆状态不输出 `network_fault`；通信模块拥有该字段。厘米、厘米每秒、小端二进制等外部格式只能在对应通信适配器中转换，禁止写回 `Train` 内部状态。

## ZMQ wire format and PLC feedback ownership

当前项目 `MessageBus` 的实际线格式是单个 ZMQ 字符串帧：

```text
<topic> <json-envelope>
```

例如：

```text
driver_input {"topic":"driver_input","timestamp":1783821594.321,"data":{"vehicle_id":"TRAIN-001"}}
```

这不是 `send_json()` 的纯 JSON 单帧，也不是 `send_multipart()` 的双帧结构。由于 topic 位于同一帧开头，`SUBSCRIBE "driver_input"` 可以使用 ZMQ 原生前缀过滤。接收后必须校验帧前缀 topic 与 JSON envelope 的 `topic` 一致，再把 `data` 交给车辆；车辆边界仍兼容旧的扁平 `type` 消息。

车辆模块只发布 `train_state`，不得导入 `DriverDeskSource` 或调用 PLC 发送函数。通信层的 `PlcFeedbackAggregator` 是唯一 PLC 上行发送所有者：它订阅 `train_state`、`ato_state`、`door_state`、`comm_state`，缓存每个字段的最新值，每 100ms 生成一次完整快照并调用一次注入的 `send_to_plc(**snapshot)`。局部更新只覆盖对应缓存字段，不会用默认 false 清除其他模块刚更新的灯态。

当前仓库的 `DriverDeskSource.send()` 仍标记为“等待正式上行帧格式”，因此聚合和单一发送权已经实现，真实 28 字节打包必须在通信组确认字段偏移、类型和校验规则后由通信层补齐，车辆模块无需改动。

## Vehicle input routing and safety inputs

实体司机台来源（`driver_tcp` / `driver_desk` / `driver_plc` / `plc`）必须显式携带 `vehicle_id`，当前固定允许控制 `TRAIN-001`。缺少 `vehicle_id`、目标车辆不存在或实体司机台试图控制其他车辆时，车辆路由直接拒绝，不得使用 `train_index` 猜测，也不得广播。`TRAIN-002..N` 可以接收带自身 `vehicle_id` 的 `virtual_driver` 输入或车载 ATO 命令。

车辆订阅的完整输入集合：

- `driver_input`：司机候选控制，严格按车路由；
- `ma_state`：移动授权及安全速度；
- `speed_constraint`：外部临时限速，必须携带 `vehicle_id`，与 MA 限速取更严格值后进入 ATP；
- `signal_state` / `interlocking_state`：必须携带 `vehicle_id`，红灯或明确 stop/deny/blocked 权限进入 ATP 禁止运行；
- `track_info`：全局线路坡度、限速和停车点；
- `power_state`：共享供电业务状态；
- `comm_state`：司机台和 ZMQ 连接及时效；
- `fault_event`：默认必须携带 `vehicle_id`；只有显式 `scope=all/system` 才广播到全部列车。

控制顺序固定为：输入缓存 → Manual/ATO 候选命令 → ATP 安全监督 → 唯一 `step_tick()` 动力学更新。集成运行入口周期发布 `train_state`、`ato_state`、`atp_state`、`door_state`，ATP 告警单独发布 `alarm_event`。

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
        "target_id": "STOP-ST-001-PF-001-R-MAIN",
        "station_name": "GGZ",
        "platform_id": "PF-001",
        "platform_name": "GGZ-P01",
        "stop_target_source": "teacher_platform_table",
        "gradient": -3.5,
        "gradient_id": "GR-002",
        "gradient_unit": "permille",
        "effective_deceleration": 0.766,
        "stop_window": {
          "lower": 1199.5,
          "upper": 1200.5
        },
        "traction_level": 0,
        "brake_level": 2,
        "holding_brake": false,
        "selected_strategy": "pid_basic",
        "score": null,
        "strategy_scores": [],
        "reason": "stop_curve_braking",
        "speed_limit_reason": "static_limit"
      }
    ]
  }
}
```

`MessageBus` 会自动包装 `topic` / `timestamp` / `data`，业务 `data` 内不要再放 `type` 或 `timestamp`。

ATO 第一版只输出目标速度、停车曲线和牵引/制动级位建议，不直接更新车辆速度、位置、加速度。车辆模块订阅 `ato_command` 后自行执行动力学。`target_speed` 必须始终小于等于 `safe_speed_limit`，其中 `safe_speed_limit` 来自 `ma_state.speed_limit`。

`STOP_TARGETS` 由 `signal_track_config.py` 的线路静态配置提供。当前优先使用老师 Excel 车站表 / 站台表抽取出的站台中心公里标，并按 `route.start <= platform.position <= route.end` 关联到进路；后续无法匹配的进路可 fallback 到 `route.end` / `end_signal_id`。业务 `data` 内仍不包含 `type` / `timestamp`。

`GRADIENT_PROFILE` 来自老师 Excel 坡度表的离线抽取。坡度按千分坡 `permille` 处理，`0x55` 第一版视为上坡、`0xaa` 视为下坡。ATO 根据列车当前位置查询坡度并计算 `effective_deceleration`：上坡提高有效制动减速度，下坡降低有效制动减速度；该修正只影响 ATO 停车曲线和 `target_speed` 策略，本阶段不修改 MA/ATP 安全边界。

ATO 优化模型采用可解释的多目标评分方法，不引入 sklearn / PyTorch / TensorFlow，也不做深度学习训练。优化器只在 `approach_station` / `braking_to_stop` / `creep` 等状态中选择目标速度策略，PID 仍负责跟踪目标速度并输出牵引/制动级位。

策略字段：

- `selected_strategy`：当前选中的策略，例如 `conservative_brake` / `comfort_brake` / `energy_saving` / `precise_stop` / `safety_stop` / `holding`。
- `score`：选中策略评分，非优化状态可为 `null`。
- `strategy_scores`：候选策略评分列表，每项包含 `strategy`、`target_speed`、`score`。
- `target_id` / `station_name` / `platform_id` / `platform_name` / `stop_target_source`：停车目标来源与站台元数据。

优化器永远不能突破 `ma_state.speed_limit`：`target_speed <= safe_speed_limit`。

回调函数会在后台线程中执行，模块内部如维护共享状态，需要做好线程安全处理。
