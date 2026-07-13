# 车辆侧 ATO 与 train_state 对接最终说明

## 1. 模块定位

本模块负责“车辆侧单车控制与状态发布”。它不是全局信号联锁模块，也不是三维视景渲染模块；它的边界是每辆车内部的控制、动力学推进和对外状态输出。

当前核心代码位于：

- `backend/app/vehicle_sim/train.py`
- `backend/app/vehicle_sim/controllers/train_ato_controller.py`
- `backend/app/vehicle_sim/message_router.py`
- `backend/app/vehicle_sim/models.py`
- `backend/app/vehicle_sim/train_manager.py`
- `backend/app/vehicle_sim/adapters/driver_plc_mapping.py`
- `backend/app/vehicle_sim/adapters/vehicle_api_codec.py`
- `backend/app/vehicle_sim/main_integrated.py`
- `scripts/run_vehicle_processes.ps1`

车辆侧负责：

- 接收司机台 `driver_input`；
- 接收信号 / MA / 限速 / 电源 / 通信状态；
- 在 `Train` 内部进行 AM / SM 模式选择；
- 调用 `TrainAtoController` 生成 ATO 推荐速度、目标速度和牵引/制动级位；
- 调用 ATP 做安全监督；
- 最终调用 `dynamics.py` 更新速度、位置和加速度；
- 生成 `train_state`、`ato_state`、`atp_state`、`door_state`、`curve_point` 等状态；
- 通过 ZMQ / data_flow 给前端、视景系统和司机台回传链路使用。

## 2. Train.step_tick(dt) 主流程

`Train.step_tick(dt)` 是车辆周期推进的唯一动力学入口。`step_manual()` 和 `step_ato()` 只缓存输入，不直接更新位置或速度。

真实流程如下：

1. `_update_doors(dt)` 更新车门状态。
2. `_sync_indicator_outputs()` 同步高压、制动、车门等指示灯输出。
3. `_update_ato_recommendation(dt)` 组装 `AtoControlInput`，调用 `TrainAtoController.compute_control()`，得到 AM 控车命令或 SM 推荐速度。
4. 根据当前 `driving_mode` 选择命令来源：
   - AM：优先使用 Train 内部 ATO 输出；
   - SM：使用司机台缓存的牵引/制动输入，同时保留 ATO 推荐速度；
   - `fallback_ato`：仅作为 legacy / demo 兼容入口；
   - 外部 `ato_command`：只作为兼容缓存入口，不是当前主控制链路。
5. 处理 MA 无效、方向手柄、钥匙开关、车门联锁、停放制动、故障、司机台 emergency 等约束。
6. 生成 `commanded_traction_level` / `commanded_brake_level`。
7. 调用 `_step(traction_level, brake_level, dt)`。
8. `_step()` 内部先调用 `evaluate_atp()`；如果 ATP 触发 emergency，则覆盖牵引为 0、制动为 4。
9. `_step()` 调用 `update_dynamics()` 更新 `position`、`speed_ms`、`acceleration`、牵引力和制动力。
10. `_maybe_generate_stop_result()` 生成停车误差结果。
11. `_maybe_adapt_brake_bias_from_stop_result()` 根据正常 AM 停车结果做保守的 `brake_bias` 自适应。
12. `sim_time_s += max(0.0, float(dt))` 更新时间。
13. `_update_curve_output()` 生成本周期 `curve_point`。
14. `_sync_control_state_to_train_state()` 和 `_sync_public_state()` 同步到 `TrainState`。
15. `_clear_transient_events()` 清除瞬时按钮事件。

## 3. 当前已有算法

### AM / SM 模式

- `driver_input.control_mode == "ato"` 时，车辆侧 `driving_mode` 映射为 AM。
- 其他情况下为 SM。
- `ato_active` / `ato_capable` 保存为硬件状态或能力标志；测试中明确不让 PLC 的 ATO 灯状态单独成为最终模式授权。

### 司机台手柄级位映射

- `main_handle_raw=1`：牵引。
- `main_handle_raw=2`：制动。
- `main_handle_raw=4`：快制，映射为最大常用制动，不等同于 emergency。
- 牵引级位为 0~4。
- 司机台制动级位为 0~7，车辆内部百分比按 0~7 映射；进入 legacy 外部 ATO 命令时会裁剪到 0~4。
- 如果制动百分比或制动级位大于 0，牵引清零，制动优先。

### ATO 推荐速度 / 目标速度

`TrainAtoController` 根据当前位置、速度、MA、停车点、坡度、延迟、制动偏差等计算：

- `recommended_speed_kmh`：推荐速度；
- `ato_target_speed_kmh`：ATO 当前目标速度；
- `ato_traction_level` / `ato_brake_level`：ATO 原始建议级位；
- `commanded_traction_level` / `commanded_brake_level`：本周期准备执行的命令。

### 停车目标 stop_target_m

`Train` 优先使用 `next_stop_target_m`；如果轨道对象提供 `get_stop_position()`，可 fallback 到线路停车点。停车点使用线路绝对里程，单位 m。

### MA 有效性校验

MA 校验由 `ma_validation.py` 和 `TrainAtoController.validate_ma_context()` 共同保障，覆盖：

- MA 终点缺失或无效；
- 允许速度缺失、非有限值或小于等于 0；
- MA 在车后；
- `target_distance_m` 非法；
- `permission` 为 stop / denied / forbidden / none；
- `signal_state` 为 red / stop；
- MA 过期；
- 通信异常。

### ATP 兜底

`_step()` 内调用 `evaluate_atp()`。ATP 覆盖场景包括超速、MA/目标距离不足、通信异常、红灯/禁止通过、电源故障等。触发后：

- `state.emergency_brake=True`；
- `state.mode="emergency"`；
- `applied_traction_level=0`；
- `applied_brake_level=4`；
- `control_source="emergency"`；
- `atp_intervened=True`。

### 牵引/制动级位选择

ATO 使用速度误差和低速位置控制规则输出级位。最终在进入动力学前仍会经过 Train 侧联锁、安全和 ATP 裁决。

### jerk limit / ATO 命令平滑

AM 模式下，ATO 命令使用上一周期 `commanded_*` 做级位变化率限制，避免普通制动场景中 0->4 或 4->0 的突变。安全场景会 bypass 平滑，包括 holding、degraded、越过停车点、MA 过近等。

### 坡度补偿

`gradient_permille` 以千分坡处理：

- 正坡度表示上坡，有效制动能力增强；
- 负坡度表示下坡，有效制动能力减弱。

坡度补偿只影响 ATO 停车曲线和 SM 推荐速度，不修改 `dynamics.py` 或 ATP 公式。

### 控制延迟补偿

ATO 计算时可启用一阶预测：

- 使用当前位置、速度、加速度和 `control_delay_sec` 预测控制决策点；
- 预测值只用于 ATO 决策；
- 不覆盖真实 `TrainState.position` / `speed_ms`；
- `stop_result` 仍使用真实位置。

### brake_bias 制动非线性补偿

`brake_bias` 表示 ATO 对实际制动能力的估计修正：

- `brake_bias > 1.0`：认为实际制动偏弱，停车曲线更保守；
- `brake_bias = 1.0`：不补偿；
- `brake_bias < 1.0`：认为实际制动偏强，可略微放松。

范围限制为 0.7~1.5。该补偿不影响 ATP、emergency、degraded、holding，也不修改真实动力学公式。

### stop_result 停车误差

停车误差由 `TrainAtoController.evaluate_stop_result()` 计算：

- `error_m = actual_position_m - target_position_m`；
- `error_m > 0` 表示停过头；
- `error_m < 0` 表示停太早；
- `qualified=True` 表示误差在 ±0.5 m 内且速度足够低。

### brake_bias 自适应

只在新的、正常 AM 停车结果后微调：

- ATP 介入不学习；
- emergency 不学习；
- degraded 不学习；
- SM 不学习；
- 同一个 `stop_target` 只学习一次；
- 每次调整幅度限制在 `ato_brake_bias_max_step_per_stop` 内；
- 最终仍限制在 0.7~1.5。

### curve_point 曲线输出

每个周期生成一个轻量 `curve_point`，嵌入 `train_state.curve_point`，不单独新增 topic。内容包括实际速度、推荐速度、ATO 目标速度、MA 边界、停车距离、三层级位、状态、brake_bias 等。

### door interlock

如果车门未全关，`Train.step_tick()` 会清零牵引，`control_source="door_interlock"`。车门状态同时通过 `train_state` 和 `door_state` 输出。

### parking brake

停放制动施加时牵引清零、制动百分比为 100%，`control_source="parking_brake"`。释放要求车辆处于低速/停止且非 emergency。

### emergency_button / emergency_cmd

司机台 `emergency_button` 或 `emergency_cmd` 触发后：

- `state.emergency_brake=True`；
- `state.mode="emergency"`；
- 牵引清零；
- 制动拉满；
- 不受 jerk limit 和 brake_bias 削弱。

### 一车一进程 vehicle_id 过滤

`main_integrated.py` 通过 `--vehicle-id` 启动单车进程。`MessageRouter(owned_vehicle_id=...)` 只处理本车消息。共用 topic 不拆分，每条消息靠 `vehicle_id` 过滤。

## 4. 三层级位解释

- `ato_traction_level` / `ato_brake_level`：ATO 原始建议。用于展示 ATO 算法本来想给出的级位。
- `commanded_traction_level` / `commanded_brake_level`：模式选择、jerk limit、司机台输入、door/parking 等 Train 侧约束后的命令，处于 ATP 裁决前。
- `applied_traction_level` / `applied_brake_level`：ATP / emergency 等安全裁决后，真正交给 `update_dynamics()` 的级位。

因此，在 ATP 介入时可能出现：

```json
{
  "ato_traction_level": 1,
  "commanded_traction_level": 1,
  "applied_traction_level": 0,
  "applied_brake_level": 4,
  "control_source": "emergency",
  "atp_intervened": true
}
```

## 5. ZMQ 通信现状

### 输入 topic

- `driver_input`：来自司机台 PLC 解析结果或虚拟司机输入；按 `vehicle_id` 路由到对应 Train。
- `comm_state`：司机台 / ZMQ 通信状态；无 `vehicle_id` 时作为广播，有 `vehicle_id` 时只处理本车。
- `ma_state`：信号 / 调度 / MA 状态；支持单条和 `ma_limits[]` 批量输入；一车一进程只取本车。
- `speed_constraint`：外部限速约束，按 `vehicle_id` 处理。
- `signal_state` / `interlocking_state`：信号或联锁安全状态，按 `vehicle_id` 处理。
- `power_state`：供电状态；无 `vehicle_id` 时作为广播。
- `track_info`：线路信息；无 `vehicle_id` 时作为广播。
- `fault_event`：故障事件；可按 `vehicle_id` 或 `scope=all` 处理。
- `ato_command`：兼容旧外部 ATO 命令；车辆侧只缓存，不作为当前主控制算法。
- `enable_fallback_ato`：legacy/demo fallback ATO 入口。
- `set_train_state` / `add_train` / `remove_train` / `clear_trains` / `reset_trains`：调试和管理入口；一车一进程模式下不会变成多车进程。

### 输出 topic

`main_integrated.py` 每周期发布：

- `train_state`：核心车辆状态；
- `ato_state`：ATO 摘要状态；
- `atp_state`：ATP 监督状态；
- `door_state`：门状态；
- alarm 事件：当 `last_alarm` 存在时发布。

`curve_point` 当前不单独开 topic，默认嵌在 `train_state.curve_point` 中。

司机台 `send_to_plc()` 所需字段来源：

- `vehicle_speed_kmh`：`train_state.vehicle_speed_kmh`；
- `high_voltage_on`：`train_state.high_voltage_on`；
- `brake_bad_light`：`train_state.brake_bad_light`；
- `door_open_light`：`train_state.door_open_light`；
- `door_closed_light`：`train_state.door_closed_light`；
- `ato_capable`：`train_state.ato_capable`；
- `ato_active`：`train_state.ato_active`；
- `auto_reverse_cap`：`train_state.auto_reverse_cap`；
- `auto_reverse_active`：`train_state.auto_reverse_active`；
- `network_fault`：由通信模块 / `comm_state` 判断，不在 `train_state` 中直接输出。

### train_state 示例

`ZmqPublisher` 会把 `type` 作为 topic 发布，业务 `data` 中不重复放 `type` / `timestamp`。下面示例按 MessageBus 外层包装展示：

```json
{
  "topic": "train_state",
  "timestamp": 1234567890.123,
  "data": {
    "vehicle_id": "TRAIN-001",
    "train_index": 1,
    "line_id": "LINE-1",
    "position": 123.4,
    "position_m": 123.4,
    "position_reference": "front_cab",
    "front_position_m": 123.4,
    "rear_position_m": 103.4,
    "speed_ms": 5.6,
    "speed_mps": 5.6,
    "speed_kmh": 20.16,
    "vehicle_speed_kmh": 20.16,
    "acceleration_mps2": 0.0,
    "direction": 1,
    "direction_code": 1,
    "direction_text": "forward",
    "mode": "ato",
    "driving_mode": "AM",
    "control_source": "ato",
    "ato_active": true,
    "ato_capable": true,
    "ato_state": "braking_to_stop",
    "recommended_speed_kmh": 20.0,
    "recommended_speed_mps": 5.556,
    "ato_target_speed_kmh": 20.0,
    "ato_target_speed_mps": 5.556,
    "ato_traction_level": 0,
    "ato_brake_level": 1,
    "commanded_traction_level": 0,
    "commanded_brake_level": 1,
    "applied_traction_level": 0,
    "applied_brake_level": 1,
    "atp_intervened": false,
    "emergency_brake": false,
    "stop_target": 300.0,
    "distance_to_stop": 50.0,
    "stop_result": null,
    "door_state": "closed",
    "doors_all_closed": true,
    "door_open_light": false,
    "door_closed_light": true,
    "high_voltage_on": true,
    "brake_bad_light": false,
    "parking_brake": false,
    "ato_brake_bias": 1.0,
    "ato_brake_bias_enabled": true,
    "ato_brake_bias_adaptation_enabled": true,
    "last_brake_bias_adjustment": null,
    "curve_point": {
      "vehicle_id": "TRAIN-001",
      "position_m": 123.4,
      "speed_mps": 5.6,
      "speed_kmh": 20.16,
      "recommended_speed_kmh": 20.0,
      "ato_target_speed_kmh": 20.0,
      "ma_limit_m": 500.0,
      "distance_to_ma_m": 376.6,
      "stop_target_m": 300.0,
      "distance_to_stop_m": 176.6,
      "control_source": "ato",
      "atp_intervened": false
    }
  }
}
```

## 6. 与视景系统 data_requirements.md 的对齐结果

| 需求                | 当前对齐情况                                                                                                                         |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `vehicle_id`        | `TrainState.to_protocol()` 输出，且一车一进程时每个进程只发布本车 ID。                                                               |
| `position_m`        | 已输出，来源为 `state.position`，单位 m。                                                                                            |
| `speed_mps`         | 已输出，来源为 `state.speed_ms`，单位 m/s。                                                                                          |
| `direction`         | 已输出，`TrainState.protocol_direction` 保证对外为 1 或 -1；内部 `direction_code=0` 对外默认归一为 1。                               |
| `line_id`           | 已输出，默认 `LINE-1` 或创建 Train 时传入。                                                                                          |
| 100ms 更新          | `main_integrated.py --dt` 默认 0.1；`run_vehicle_processes.ps1` 默认 `-Dt 0.1`；主循环即使状态不变也会 `step_all()` 并发布当前状态。 |
| 速度 <= 33.333 m/s  | `train_state` 不做截断，避免掩盖仿真异常；速度约束由 MA、限速、ATP 和测试场景保证。视景适配层可按数据有效性要求做告警。              |
| 其他车辆最多 128 辆 | 单车 Train 不维护全局多车列表；多车聚合由 data_flow / 视景适配层按 `vehicle_id` 完成。                                               |
| 边号 / 区段         | `edge_id`、`section_id`、`edge_offset_m` 已输出；视景需要的边号换算仍建议由视景或 data_flow 根据线路表处理。                         |

## 7. 与司机台 driver-desk-interface.md 的对齐结果

| 司机台字段 / 行为                    | 当前对齐情况                                                                                                                                                                                              |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `vehicle_id`                         | `MessageRouter` 按 `vehicle_id` 找到 Train；一车一进程由 `owned_vehicle_id` 过滤非本车消息。物理司机台默认只允许控制 `physical_driver_vehicle_id`。                                                       |
| `direction`                          | `forward` -> `direction_code=1`；`backward` / `reverse` -> `direction_code=-1`；`neutral` -> `direction_code=0`，并禁止牵引。                                                                             |
| `main_handle_raw=4`                  | 解析为快制，`fast_brake=True`，常用制动百分比 100%，不等同于 emergency。                                                                                                                                  |
| `traction_level` 0~4                 | 进入车辆侧缓存，超界时裁剪。                                                                                                                                                                              |
| `brake_level` 0~7                    | 司机台常用制动按 0~7 保存和百分比映射；外部 ATO 兼容命令进入车辆动力学前裁剪到 0~4。                                                                                                                      |
| `traction_percent` / `brake_percent` | 作为 canonical 控制输入；如果存在百分比，优先按百分比映射级位。                                                                                                                                           |
| `control_mode`                       | `"ato"` 映射 AM；其他映射 SM。PLC 的 `ato_active` 作为硬件状态保存，不单独改变控制授权。                                                                                                                  |
| `emergency_button` / `emergency_cmd` | 触发 `manual_emergency_requested` / `emergency_pending`，下一周期 emergency 覆盖牵引/制动。                                                                                                               |
| `key_switch=false`                   | 禁止牵引，不直接改写速度/位置。                                                                                                                                                                           |
| door open/close                      | 瞬时开关通过 rising edge 缓存，`DoorState` 更新车门状态；门未全关时 `door_interlock` 禁止牵引。                                                                                                           |
| `parking_apply` / `parking_release`  | 支持停放制动施加和低速非 emergency 条件下释放。                                                                                                                                                           |
| `comm_state`                         | `driver_console_connected && zmq_connected` 映射为 `comm_ok`；通信异常进入 ATP 监督。                                                                                                                     |
| `network_fault_light`                | 保存为硬件反馈灯状态，不直接替代 `comm_state`。                                                                                                                                                           |
| send_to_plc                          | `DriverDeskSource.send_to_plc()` 已支持速度、高压、制动故障、门灯、网络故障、ATO能力/激活、自动折返等字段。车辆侧 `train_state` 提供除 `network_fault` 外的大部分来源；`network_fault` 应由通信模块提供。 |

## 8. 旧代码保留与后续清理建议

### 当前仍保留，且不应直接删除

- `backend/app/services/signal_ato_controller.py`：信号侧仍有 `SignalZmqAdapter` 引用并发布 `ato_command`；相关信号测试仍覆盖它。当前它是信号侧 legacy / 外部建议链路，不是车辆主控 ATO。
- `backend/app/vehicle_sim/main_ato_local.py`：本地 demo / 调试入口，仍调用 `step_ato()`。
- `backend/app/vehicle_sim/controllers/fallback_ato.py`：`enable_fallback_ato`、场景文件和测试仍引用；作为 legacy / demo fallback 保留。
- `Train.step_ato()` / `ato_command`：兼容旧外部 ATO 命令和 data_flow / API 现有 schema；当前只缓存，不直接积分。

### 可后续清理但本次不建议删

- 如果后续确认信号侧不再需要外部 `ato_command`，可将 `signal_ato_controller.py` 标注为 deprecated，并迁移测试。
- 如果所有 demo 都改为 Train 内部 ATO，可逐步移除 `main_ato_local.py` 或归档到 demo 目录。
- 如果 fallback ATO 不再用于应急演示，可保留接口但在文档中标记为 legacy。

本次没有删除任何旧文件，避免破坏 API、测试、demo 或兼容链路。

## 9. 启动方式

单车启动：

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.vehicle_sim.main_integrated --vehicle-id TRAIN-001 --train-index 1 --initial-position 0
.\.venv\Scripts\python.exe -m app.vehicle_sim.main_integrated --vehicle-id TRAIN-002 --train-index 2 --initial-position 300
```

批量启动：

```powershell
.\scripts\run_vehicle_processes.ps1 -Count 3
.\scripts\run_vehicle_processes.ps1 -Count 2 -Spacing 500
.\scripts\run_vehicle_processes.ps1 -Count 2 -NoZmq -Steps 1
```

一车一进程不是每车独立 topic。所有车辆仍共用 `driver_input` / `ma_state` / `comm_state` / `train_state` 等 topic，通过 `vehicle_id` 过滤。

## 10. ATO 控制业务逻辑分层

### 10.1 输入层

每个 `Train.step_tick(dt)` 周期会综合以下输入。所有输入先缓存到 `Train`，不会在消息到达时直接积分车辆位置或速度。

| 输入                        | 主要来源                      | 进入 Train 后的作用                                                                                               |
| --------------------------- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| 司机台输入 `driver_input`   | `DriverDeskSource` 或虚拟司机 | 缓存牵引/制动、方向、钥匙、门控、parking、emergency 等离散状态。                                                  |
| MA / 信号状态 `ma_state`    | 信号 / 调度 / MA 模块         | 更新 `ma_limit`、`allowed_speed_kmh`、`eb_trigger_speed_kmh`、`target_distance_m`、`permission`、`signal_state`。 |
| 外部限速 `speed_constraint` | data_flow / 调试 / 临时限速   | 写入 `external_speed_limit_kmh`，与 MA 允许速度取更保守值。                                                       |
| 通信状态 `comm_state`       | 司机台通信源                  | 更新 `comm_ok`、`last_comm_message_at`，进入 ATO MA 时效性检查和 ATP 通信丢失判断。                               |
| 供电状态 `power_state`      | 供电模块                      | 更新 `power_fault`、`power_factor`，影响动力学牵引可用功率和 ATP emergency。                                      |
| 轨道信息                    | `TrackMap` / `track_info`     | 提供当前位置坡度、线路限速、停车点、区段边号。                                                                    |
| 车辆实际状态                | `TrainState`                  | 提供 `position`、`speed_ms`、`acceleration`、上一周期级位。                                                       |
| 离散约束                    | Train 内部缓存                | 车门、停放制动、钥匙、方向手柄、紧急按钮等最终约束牵引/制动。                                                     |

### 10.2 模式层

当前代码区分两类概念：

- `driving_mode`：驾驶模式，只表示司机选择或车辆当前运行在 AM / SM。
- `state.mode`：对外状态模式，取值为 `manual` / `ato` / `atp` / `emergency`。
- `control_source`：本周期命令来源或约束来源，例如 `manual`、`ato`、`degraded`、`emergency`、`door_interlock`、`parking_brake`、`fallback`、`emergency_button`、`fault_event`。

不要把 `driving_mode` 和 `control_source` 混为一谈。典型关系如下：

| 层面         | 真实字段                                                | 业务含义                                        |
| ------------ | ------------------------------------------------------- | ----------------------------------------------- |
| SM           | `driving_mode="SM"`                                     | 司机台手柄控车；ATO 只计算推荐速度。            |
| AM           | `driving_mode="AM"`                                     | Train 内部 ATO 参与控车。                       |
| fallback ATO | `fallback_ato is not None`，`control_source="fallback"` | 旧 demo / fallback 兼容链路，不是主控制链路。   |
| emergency    | `state.mode="emergency"`                                | ATP、司机台 emergency、故障等安全覆盖状态。     |
| degraded     | `ato_state="degraded"` 或 `control_source="degraded"`   | ATO 降级；AM 下不继续牵引，采用保守制动或保持。 |

### 10.3 ATO 决策层

`Train._update_ato_recommendation(dt)` 组装 `AtoControlInput`，再调用 `TrainAtoController.compute_control()`。

主要输入：

- `vehicle_id`
- `position_m`
- `speed_ms`
- `acceleration_ms2`
- `ma_limit_m`
- `allowed_speed_kmh`
- `stop_target_m`
- `target_distance_m`
- `permission`
- `signal_state`
- `driving_mode`
- `direction`
- `ma_valid`
- `ma_age_sec`
- `max_ma_age_sec`
- `comm_ok`
- `dt`
- `control_delay_sec`
- `delay_compensation_enabled`
- `gradient_permille`
- `gradient_compensation_enabled`
- `previous_commanded_traction_level`
- `previous_commanded_brake_level`
- `jerk_limit_enabled`
- `brake_bias`
- `brake_bias_enabled`

主要输出：

- `recommended_speed_kmh`
- `ato_target_speed_kmh`
- `ato_traction_level`
- `ato_brake_level`
- `commanded_traction_level`
- `commanded_brake_level`
- `ato_state`
- `control_source`
- `degraded`
- `reason`
- `distance_to_stop_m`
- `distance_to_ma_m`

SM 下输出推荐速度和 ATO 原始建议，但 `commanded_traction_level=0`、`commanded_brake_level=0`，不接管司机输入。AM 下输出会成为 Train 侧命令候选。

### 10.4 Train 约束层

ATO 输出不会直接进入动力学。`Train.step_tick()` 会继续施加车辆侧约束：

- AM 且 MA 无效：禁止继续牵引。
- 钥匙未开：禁止牵引。
- 方向手柄为 neutral：禁止牵引。
- 车门未全关：禁止牵引，`control_source="door_interlock"`。
- 停放制动已施加：牵引清零，制动百分比 100%，`control_source="parking_brake"`。
- 司机台 emergency 或故障 emergency：直接进入 `state.mode="emergency"`。
- 制动优先：只要制动百分比或制动级位大于 0，牵引清零。

### 10.5 ATP 裁决层

`_step()` 内部先调用 `evaluate_atp()`，再调用 `update_dynamics()`。

- ATP 不介入：`applied_*` 等于本周期 `commanded_*`。
- ATP 介入：`applied_traction_level=0`，`applied_brake_level=4`。
- ATP 介入后：`state.mode="emergency"`，`control_source="emergency"`，`state.emergency_brake=True`，`atp_intervened=True`。

ATP 是最终安全裁决之一，不受 ATO 的 jerk limit、brake_bias 或推荐速度削弱。

### 10.6 动力学层

`update_dynamics()` 只接收最终级位和当前状态，统一更新：

- `speed_ms`
- `position`
- `acceleration`
- `actual_traction_force_n`
- `actual_brake_force_n`

ATO 不直接修改位置、速度、加速度；真实位置和速度只由动力学积分推进。

## 11. ATO 状态机 / ato_state 说明

真实代码中的 `ato_state` 字符串为：

- `approaching`
- `braking_to_stop`
- `creep`
- `holding`
- `manual_recommend`
- `manual_creep_recommend`
- `degraded`

代码中没有单独的 `cruise`、`coast`、`traction`、`emergency` 作为 `ato_state`。这些是业务行为或 `control_source/state.mode`，不是 ATO 状态名。

| ato_state                | 触发条件                                                                | 控制行为                                                 | 牵引/制动倾向                            | 是否安全降级 | 备注                                           |
| ------------------------ | ----------------------------------------------------------------------- | -------------------------------------------------------- | ---------------------------------------- | ------------ | ---------------------------------------------- |
| `approaching`            | AM，MA 有效，尚未进入明显制动或蠕行状态。                               | 根据停车曲线和目标速度进行速度跟随。                     | 可能牵引、惰行或小制动，取决于速度误差。 | 否           | 业务上可理解为接近目标/巡航跟随状态。          |
| `braking_to_stop`        | AM，当前速度高于目标速度，或越过停车点/需要制动。                       | 牵引清零，输出制动级位。                                 | 制动为主。                               | 否           | 如果越过停车点，会禁止牵引并趋向保守制动。     |
| `creep`                  | AM，停车点安全且 `distance_to_stop_m <= CREEP_DISTANCE_M`。             | 使用低速位置-速度控制，目标速度不超过 `CRAWL_SPEED_MS`。 | 小制动/惰行，必要时低速牵引。            | 否           | 用于最后 5 m 左右低速对标。                    |
| `holding`                | AM，停车点安全，距离在 `HOLD_DISTANCE_M` 内且速度低于 `HOLD_SPEED_MS`。 | 目标速度 0，保持制动。                                   | 制动保持，`brake_level=4`。              | 否           | 满足停车保持条件，后续可能生成 `stop_result`。 |
| `manual_recommend`       | SM，允许速度有效，未进入低速推荐区。                                    | ATO 只计算推荐速度，不接管司机命令。                     | `commanded_*` 为 0。                     | 否           | 司机台手柄仍是实际命令来源。                   |
| `manual_creep_recommend` | SM，存在停车目标且进入低速区。                                          | 推荐速度按低速对标逻辑降低。                             | `commanded_*` 为 0。                     | 否           | 只提示司机，不直接控车。                       |
| `degraded`               | MA/限速/通信/permission/signal 等无效或不安全。                         | AM 下不继续牵引，制动或保持；SM 下推荐速度为 0。         | AM 制动，SM 不接管。                     | 是           | 降级原因在 `reason` 中。                       |

### 状态转换业务说明

1. 没有有效 MA、红灯、permission stop/denied、通信异常：AM 进入 `degraded`，不继续牵引。
2. 距离停车点较远且当前速度低于目标速度：通常仍是 `approaching`，级位上表现为牵引。
3. 当前速度接近推荐速度：通常仍是 `approaching` 或 SM 的 `manual_recommend`，级位表现为 0 牵引、0 制动或小级位。
4. 当前速度超过推荐速度或接近停车曲线：进入或保持 `braking_to_stop`。
5. 进入低速停车区：进入 `creep`，使用位置-速度串级目标速度。
6. 已低速进入停车窗口：进入 `holding`，生成停车保持命令，随后 Train 可生成 `stop_result`。
7. 越过停车点或安全距离不足：不会继续牵引，进入 `braking_to_stop` 或 `degraded`，由 Train/ATP 继续兜底。

## 12. ATO 典型运行场景

### 场景 1：AM 正常牵引加速

- 输入条件：MA 有效；允许速度大于 0；前方停车点或 MA 距离充足；当前速度低于目标速度；方向 forward；车门关闭；钥匙有效；无 emergency。
- ATO 判断：`compute_am_command()` 计算停车曲线目标速度，若当前速度明显低于目标速度，则 `_levels_for_speed_error()` 倾向给牵引。
- 输出级位：`ato_traction_level > 0`，`ato_brake_level=0`；经过 jerk limit 后 `commanded_traction_level` 逐步上升。
- Train 侧约束：钥匙、方向、门、parking、MA 再检查；无异常则允许牵引。
- ATP：正常不介入，`applied_traction_level == commanded_traction_level`。
- train_state：`driving_mode="AM"`，`control_source="ato"`，`state.mode="ato"`，`atp_intervened=false`。

### 场景 2：AM 巡航 / 惰行

- 输入条件：当前速度接近 `recommended_speed_kmh` / `ato_target_speed_kmh`；停车点仍较远；不需要明显制动。
- ATO 判断：真实 `ato_state` 通常仍为 `approaching`，代码没有单独 `cruise` 或 `coast` 状态。
- 输出级位：可能为 `0/0`，或小牵引/小制动，取决于速度误差阈值。
- Train 侧约束：正常透传 commanded 到 `_step()`。
- ATP：若未超速且 MA 安全，不介入。
- train_state：`curve_point.speed_kmh` 与 `curve_point.recommended_speed_kmh` 接近，`control_source="ato"`。

### 场景 3：AM 进站制动

- 输入条件：`stop_target_m` 有效；`distance_to_stop_m` 变短；当前速度高于停车曲线允许速度。
- ATO 判断：进入 `braking_to_stop`，或在低速区前持续制动。
- 输出级位：`ato_brake_level > 0`，牵引清零；jerk limit 可能让 `commanded_brake_level` 逐周期上升。
- Train 侧约束：制动优先，`traction=0`。
- ATP：如果制动不足或 MA 过近，可能进一步 emergency。
- train_state：`distance_to_stop` 逐渐减小，`curve_point.stop_target_m`、`curve_point.distance_to_stop_m`、`ato_brake_level` 有值。

### 场景 4：AM 低速对标 / 停车保持

- 输入条件：进入 `POSITION_CONTROL_DISTANCE_M=12.0 m` 内，尤其是 `CREEP_DISTANCE_M=5.0 m` 内；速度较低。
- ATO 判断：先进入 `creep`，按 `POSITION_KP=0.28` 生成低速目标；距离足够小且速度低于 `HOLD_SPEED_MS=0.15 m/s` 时进入 `holding`。
- 输出级位：`creep` 下以小制动/惰行为主；`holding` 下 `brake_level=4`。
- Train 侧约束：正常执行；如果停车点附近满足条件，生成 `stop_result`。
- ATP：正常对标不介入；越权或超速会介入。
- train_state：`ato_state="creep"` 或 `"holding"`；`stop_result` 包含 `error_m = actual_position - target_position`、`qualified`、`status`。

### 场景 5：SM 人工驾驶 + ATO 推荐速度

- 输入条件：`control_mode="manual"`；司机台给牵引/制动级位或百分比；MA/允许速度可用。
- ATO 判断：进入 `manual_recommend` 或 `manual_creep_recommend`，只计算推荐速度。
- 输出级位：ATO 输出的 `commanded_*` 为 0；Train 使用司机台缓存作为 commanded。
- Train 侧约束：钥匙、方向、门、parking、emergency 仍然约束司机命令。
- ATP：司机超速、MA 不足、通信异常时仍覆盖 applied。
- train_state：`driving_mode="SM"`，`control_source="manual"`，`recommended_speed_kmh` 仍可显示。

### 场景 6：异常 / 降级 / ATP 介入

- MA 无效、红灯、permission stop：ATO 进入 `degraded`，AM 不继续牵引。
- 通信中断：ATP 触发 communication_lost emergency。
- 司机台 emergency：Train 直接设置 emergency，牵引清零，制动拉满。
- 车门未关：`control_source="door_interlock"`，禁止牵引。
- parking brake：`control_source="parking_brake"`，牵引清零，制动百分比 100%。
- 超速或 MA 距离不足：ATP 覆盖 `applied_*`。

这些场景中 `brake_bias`、jerk limit 不会削弱 emergency；`applied_*` 可能不同于 `commanded_*`。

## 13. 当前算法清单

### 13.1 driver_input 手柄解析算法

- 输入：`main_handle_raw`、`traction_percent`、`brake_percent`、`traction_level`、`brake_level`、`direction`、瞬时按钮。
- 核心判断：
  - `main_handle_raw=1` 使用牵引百分比；
  - `main_handle_raw=2` 使用制动百分比；
  - `main_handle_raw=4` 输出快制，常用制动 100%；
  - 没有手柄原始值时，优先使用百分比，再使用显式级位；
  - 制动优先，制动大于 0 时牵引清零；
  - 瞬时按钮通过 `_rising_edge()` 识别。
- 输出：缓存牵引/制动级位、百分比、方向、门控、parking、emergency 等状态。
- 保护边界：`fast_brake` 不是 emergency；`emergency_button` / `emergency_cmd` 才触发 emergency。

### 13.2 AM/SM 模式选择算法

- 输入：`driver_input.control_mode`、`ato_active`、`ato_capable`。
- 核心判断：`control_mode=="ato"` -> AM；否则 SM。
- 输出：`driving_mode`。
- 保护边界：`ato_active`/`ato_capable` 保存为状态和灯显，不单独成为控车授权。

### 13.3 MA 有效性校验算法

- 输入：`ma_limit`、`allowed_speed_kmh`、`target_distance_m`、`permission`、`signal_state`、`updated_at`、`direction_code`、`comm_ok`。
- 核心判断：
  - `validate_ma()` 检查时间戳、方向、权限、信号、距离一致性；
  - `TrainAtoController.validate_ma_context()` 进一步检查 ATO 控车所需字段；
  - `target_distance_m` 与绝对 MA 同时存在时取更保守距离。
- 输出：`MaValidationResult`、`ma_valid`、`distance_to_ma_m`。
- 保护边界：无有效 MA 时 AM 不牵引。

### 13.4 ATO 推荐速度算法

- 输入：允许速度、MA、停车目标、当前位置、速度、延迟预测、坡度、brake_bias。
- 核心判断：推荐速度不超过安全速度；若有停车目标，则按停车曲线收敛。
- 输出：`recommended_speed_kmh`、`ato_target_speed_kmh`。
- 保护边界：SM 只推荐不控车；AM 才参与控车。

### 13.5 停车曲线算法

- 输入：`distance_to_stop_m`、`effective_decel_ms2`、`allowed_speed_kmh`。
- 核心公式：`target_speed = sqrt(2 * effective_decel * distance)`，再限制到 `allowed_speed_kmh`。
- 输出：目标速度和制动倾向。
- 保护边界：停车目标在 MA 外时以 MA 边界为有效目标；越过停车点后不牵引。

### 13.6 巡航 / 速度跟随算法

- 真实代码阈值：
  - 速度高于目标 10 km/h 以上：制动 4；
  - 高于 6 km/h：制动 3；
  - 高于 3 km/h：制动 2；
  - 高于 `SPEED_DEADBAND_KMH=1.0`：制动 1；
  - 当前速度低于目标 3 km/h 以上且目标速度大于 1 km/h：牵引 1 或 2；
  - 其余：0 牵引 / 0 制动。
- 输出：ATO 原始级位。
- 保护边界：最终仍需 Train 约束和 ATP。

### 13.7 jerk limit 级位平滑算法

- 输入：`previous_commanded_traction_level`、`previous_commanded_brake_level`、目标级位。
- 核心判断：牵引和制动每周期最大变化为 1 级；制动未释放前不允许给牵引。
- 输出：平滑后的 `commanded_*`。
- bypass 场景：`holding`、`degraded`、安全类 reason、越过停车点、MA 过近、目标制动 4 且当前速度明显高于目标。

### 13.8 控制延迟补偿算法

- 输入：`speed_ms`、`acceleration_ms2`、`control_delay_sec`、`direction`。
- 核心判断：默认延迟 0.3 s，最大 1.0 s；预测位置和速度用于 ATO 决策。
- 输出：预测控制位置和速度。
- 保护边界：不覆盖真实 `TrainState`。

### 13.9 坡度补偿算法

- 输入：`gradient_permille`。
- 核心判断：正坡度上坡增加有效减速度，负坡度下坡降低有效减速度；坡度限制在 ±60‰。
- 输出：坡度修正后的有效减速度。
- 保护边界：只影响 ATO 曲线和推荐速度，不改动力学主公式。

### 13.10 brake_bias 制动非线性补偿

- 输入：`brake_bias`，范围 0.7~1.5。
- 核心判断：`effective_decel / brake_bias`；`brake_bias>1` 更保守，`brake_bias<1` 更放松。
- 输出：brake_bias 修正后的有效减速度。
- 保护边界：不影响 ATP、emergency、degraded、holding、真实动力学。

### 13.11 stop_result 停车评价算法

- 输入：目标位置、实际位置、速度。
- 核心判断：`error_m = actual_position - target_position`；速度高于 `HOLD_SPEED_MS` 为 `not_stopped`；误差 ±0.5 m 内为 `in_window`。
- 输出：`status`、`qualified`、`error_m`、`error_cm`。
- 保护边界：只评价，不反向修改位置速度。

### 13.12 brake_bias 自适应算法

- 输入：正常 AM 停车产生的新 `stop_result`。
- 核心判断：误差死区 0.20 m；学习率 0.04；每站最大调整 0.05；同一目标只调一次。
- 输出：新的 `ato_brake_bias` 和 `last_brake_bias_adjustment`。
- 保护边界：ATP、emergency、degraded、SM、速度未停稳、vehicle_id 不匹配时不学习。

### 13.13 ATP 安全监督算法

- 输入：轨道限速、MA、允许速度、EB 触发速度、目标距离、power_fault、comm_ok、坡度。
- 核心判断：通信超时、电源故障、超 EB 速度、MA 越界、紧急制动曲线越界等触发 emergency。
- 输出：`AtpDecision`。
- 保护边界：一旦 emergency，覆盖 applied 级位。

### 13.14 door interlock 算法

- 输入：门控按钮、门模式、当前速度、停车点。
- 核心判断：车门未全关时禁止牵引；低速/停车条件下可按模式开关门。
- 输出：`DoorState` 和 `door_state` topic。
- 保护边界：门未关不允许牵引。

### 13.15 parking brake 算法

- 输入：`parking_apply`、`parking_release`、速度、emergency 状态。
- 核心判断：施加后保持停放制动；释放需低速/停止且非 emergency。
- 输出：`parking_brake` 状态和制动覆盖。
- 保护边界：施加时牵引清零。

### 13.16 curve_point 曲线输出算法

- 输入：本周期 Train 状态、ATO 输出、MA、停车点、级位、brake_bias。
- 核心判断：每 tick 构建一个轻量点，历史默认保留 300 点。
- 输出：`train_state.curve_point`。
- 保护边界：不新增 topic，不输出完整长历史，避免消息过大。

### 13.17 一车一进程消息过滤算法

- 输入：`owned_vehicle_id` 和消息中的 `vehicle_id` / `train_index`。
- 核心判断：严格过滤 `driver_input`、`ato_command`、`ma_state`、`set_train_state`、`enable_fallback_ato`；`comm_state`、`power_state`、`track_info` 无 `vehicle_id` 时按广播处理。
- 输出：只更新本进程 Train。
- 保护边界：`add_train` 不创建其他车；`reset_trains` 不恢复默认 10 辆；`clear_trains` 在单车进程下忽略。

## 14. ZMQ 通信 payload 示例

### 14.1 driver_input 输入

```json
{
  "topic": "driver_input",
  "timestamp": 1234567890.123,
  "data": {
    "vehicle_id": "TRAIN-001",
    "direction": "forward",
    "main_handle_raw": 1,
    "traction_level": 2,
    "brake_level": 0,
    "traction_percent": 50,
    "brake_percent": 0,
    "control_mode": "manual",
    "ato_capable": true,
    "ato_active": false,
    "ato_start_btn": false,
    "emergency_button": false,
    "emergency_cmd": false,
    "parking_apply": false,
    "parking_release": false,
    "key_switch": true,
    "door_closed_light": true,
    "network_fault_light": false,
    "open_left_door": false,
    "open_right_door": false,
    "close_left_door": false,
    "close_right_door": false,
    "door_mode": "manual"
  }
}
```

进入 Train 后：

- `control_mode` 映射 `driving_mode`；
- 手柄和百分比映射牵引/制动；
- door / parking / emergency 等离散输入进入缓存；
- 不直接积分位置速度。

### 14.2 comm_state 输入

```json
{
  "topic": "comm_state",
  "timestamp": 1234567890.123,
  "data": {
    "source": "driver_tcp",
    "driver_console_connected": true,
    "zmq_connected": true,
    "last_message_at": 1234567890.1
  }
}
```

`driver_console_connected && zmq_connected` 写入 `comm_ok`。通信中断或超时会进入 ATO 降级和 ATP emergency 监督。

### 14.3 ma_state 输入

单车版：

```json
{
  "topic": "ma_state",
  "timestamp": 1234567890.123,
  "data": {
    "vehicle_id": "TRAIN-001",
    "ma_limit": 1500.0,
    "allowed_speed_kmh": 60.0,
    "eb_trigger_speed_kmh": 68.0,
    "target_distance_m": 500.0,
    "permission": "allow",
    "signal_state": "green",
    "reason": "route_open"
  }
}
```

批量版：

```json
{
  "topic": "ma_state",
  "timestamp": 1234567890.123,
  "data": {
    "ma_limits": [
      {
        "vehicle_id": "TRAIN-001",
        "ma_limit": 1500.0,
        "allowed_speed_kmh": 60.0
      },
      {
        "vehicle_id": "TRAIN-002",
        "ma_limit": 1800.0,
        "allowed_speed_kmh": 45.0
      }
    ]
  }
}
```

一车一进程只处理本车 `vehicle_id`。`allowed_speed_kmh`、`eb_trigger_speed_kmh`、`permission`、`signal_state` 同时影响 ATO 和 ATP。

### 14.4 power_state 输入

```json
{
  "topic": "power_state",
  "timestamp": 1234567890.123,
  "data": {
    "substation_id": "SS-01",
    "voltage": 1500.0,
    "current": 100.0,
    "power": 150000.0,
    "is_fault": false
  }
}
```

`is_fault` 或电压低于阈值会置 `power_fault`；`power_factor` 在故障时为 0，影响牵引可用性，并可触发 ATP emergency。

### 14.5 train_state 输出

见第 5 节示例。最小视景字段为：

```json
{
  "vehicle_id": "TRAIN-001",
  "line_id": "LINE-1",
  "position_m": 123.4,
  "speed_mps": 5.6,
  "direction": 1
}
```

完整状态还包含 AM/SM、ATO、ATP、门、停车结果、brake_bias、curve_point 等字段。

### 14.6 ato_state 输出

`main_integrated.py` 每周期调用 `train.build_ato_state()` 并发布：

```json
{
  "type": "ato_state",
  "timestamp": 1234567890.123,
  "vehicle_id": "TRAIN-001",
  "driving_mode": "AM",
  "ato_active": true,
  "ato_capable": true,
  "ato_state": "braking_to_stop",
  "recommended_speed_kmh": 30.0,
  "ato_target_speed_kmh": 30.0,
  "ato_traction_level": 0,
  "ato_brake_level": 1,
  "ato_brake_bias": 1.0,
  "ato_brake_bias_enabled": true,
  "stop_target_m": 300.0,
  "distance_to_stop_m": 50.0,
  "auto_reverse_cap": false,
  "auto_reverse_active": false
}
```

### 14.7 atp_state 输出

```json
{
  "type": "atp_state",
  "timestamp": 1234567890.123,
  "vehicle_id": "TRAIN-001",
  "intervened": false,
  "emergency_brake": false,
  "supervision_state": "normal",
  "reason": "normal",
  "allowed_speed_kmh": 60.0,
  "eb_trigger_speed_kmh": 68.0
}
```

### 14.8 door_state 输出

```json
{
  "type": "door_state",
  "timestamp": 1234567890.123,
  "vehicle_id": "TRAIN-001",
  "door_state": "closed",
  "left_door_open": false,
  "right_door_open": false,
  "doors_all_closed": true,
  "door_mode": "manual"
}
```

### 14.9 司机台 send_to_plc 回传字段来源

| send_to_plc 参数      | 当前来源建议                             |
| --------------------- | ---------------------------------------- |
| `vehicle_speed_kmh`   | `train_state.vehicle_speed_kmh`          |
| `high_voltage_on`     | `train_state.high_voltage_on`            |
| `brake_bad_light`     | `train_state.brake_bad_light`            |
| `door_open_light`     | `train_state.door_open_light`            |
| `door_closed_light`   | `train_state.door_closed_light`          |
| `network_fault`       | 通信模块根据 `comm_state` / 连接状态生成 |
| `ato_capable`         | `train_state.ato_capable`                |
| `ato_active`          | `train_state.ato_active`                 |
| `auto_reverse_cap`    | `train_state.auto_reverse_cap`           |
| `auto_reverse_active` | `train_state.auto_reverse_active`        |

## 15. 旧 ATO / fallback 代码核查结论

全局搜索结果说明：

| 代码 / 入口                                     | 当前引用                                                             | 结论                                                         |
| ----------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------ |
| `backend/app/services/signal_ato_controller.py` | `signal_zmq_adapter.py` 引用；信号侧测试引用；仍发布 `ato_command`。 | legacy 外部 ATO / 信号侧建议链路，不是车辆主控制链路。保留。 |
| `Train.step_ato()`                              | `message_router.py`、`main_ato_local.py`、多个车辆测试调用。         | 兼容外部 `ato_command`，只缓存不积分。保留。                 |
| `ato_command` topic                             | API、data_flow、signal_zmq_adapter、vehicle_sim router 均支持。      | 兼容 topic，不删除。                                         |
| `fallback_ato.py`                               | `enable_fallback_ato`、场景文件和 `test_fallback_ato.py` 使用。      | demo / fallback 兼容模式，不是主链路。保留。                 |
| `main_ato_local.py`                             | 本地 demo 调用 `step_ato()`。                                        | demo 入口。可后续归档但本次不删。                            |
| `main_integrated.py`                            | 主入口，一车一进程，周期调用 Train 内部 ATO。                        | 当前主链路。                                                 |

当前主链路是：

```text
driver_input / ma_state / comm_state / power_state
        -> MessageRouter(vehicle_id 过滤)
        -> Train 缓存
        -> Train.step_tick(dt)
        -> TrainAtoController
        -> Train 约束
        -> ATP
        -> dynamics
        -> train_state / ato_state / atp_state / door_state
```
