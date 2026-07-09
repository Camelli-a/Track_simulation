# 信号控制模块说明

本文档说明当前信号控制模块的定位、输入输出、HTTP 调试接口、ZMQ topic、老师线路数据接入情况、MA 计算逻辑、简化 ATP 制动曲线，以及当前仍保留的简化假设。

## 1. 模块定位

本模块是轨道交通教学仿真项目中的信号控制 / 联锁 / ZC-lite 模块，核心代码位于：

- `backend/app/services/signal_control.py`
- `backend/app/services/signal_track_config.py`
- `backend/app/services/signal_zmq_adapter.py`

核心入口函数：

```python
calculate_signal_snapshot(
    train_states: list[dict],
    route_requests: list[dict] | None = None,
) -> dict
```

当前职责：

- 接收列车状态 `train_state`。
- 根据线路静态数据计算区段占用。
- 根据道岔状态和进路需求判断进路冲突。
- 计算每辆车的 MA 移动授权。
- 基于简化 ATP 制动曲线输出 `permission`、`signal_state`、`speed_limit`。
- 输出 `signal_state` 和 `ma_state`。

需要强调的是，本模块不是工业 SIL4 安全系统。当前实现是课程设计中的简化 CBTC / MA / ATP 思想仿真，用于联调、展示和答辩说明。

## 2. 输入数据

ZMQ 订阅 topic：

```text
train_state
```

`data` 示例：

```json
{
  "vehicle_id": "TRAIN-001",
  "position": 300.0,
  "speed": 40.0,
  "route_id": "R_MAIN",
  "train_length": 120.0
}
```

字段说明：

| 字段 | 说明 |
|------|------|
| `vehicle_id` | 列车编号 |
| `position` | 线路一维坐标，单位 m |
| `speed` | 速度，单位 km/h |
| `route_id` | 当前进路，缺失时默认 `R_MAIN` |
| `train_length` | 列车长度，缺失时使用 `DEFAULT_TRAIN_LENGTH` |

HTTP 调试接口中的 `route_requests` 用于临时进路申请，不和 `ma_limits` 的当前运行进路混在一起：

```json
[
  {
    "vehicle_id": "TRAIN-003",
    "route_id": "R_BRANCH"
  }
]
```

## 3. 输出数据一：signal_state

ZMQ 发布 topic：

```text
signal_state
```

`data` 包含：

```json
{
  "system_mode": "normal",
  "signals": [],
  "sections": [],
  "switches": [],
  "route_results": []
}
```

字段说明：

| 字段 | 说明 |
|------|------|
| `system_mode` | 系统模式，当前为 `normal` |
| `signals` | 信号显示状态，包含 `state`、`signal_state`、`permission` 等 |
| `sections` | 区段占用状态 |
| `switches` | 道岔位置与锁闭状态 |
| `route_results` | 进路申请结果，例如 `switch_locked_conflict` |

## 4. 输出数据二：ma_state

ZMQ 发布 topic：

```text
ma_state
```

`data` 包含：

```json
{
  "ma_limits": []
}
```

`ma_limits` 中重点字段：

| 字段 | 说明 |
|------|------|
| `vehicle_id` | 列车编号 |
| `position` | 当前列车位置，单位 m |
| `route_id` | 当前进路 |
| `ma_limit` | 移动授权终点，单位 m |
| `distance_to_ma` | 当前车到 MA 终点的距离，单位 m |
| `permission` | `allow` / `restricted` / `stop` |
| `signal_state` | `green` / `yellow` / `red` |
| `speed_limit` | 当前约束限速，单位 km/h |
| `target_speed` | 建议目标速度，单位 km/h |
| `reason` | MA 来源原因，例如 `front_vehicle_protection` / `route_end` |
| `front_vehicle_id` | 前车编号，没有前车时为 `null` |
| `front_protection_point` | 前车安全包络边界点 |
| `front_train_length` | 前车长度 |
| `location_uncertainty` | 定位误差裕量 |
| `communication_margin` | 通信 / 计算延迟折算裕量 |
| `safety_margin` | 固定安全裕量 |
| `current_speed` | 当前速度，单位 km/h |
| `route_speed_limit` | 进路限速，单位 km/h |
| `required_stop_distance` | 常用制动停车距离 |
| `emergency_stop_distance` | 紧急制动停车距离 |
| `warning_distance` | restricted/yellow 预警距离 |
| `braking_curve_speed_limit` | 按制动曲线反推的允许速度 |
| `braking_model` | 当前为 `simplified_atp_braking_curve` |

## 5. 老师线路数据接入情况

`signal_track_config.py` 当前已经接入老师 Excel 的半真实静态数据：

- `SECTIONS`：来自 `计轴区段表 + Seg表`，共 259 个区段。
- `SWITCHES`：来自 `道岔表`，共 60 个道岔。
- `SIGNALS`：来自 `信号机表`，共 157 个信号机。
- `ROUTES`：来自 `进路表`，共 249 条真实进路，另保留 `R_MAIN` / `R_BRANCH` 兼容演示进路。

当前限制：

- `section.start` / `section.end` 当前是按表格顺序累计得到的一维近似坐标。
- `signal.position` 当前也是累计坐标近似。
- `required_switches` 第一版仍以人工配置为主。
- `STATIC_SPEED_LIMITS` 第一版已接入 demo 静态限速配置，后续可替换为老师 Excel 静态限速表。
- `side_speed_limit` 单位后续需要结合课程数据定义确认。

## 6. MA 计算逻辑

当前 MA 使用前车安全包络模型。

有前车时：

```text
front_protection_point =
  front_vehicle.position
  - front_train_length
  - location_uncertainty
  - communication_margin
  - safety_margin

ma_limit = min(front_protection_point, route_end)
```

无前车时：

```text
ma_limit = route_end
```

默认参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `DEFAULT_TRAIN_LENGTH` | `120.0` | 默认列车长度，单位 m |
| `LOCATION_UNCERTAINTY` | `5.0` | 定位误差裕量，单位 m |
| `COMMUNICATION_MARGIN` | `10.0` | 通信 / 计算延迟折算裕量，单位 m |
| `SAFETY_MARGIN` | `30.0` | 固定安全裕量，单位 m |

这相当于简化版 ZC 移动授权计算：用前车位置反推前车尾部，再叠加定位误差、通信延迟裕量和固定安全裕量，得到后车不能越过的保护边界。

## 7. 制动曲线限速逻辑

当前不再使用固定 `80m / 200m` 阈值作为主逻辑，而是使用简化 ATP 制动距离模型。

配置参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `REACTION_TIME` | `1.5` | 检测、通信、制动建立等反应时间，单位 s |
| `SERVICE_BRAKE_DECELERATION` | `1.0` | 常用制动减速度，单位 m/s² |
| `EMERGENCY_BRAKE_DECELERATION` | `1.2` | 紧急制动减速度，单位 m/s² |
| `BRAKING_SAFETY_MARGIN` | `30.0` | 制动安全裕量，单位 m |
| `WARNING_MARGIN` | `50.0` | 预警附加距离，单位 m |

公式：

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

制动曲线反推限速会用当前 `distance_to_ma` 反解可允许速度，并与 `route_speed_limit` 取较小值。

## 8. HTTP 调试接口

### GET /api/v1/signal/status

用途：查看当前 mock / 默认信号状态。

返回结构：

```json
{
  "timestamp": 1720000000.0,
  "system_mode": "normal",
  "lights": [],
  "signals": [],
  "sections": [],
  "switches": [],
  "ma_limits": [],
  "route_results": []
}
```

### POST /api/v1/signal/evaluate

用途：不用 ZMQ，手动传 `train_states` 和 `route_requests` 调试信号计算。

请求示例：

```json
{
  "train_states": [
    {
      "vehicle_id": "TRAIN-001",
      "position": 300.0,
      "speed": 40.0,
      "route_id": "R_MAIN",
      "train_length": 120.0
    },
    {
      "vehicle_id": "TRAIN-002",
      "position": 620.0,
      "speed": 30.0,
      "route_id": "R_MAIN",
      "train_length": 120.0
    }
  ],
  "route_requests": [
    {
      "vehicle_id": "TRAIN-003",
      "route_id": "R_BRANCH"
    }
  ]
}
```

该示例中：

- `TRAIN-001` 的 `ma_limit = 455.0`。
- `permission = restricted`。
- `signal_state = yellow`。
- `route_results` 会产生 `switch_locked_conflict`。

## 9. ZMQ 启动与验证

启动顺序：

终端 1：

```bash
python -m app.communication.broker
```

终端 2：

```bash
python -m app.communication.mock_publisher
```

终端 3：

```bash
python -m app.communication.signal_worker
```

终端 4：

```bash
python -m app.communication.test_subscriber
```

说明：

- `mock_publisher` 本身也会发布 `signal_state` / `ma_state`。
- `signal_worker` 也会发布 `signal_state` / `ma_state`。
- 因此测试时会看到两套消息。
- `signal_worker` 的 `ma_state` 可通过 `braking_model` 字段识别。
- `signal_worker` 的 `signal_state` 可通过 `route_results` 字段识别。

ZMQ 包装格式由 `MessageBus` 自动生成：

```json
{
  "topic": "ma_state",
  "timestamp": 1720000000.0,
  "data": {
    "ma_limits": []
  }
}
```

注意：`data` 内不要再放 `type` 或 `timestamp`，避免双层包装。

## 10. 当前简化假设与后续扩展

当前简化假设：

- 当前使用一维线路坐标。
- `section.start` / `section.end` 是按表格顺序累计的近似坐标。
- 真实 Seg 拓扑寻路尚未实现。
- `route_request` 暂未通过 ZMQ 接入。
- `required_switches` 尚未从真实进路自动推断。
- 静态限速表、坡度表、保护区段表暂未接入。
- 制动模型为简化匀减速模型，不是工业级安全制动模型。
- 本系统用于课程设计仿真，不是 SIL4 安全级实现。

后续可扩展：

- 接入 `route_request` topic。
- 接入静态限速表。
- 接入坡度表修正制动距离。
- 根据 Seg 邻接关系生成真实拓扑里程。
- 自动推断进路 `required_switches`。
- 增加完整进路锁闭 / 解锁生命周期。
- 与车辆 ATP / ATO 模块联动。

## 静态限速第一版接入

`signal_track_config.py` 当前新增了第一版 demo 静态限速表 `STATIC_SPEED_LIMITS`：

- `SL-001`：`0.0m <= position < 500.0m`，`speed_limit = 60.0 km/h`
- `SL-002`：`500.0m <= position < 2500.0m`，`speed_limit = 80.0 km/h`

所有速度单位统一为 `km/h`，`start` / `end` 使用当前系统的一维 position 坐标。后续可以从老师 Excel 静态限速表生成真实配置。

`ma_state.ma_limits[]` 新增以下字段：

| 字段 | 说明 |
|------|------|
| `static_speed_limit` | 当前 position 命中的静态线路限速 |
| `static_speed_limit_id` | 当前命中的静态限速区间 ID |
| `fault_speed_limit` | train_state 或 704 映射输入中的故障限速 |
| `speed_limit_reason` | 当前主导限速原因 |

最终 `speed_limit` 是安全速度上限，综合：

- `route_speed_limit`
- `static_speed_limit`
- `fault_speed_limit`
- `braking_curve_speed_limit`

当 `emergency_brake=True` 时，信号输出会直接进入 `stop / red / speed_limit=0`，`speed_limit_reason = emergency_brake`。

ATO/车辆控制模块后续应直接使用 `ma_state.speed_limit` 作为安全速度上限，并在该上限内做牵引、惰行和制动控制；不应绕过信号模块重新判断联锁安全。

## ATO 基础模块与 ato_command

第一版 ATO 模块位于 `signal_ato_controller.py`，职责是在 `ma_state.speed_limit` 安全上限内生成智能驾驶建议，不直接更新车辆动力学。

当前包含：

- demo 停车目标点 `STOP_TARGETS`
- 简化停车曲线 `v = sqrt(2 * a * distance)`
- 基础 `PIDController`
- ATO 状态：`cruise` / `approach_station` / `braking_to_stop` / `creep` / `holding` / `degraded`
- ZMQ topic：`ato_command`

`ato_command.data` 结构：

```json
{
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
      "traction_level": 0,
      "brake_level": 2,
      "holding_brake": false,
      "selected_strategy": "comfort_brake",
      "score": 0.82,
      "strategy_scores": [
        {"strategy": "conservative_brake", "target_speed": 13.8, "score": 0.76},
        {"strategy": "comfort_brake", "target_speed": 16.5, "score": 0.82}
      ],
      "reason": "stop_curve_braking"
    }
  ]
}
```

`target_speed` 始终不超过 `safe_speed_limit`。车辆模块后续订阅 `ato_command` 后自行执行动力学；本模块不替代车辆模型，也不做真实深度学习训练。

### ATO AI 多目标评分模型

当前 AI 优化是可解释的规则评分模型，不引入外部机器学习库，也不做深度学习训练。优化器在安全限速内生成候选策略并评分：

- `conservative_brake`：更早制动，安全裕度更大。
- `comfort_brake`：平滑制动，兼顾停车和舒适。
- `energy_saving`：距离较远时减少牵引/制动切换。
- `precise_stop`：接近停车点时更重视停车精度。

评分目标包括：

- 停车精度
- 乘坐舒适度
- 节能
- 运行效率
- 超速/MA 违规惩罚

优化器只选择 `target_speed`、`selected_strategy`、`score` 和 `strategy_scores`；PIDController 仍负责根据目标速度输出牵引/制动级位。所有候选与最终 `target_speed` 都必须满足 `target_speed <= ma_state.speed_limit`。
