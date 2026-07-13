# 车辆仿真一车一进程与 ATO 状态输出说明

## 1. 总体设计

当前车辆仿真采用：

```text
一车一进程 + 共用 ZMQ topic + vehicle_id 过滤
```

每个车辆进程只维护一个 `Train`。多个车辆进程可以同时运行。ZMQ topic 不做每车拆分，仍然共用：

- `driver_input`
- `ato_command`
- `ma_state`
- `comm_state`
- `power_state`
- `track_info`
- `train_state`

每个车辆进程通过 `vehicle_id` 判断消息是不是发给自己的。

```text
TRAIN-001 进程
  └── TrainManager
        └── TRAIN-001 + TrainAtoController

TRAIN-002 进程
  └── TrainManager
        └── TRAIN-002 + TrainAtoController

TRAIN-003 进程
  └── TrainManager
        └── TRAIN-003 + TrainAtoController
```

## 2. 启动方式

单车进程启动：

```powershell
python -m app.vehicle_sim.main_integrated --vehicle-id TRAIN-001 --train-index 1 --initial-position 0
python -m app.vehicle_sim.main_integrated --vehicle-id TRAIN-002 --train-index 2 --initial-position 300
```

脚本批量启动：

```powershell
.\scripts\run_vehicle_processes.ps1 -Count 3
.\scripts\run_vehicle_processes.ps1 -Count 2 -Spacing 500
.\scripts\run_vehicle_processes.ps1 -Count 2 -NoZmq -Steps 1
```

如果 Windows PowerShell 执行策略禁止直接运行脚本，可以使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_vehicle_processes.ps1 -Count 2 -NoZmq -Steps 1
```

脚本默认生成：

- `TRAIN-001` / `train-index=1` / `initial-position=0`
- `TRAIN-002` / `train-index=2` / `initial-position=300`
- `TRAIN-003` / `train-index=3` / `initial-position=600`

## 3. 消息过滤规则

以下消息严格按 `vehicle_id` 过滤：

- `driver_input`
- `ato_command`
- `ma_state`
- `set_train_state`
- `enable_fallback_ato`

例如：

- `TRAIN-001` 进程收到 `TRAIN-002` 的 `driver_input`，会忽略。
- `TRAIN-001` 进程收到 `TRAIN-002` 的 `ma_state`，会忽略。
- `TRAIN-001` 进程不会因为其他车消息创建新的 `Train`。

以下消息可以作为全局广播：

- `comm_state`
- `power_state`
- `track_info`

规则：

- 不带 `vehicle_id`：视为全局广播，本车处理。
- 带 `vehicle_id`：只处理本车，其他忽略。

## 4. train_state 输出字段

基础字段：

| 字段 | 含义 |
|---|---|
| `vehicle_id` | 车辆 ID，例如 `TRAIN-001` |
| `line_id` | 线路 ID，例如 `LINE-1` |
| `position_m` | 当前位置，单位 m |
| `speed_mps` | 当前速度，单位 m/s |
| `speed_kmh` | 当前速度，单位 km/h |
| `direction` | 方向，`1` 正向，`-1` 反向 |
| `acceleration_mps2` | 加速度，单位 m/s^2 |

ATO / ATP 字段：

- `driving_mode`
- `ato_state`
- `recommended_speed_kmh`
- `recommended_speed_mps`
- `ato_target_speed_kmh`
- `ato_target_speed_mps`
- `ato_traction_level`
- `ato_brake_level`
- `commanded_traction_level`
- `commanded_brake_level`
- `applied_traction_level`
- `applied_brake_level`
- `control_source`
- `atp_intervened`
- `emergency_brake`

三层级位含义：

| 字段前缀 | 含义 |
|---|---|
| `ato_*` | ATO 算法原始建议 |
| `commanded_*` | AM/SM 模式选择和 jerk 限制后的命令 |
| `applied_*` | ATP 最终裁决后真正交给动力学的命令 |

## 5. stop_result 停车误差

`stop_result` 字段用于输出停车误差评价，主要字段包括：

- `vehicle_id`
- `target_position_m`
- `actual_position_m`
- `error_m`
- `error_cm`
- `qualified`
- `status`
- `speed_mps`

误差定义：

```text
error_m = actual_position_m - target_position_m
```

因此：

- `error_m > 0`：停过头 / 冲标
- `error_m < 0`：停太早 / 欠标
- `qualified=True`：满足 +/- 50cm 停车窗

## 6. brake_bias 与自适应

`brake_bias` 表示 ATO 对实际制动能力的估计修正：

- `ato_brake_bias > 1`：认为实际制动偏弱，后续更早制动。
- `ato_brake_bias = 1`：不补偿。
- `ato_brake_bias < 1`：认为实际制动偏强，允许略微放松。

输出字段：

- `ato_brake_bias`
- `ato_brake_bias_enabled`
- `ato_brake_bias_adaptation_enabled`
- `last_brake_bias_adjustment`
- `brake_bias_history_size`

安全限制：

- ATP 介入不参与 brake_bias 自适应。
- emergency 不参与 brake_bias 自适应。
- degraded 不参与 brake_bias 自适应。
- SM 模式不参与 brake_bias 自适应。
- 同一个 `stop_target` 只调整一次。
- `brake_bias` 限制在 `0.7 ~ 1.5`。

## 7. curve_point 曲线数据

每个 `train_state` 中带一个轻量 `curve_point`，用于前端或 data_flow 连续累积后画曲线。

实际速度曲线：

- `speed_mps`
- `speed_kmh`

ATO 推荐速度曲线：

- `recommended_speed_mps`
- `recommended_speed_kmh`

ATO 目标速度曲线：

- `ato_target_speed_mps`
- `ato_target_speed_kmh`

ATP / MA 安全边界：

- `allowed_speed_kmh`
- `eb_trigger_speed_kmh`
- `ma_limit_m`
- `distance_to_ma_m`

停车距离：

- `stop_target_m`
- `distance_to_stop_m`

控制级位：

- `ato_traction_level`
- `ato_brake_level`
- `commanded_traction_level`
- `commanded_brake_level`
- `applied_traction_level`
- `applied_brake_level`

状态：

- `driving_mode`
- `control_source`
- `ato_state`
- `atp_intervened`
- `degraded`

说明：

- `train_state` 默认只输出最新 `curve_point`。
- 不默认输出完整 `curve_history`，避免消息过大。
- 前端或 data_flow 可以按 `vehicle_id` 连续累积 `curve_point` 来画速度曲线、推荐速度曲线、ATO 目标速度曲线和 ATP 安全边界曲线。

## 8. data_flow / 视景系统如何使用

车辆进程只发布自己的 `train_state`。data_flow 或视景适配层负责收集多个车辆进程的 `train_state`，并按 `vehicle_id` 聚合为多车状态。

```text
TRAIN-001 进程 -> train_state(vehicle_id=TRAIN-001)
TRAIN-002 进程 -> train_state(vehicle_id=TRAIN-002)
TRAIN-003 进程 -> train_state(vehicle_id=TRAIN-003)
        ↓
data_flow / 视景适配层按 vehicle_id 聚合
        ↓
前端 / 三维视景 / 实时数据库
```

注意：

- 单个车辆进程不维护其他车列表。
- 多车聚合不放在 `Train` 内部做。
- ZMQ topic 仍然共用，不需要改成 `train_state.TRAIN-001` 这类每车独立 topic。

## 9. 安全场景测试覆盖

当前已覆盖以下突发场景：

- MA 突然缩短
- 红灯 / `signal_state=red`
- 通信中断
- SM 司机超速
- 司机台 emergency
- ATO 越过停车点风险
- 一车一进程忽略其他车 MA
- 一车一进程忽略其他车 `driver_input`
- 安全场景不触发 `brake_bias` 自适应

当前车辆仿真测试结果：

```text
vehicle_sim tests: 187 passed, 1 warning
```

## 10. 给组长/老师的简短说明

目前车辆仿真已经支持一车一进程部署。每个车辆进程通过 `--vehicle-id` 指定唯一车辆，只维护一个 `Train` 实例，并在 `Train` 内部独立运行 ATO 控制器。ZMQ topic 仍然共用，消息通过 `vehicle_id` 过滤，因此不需要改成每车独立 topic。每个进程周期发布本车 `train_state`，包含位置、速度、方向、ATO 状态、ATP 裁决结果、停车误差、`brake_bias` 自适应状态以及 `curve_point` 曲线点。data_flow 或视景适配层可以按 `vehicle_id` 聚合多个车辆进程的 `train_state`，用于前端和三维视景展示。
