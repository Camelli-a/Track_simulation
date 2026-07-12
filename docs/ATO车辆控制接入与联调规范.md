# ATO 车辆控制接入与联调规范

> 状态：第一版开发基线  
> 用途：作为车载 ATO、车辆动力学、ATP、信号/MA、停车目标与状态发布之间的单一事实来源。  
> 适用范围：`TrainAtoController` 纯算法开发、单元测试，以及后续接入 `Train.step_tick(dt)` 的联调阶段。

## 1. 总体原则

1. 每个 `Train` 实例拥有独立的 `TrainAtoController`，不得在多车之间共享 PID、停车阶段或事件锁存状态。
2. ATO 只计算目标速度、推荐速度及 `0~4` 的牵引/制动建议级位，不直接计算或写入实际牵引力、制动力、速度和位置。
3. 实际力由车辆动力学依据当前速度、52 点单电机转矩曲线、传动比、轮半径、电机数量、运行阻力和坡度阻力计算。
4. `Train.step_tick(dt)` 是唯一动力学周期入口；每个 tick 只允许执行一次动力学积分。
5. ATP 始终具有最高安全优先级，在动力学执行前覆盖不安全命令。
6. `driving_mode` 表示驾驶模式选择，`mode` 表示当前实际控制来源，两者不得混用。
7. MA 必须经过字段合法性和数据时效性检查；AM 下无有效 MA 时禁止牵引并进入失效保护。
8. 停车目标统一使用线路绝对里程，单位为 m，并与列车位置、MA 终点使用相同坐标系和参考点。
9. 状态输出必须区分 ATO 建议、模式选择后的命令和 ATP 裁决后的实际施加命令。

## 2. 第一阶段开发边界

同学 3 第一阶段负责：

- 新增 `TrainAtoController` 纯算法文件；
- 定义清晰、可测试的输入输出数据结构；
- 编写 AM、SM、停车控制、失效保护与边界场景单元测试；
- 第一版实现停车曲线、低速蠕行、AM 自动停车、SM 推荐速度和停车误差判断。

第一阶段不得：

- 修改 `dynamics.py` 或 `atp.py`；
- 调用 `update_dynamics()` 或 `Train._step()`；
- 修改 `Train` 的速度、位置或 ATP 状态；
- 发布消息或直接读取信号服务、站台服务内部对象；
- 在多个入口执行动力学积分。

纯算法稳定后，再共同接入 `Train.step_tick(dt)`。

## 3. 新车辆动力学契约

### 3.1 基础参数

当前车辆模型采用：

| 参数 | 数值 | 单位/说明 |
|---|---:|---|
| 列车质量 | 225000 | kg |
| 编组 | Tc-M-M-M-M-Tc | 6 辆 |
| 列车长度 | 118.0 | m |
| 轮半径 | 0.46 | m |
| 牵引电机数 | 16 | 台 |
| 传动比 | 7.8 | 工程反推值，待权威参数确认 |
| 轴数 | 24 | 根 |
| 迎风面积 | 10.6 | m² |

传动比 7.8 将 52 点曲线端点 `4160.1 rpm` 映射为约 `92.6 km/h`，相对 `80 km/h` 运营速度保留约 15% 余量。

### 3.2 52 点曲线语义

- 横轴：单台牵引电机转速，单位 rpm；
- 纵轴：单台电机转矩，单位 N·m；
- 牵引和制动各使用一组 52 点曲线；
- 点间使用线性插值，超出曲线范围时采用端点钳制；
- 实际全列车轮周力由 16 台电机合成。

换算关系：

```python
motor_rpm = speed_ms / (2 * pi * wheel_radius_m) * 60 * gear_ratio
wheel_force_n = motor_torque_nm * gear_ratio / wheel_radius_m * motor_count
```

### 3.3 运行阻力与坡度

戴维斯阻力公式的速度使用 km/h：

```python
speed_kmh = speed_ms * 3.6
running_resistance_n = (
    6.4 * 225
    + 130 * 24
    + 0.14 * 225 * speed_kmh
    + (0.046 + 0.0065 * (6 - 1)) * 10.6 * speed_kmh**2
)
```

坡度阻力：

```python
gradient_resistance_n = 225000 * 9.80665 * gradient_permille / 1000
```

正坡度表示上坡，负坡度表示下坡。ATO 不得继续使用旧的 40 t 质量、固定牵引力、固定制动力或旧阻力公式。

### 3.4 ATO 可使用的只读性能查询

ATO 计算停车曲线时可以调用无副作用的只读函数：

```python
calc_traction_force(level, speed_ms, power_factor)
calc_brake_force(level, speed_ms)
calc_running_resistance(speed_ms)
calc_gradient_resistance(gradient_permille)
```

ATO 不得调用 `update_dynamics()`，也不得复制一套与车辆模块不同的动力学公式。

### 3.5 已知制动限制

当前官方 52 点制动曲线在零转速附近的电机制动转矩为零。因此：

- `brake_level=4` 不等于零速时一定具有保持力；
- 当前模型尚未完整表示低速空气制动、保持制动和停车制动；
- 下坡停车保持不能仅依靠现有电制动曲线保证；
- 第一版 ATO 可输出停车保持制动建议，但必须将该问题记录为车辆模型已知限制；
- 后续由车辆模块补充电空混合制动或独立保持制动模型，ATO 不得自行虚构固定制动力。

## 4. 牵引与制动级位

### 4.1 级位范围

牵引和制动统一使用整数级位 `0~4`：

| 级位 | 名义比例 | 含义 |
|---:|---:|---|
| 0 | 0% | 不施加 |
| 1 | 25% | 一级牵引/制动 |
| 2 | 50% | 二级牵引/制动 |
| 3 | 75% | 三级牵引/制动 |
| 4 | 100% | 四级牵引/制动 |

名义比例作用于“当前速度下通过 52 点曲线插值得到的全级位能力”，不是全速度范围内的固定最大力：

```python
actual_traction_force = lookup_traction_force(speed_ms) * traction_percent / 100
actual_brake_force = lookup_brake_force(speed_ms) * brake_percent / 100
```

### 4.2 互斥与制动优先

ATO 输出必须整数化、限幅并满足牵引/制动互斥：

```python
traction_level = max(0, min(4, int(traction_level)))
brake_level = max(0, min(4, int(brake_level)))

if brake_level > 0:
    traction_level = 0
```

任何模块检测到牵引与制动同时大于 0 时，统一执行制动优先。

## 5. 驾驶模式与控制来源

### 5.1 字段定义

`driving_mode` 表示司机选择的驾驶模式：

- `AM`：Automatic Mode；
- `SM`：Supervised Manual Mode。

`mode` 表示当前周期实际生效的控制来源：

- `manual`：司机输入生效；
- `ato`：ATO 输出生效；
- `emergency`：紧急控制或 ATP 紧急覆盖生效。

正常映射：

| driving_mode | mode | 生效命令 |
|---|---|---|
| AM | ato | ATO 输出 |
| SM | manual | 司机输入 |

紧急状态允许：

```text
driving_mode = AM 或 SM
mode = emergency
```

紧急状态不得反向修改 `driving_mode`。紧急状态解除后是否恢复原驾驶模式，必须通过明确的复位和安全检查，不得自动恢复牵引。

### 5.2 模式输入

驾驶模式由司机台/PLC 状态经适配器进入车辆模块：

```text
ato_start_btn -> Train ATO 状态机检查 -> driving_mode
```

- 未收到合法模式时默认 `SM`；
- 模式切换在 tick 边界生效；
- AM 切换至 SM 后使用最新缓存司机命令；
- SM 切换至 AM 时，如 MA 或停车目标不满足控制条件，ATO 进入 `degraded` 且不得直接牵引。

### 5.3 SM 行为

SM 下 ATO 仍计算：

- `recommended_speed_kmh`；
- `ato_target_speed_kmh`；
- ATO 建议级位和状态。

但 ATO 不得覆盖司机输入，也不得将 `mode` 改为 `ato`。ATP 仍可覆盖司机命令。

## 6. 唯一周期入口与控制链

### 6.1 输入缓存

以下输入只允许缓存，不执行动力学积分：

- `driver_input`；
- `ma_state`；
- `stop_target`；
- 兼容保留的 `step_manual()` 与 `step_ato()`。

推荐后续将兼容入口改名为：

```python
set_manual_command(...)
set_ato_command(...)
```

### 6.2 每周期执行顺序

`Train.step_tick(dt)` 是唯一周期调度入口；每个 tick 内只允许调用一次：

```python
_step(traction_level, brake_level, dt)
```

固定流程：

```text
1. 读取缓存的司机输入、驾驶模式、MA、停车目标和更新时间
2. 检查输入合法性与时效性
3. ATO 计算目标速度、推荐速度和建议级位
4. AM 采用 ATO 命令，SM 采用司机命令
5. 级位整数化、限幅并执行制动优先
6. ATP 进行最高优先级监督与覆盖
7. 调用一次 _step(...) 执行动力学积分
8. 更新并发布 train_state
9. 满足唯一触发条件时发布 stop_result
```

任何其他方法不得在同一周期内再次修改速度或位置。

### 6.3 控制优先级

```text
人工紧急制动 / ATP 紧急覆盖
              ↓
AM 的 ATO 命令 或 SM 的司机命令
              ↓
车辆动力学执行
```

旧地面 `ato_command`、`fallback_ato` 与新车载 ATO 不得同时获得控制权。兼容链路必须有显式开关和唯一控制源。

## 7. MA 接口与失效保护

### 7.1 沿用字段

第一版使用现有字段：

- `Train.ma_limit`：MA 绝对终点，m；
- `allowed_speed_kmh`：安全允许速度，km/h；
- `target_distance_m`：距 MA 终点的距离，m；
- `permission`；
- `signal_state`。

建议增加：

```python
ma_updated_at
ma_valid
```

### 7.2 字段合法性

以下情况使 MA 无效或不可用于继续牵引：

- `ma_limit` 和 `target_distance_m` 均缺失；
- 关键数值为 NaN、无穷大或语义非法；
- `allowed_speed_kmh` 缺失、非有限数值或小于 0；
- `permission` 明确禁止继续运行；
- `signal_state` 与许可或限速发生安全冲突；
- 数据来源状态异常或通信失效。

`target_distance_m` 缺失时，只要 `ma_limit` 有效，允许推导：

```python
calculated_distance_to_ma_m = ma_limit - position_m
```

两种距离同时存在时进行一致性检查，并采用更保守的非负结果。

### 7.3 数据时效性

- MA 输入必须保存消息时间戳或接收更新时间；
- 超过配置有效期的 MA 视为过期；
- 不得仅因旧值仍保存在 `Train` 中就继续牵引；
- 超时时间由车辆/ATP通信策略统一配置，不在 ATO 内硬编码多份。

### 7.4 AM 失效保护

AM 下 MA 无效时：

- 牵引级位必须为 0；
- `ato_state=degraded`；
- 已停车时输出停车保持请求，但遵守低速制动已知限制；
- 运行中执行配置的安全制动策略，不得长期仅靠惰行；
- ATP 继续执行最终安全兜底。

ATO 目标速度始终满足：

```python
ato_target_speed_kmh <= allowed_speed_kmh
```

## 8. 停车目标

### 8.1 数据来源

第一版优先使用：

```python
Train.next_stop_target_m
```

不存在时使用 `TrackMap.get_stop_position()` 作为本地 fallback。

正式版由老师站台表生成的 `STOP_TARGETS` 通过共享配置、adapter 或明确的数据服务接口注入车辆。车辆模块不得长期直接 import 信号服务。

### 8.2 坐标和参考点

`next_stop_target_m` 表示线路绝对里程，单位 m，不表示相对剩余距离。

停车目标、`Train` 位置与 MA 终点必须使用：

- 相同线路坐标系；
- 相同里程方向；
- 相同列车参考点。

项目正式联调前必须确认 `position_m` 表示车头、列车中心还是其他测量参考点；停车误差使用同一参考点计算。

正向运行：

```python
distance_to_stop_m = stop_target_m - position_m
```

反向运行必须结合 `direction_code` 计算带符号距离，不得直接套用正向公式。

### 8.3 边界情况

必须处理：

- 停车目标不存在；
- 目标位于列车后方；
- 已越过停车点；
- 运行方向改变；
- TrackMap 无 fallback；
- 目标在周期中切换。

状态中使用：

```text
stop_target_source = injected / train / track_map / none
```

停车目标与 MA 终点必须分开建模：前者是运营目标，后者是安全授权边界。

## 9. TrainAtoController 接口

### 9.1 推荐输入

```python
output = controller.compute(
    dt=dt,
    speed_ms=speed_ms,
    position_m=position_m,
    gradient_permille=gradient_permille,
    driving_mode=driving_mode,
    ma_state=ma_state,
    stop_target_m=stop_target_m,
)
```

`ma_state` 建议使用只读数据结构，至少包含：

```text
ma_limit_m
allowed_speed_kmh
target_distance_m
permission
signal_state
updated_at
valid
```

### 9.2 推荐输出

```python
{
    "ato_state": "running",
    "ato_target_speed_kmh": 40.0,
    "recommended_speed_kmh": 40.0,
    "traction_level": 2,
    "brake_level": 0,
    "distance_to_stop_m": 320.0,
    "degraded_reason": None,
}
```

控制器不得在 `compute()` 内修改 `Train`、ATP、动力学或消息总线。

## 10. ATO 状态

第一版统一使用：

- `inactive`：未参与计算或尚未初始化；
- `ready`：输入有效，等待运行；
- `running`：正常速度控制；
- `approaching_stop`：执行停车控制；
- `creeping`：低速蠕行；
- `stopped`：已在目标附近停稳；
- `degraded`：关键输入无效，执行失效保护；
- `fault`：控制器内部异常。

枚举一经实现，代码、测试、协议和前端必须保持一致。

## 11. train_state 输出

### 11.1 ATO 与目标字段

第一版增加：

```text
driving_mode
ato_state
recommended_speed_kmh
ato_target_speed_kmh
ato_traction_level
ato_brake_level
stop_target_m
distance_to_stop_m
stop_target_source
```

即使 `recommended_speed_kmh` 与 `ato_target_speed_kmh` 第一版数值相同，也必须保持语义独立。

### 11.2 命令分层

状态必须区分：

```text
ato_traction_level / ato_brake_level
    ATO 算法建议

commanded_traction_level / commanded_brake_level
    AM/SM 模式选择后、ATP 裁决前的命令

applied_traction_level / applied_brake_level
    ATP 裁决后实际交给动力学的命令
```

同时增加：

```text
control_source = manual / ato / atp / emergency_button / fallback / none
atp_intervened
```

`_step()` 接入时必须把 ATP 裁决后的最终级位保存或返回，不能用裁决前的值伪装成 `applied_*`。

调试字段较多时再增加低频 `ato_status` topic，第一版不强制。

## 12. stop_result 事件

停车完成使用独立 `stop_result` 事件，不使用持续状态轮询表达一次性结果。

建议字段：

```json
{
  "type": "stop_result",
  "timestamp": 1720000000.123,
  "vehicle_id": "TRAIN-001",
  "stop_target_m": 1500.0,
  "actual_stop_position_m": 1500.32,
  "stop_error_m": 0.32,
  "result": "success"
}
```

如需仿真时间，另加 `simulation_time_s`，不得混用系统时间与仿真时间。

`result` 至少包括：

- `success`；
- `undershoot`；
- `overshoot`；
- `invalid_target`。

事件触发条件：

1. 速度低于配置停车阈值；
2. 已进入停车结果判定；
3. 状态首次从进站控制转换为停稳结果；
4. 当前停车目标尚未发布过结果。

同一停车目标只允许发布一次；更换目标后才重置事件锁存。

## 13. 最低单元测试清单

### 13.1 级位与动力学边界

- 输出始终为 `0~4` 整数；
- 牵引和制动互斥，冲突时制动优先；
- ATO 不直接修改速度和位置；
- ATO 不调用动力学积分；
- 高速牵引能力下降时算法行为稳定；
- 低速电制动力下降被正确识别；
- 上坡、平坡、下坡停车曲线行为符合预期。

### 13.2 驾驶模式

- AM 使用 ATO 命令；
- SM 使用司机命令；
- SM 仍计算推荐速度；
- SM 不把 `mode` 改为 `ato`；
- AM/SM 均可被紧急控制或 ATP 覆盖；
- 紧急解除后不会无条件恢复牵引。

### 13.3 MA 与失效保护

- MA 正常、缺失、非法和超时；
- `allowed_speed_kmh` 缺失、负数、NaN、无穷大；
- `target_distance_m` 缺失但可由 `ma_limit-position_m` 推导；
- 两种 MA 距离不一致时采用更保守值；
- `permission` 禁止或与 `signal_state` 冲突；
- 降级后牵引为 0；
- 运行中采用预期安全制动策略。

### 13.4 停车控制

- 正常接近、蠕行和停稳；
- 停车目标不存在及 TrackMap fallback；
- 越过、欠停、过停和目标切换；
- 反向运行；
- 不同列车的控制器状态互不影响；
- `stop_result` 对同一目标只发布一次。

### 13.5 周期与状态

- 一个 tick 只调用一次 `_step(...)`；
- `step_manual()`/`step_ato()` 不执行积分；
- ATO 建议、模式选择命令和 ATP 后实际命令正确区分；
- `control_source` 与 `atp_intervened` 正确；
- 状态字段单位和枚举符合本文档。

## 14. 联调验收标准

纯算法满足以下条件后方可接入车辆：

1. 每车独立控制器，无跨车共享状态；
2. 控制器无外部副作用；
3. 级位合法、互斥且制动优先；
4. AM、SM、emergency 语义明确；
5. MA 缺失、非法、超时和冲突均有确定行为；
6. 停车目标坐标、方向和参考点语义统一；
7. 停车曲线与新 52 点动力学、戴维斯阻力和坡度方向一致；
8. `step_tick(dt)` 是唯一积分入口；
9. 状态能够解释 ATO 建议、模式选择、ATP 干预和实际动力学输入；
10. 单元测试覆盖正常、边界和失效场景。

## 15. 变更管理

### 15.1 `driver_input` 控制契约（2026-07-12）

- 手动驾驶牵引显示级位为 `0..4`，常用制动显示级位为 `0..7`；ATO 输出仍统一为牵引/制动 `0..4`。
- 动力学唯一主控制量是 `traction_percent` / `brake_percent`（`0..100`）。级位仅用于显示、日志和兼容输入，不得与百分比重复叠加成力。
- 手动制动级位换算为 `brake_percent = brake_level / 7 * 100`；ATO 制动级位换算为 `brake_percent = brake_level / 4 * 100`。
- 牵引与制动互斥且制动优先。`main_handle_raw=4` 固定表示 100% 快速/最大常用制动，即 `brake_level=7`，不等同于 ATP 紧急制动。
- `key_switch=false` 或方向为中立位时禁止牵引；反向运行仍使用线路绝对里程，位置沿减小方向推进。
- `emergency_button` 是持续安全输入；为真期间必须保持紧急制动。`forced_release` 只是请求，不得直接清除紧急制动。
- `ato_start_btn` 是司机请求，`Train` 内 ATO 状态机是 `ato_active` 的权威来源。PLC 上报的 `ato_active` 仅作为硬件显示回读，不得直接切换 `driving_mode`。
- `parking_apply` 可锁存停放制动；仅在列车停止且无紧急制动时接受 `parking_release`。
- `brake_bad_light`、`network_fault_light` 仅作硬件回读诊断，不能成为制动命令，`network_fault_light` 也不能替代 `comm_state`。

当前车辆消息入口已经支持上述字段。实体司机台二进制解析器仍须依据通信组确认的 PLC 字节偏移生成 `driver_input`；禁止在没有权威偏移表时猜测字段位置。

### 15.2 车门仿真与牵引联锁

- `open_left_door`、`open_right_door`、`close_left_door`、`close_right_door` 均为操作请求，每个周期消费一次。
- `Train.door_state` 是车门物理状态的权威来源；司机台输入的 `door_closed_light` 仅为硬件指示灯回读。
- 列车速度不大于 0.05m/s 且绝对里程进入停车点 ±0.5m 窗口时，自动开门并保持 5 秒，然后自动关闭。
- `door_mode=left/right/both` 指定开门侧；线路尚无站台侧数据时，`auto` 默认开左门。
- 同一停车点完成一次开关后不会在原地反复开门；离开该点 2m 后重新允许触发。
- 任一侧车门未完全关闭，最终实际牵引百分比强制为 0；制动和 ATP 紧急干预不受车门联锁阻断。
- `train_state` 发布 `door_state`、左右门状态、`doors_all_closed`、`door_mode` 和由物理状态生成的 `door_closed_light`。

### 15.3 指示灯单向显示契约

- `driver_input` 中的 `high_voltage_light`、`brake_bad_light`、`door_closed_light`、`network_fault_light` 全部是 PLC 回读，不是业务状态输入。
- 回读分别保存到 `hardware_high_voltage_light`、`hardware_brake_bad_light`、`hardware_door_closed_light`、`hardware_network_fault_light`。
- 系统输出灯态只能由 `PowerState`、制动故障业务状态、物理 `DoorState` 和 `CommState` 生成。
- PLC 回读不得修改 `power_fault`、`power_factor`、`brake_fault`、车门物理状态、`comm_ok` 或 ATP 判定。
- `get_indicator_feedback_mismatches()` 可以检查灯命令是否在硬件上真实点亮，但诊断结果不进入车辆控制闭环。
- `network_fault` 及其输出灯命令归通信模块所有；车辆只保留 PLC 的 `hardware_network_fault_light` 回读，不在 `train_state` 中生成网络故障字段。

### 15.4 通信时效与瞬时按钮

- 车辆订阅 `comm_state`，ATP 同时使用连接状态和 `last_message_at`，不能只判断 `driver_console_connected`。
- 当前可配置阈值为 0.3 秒告警、0.5 秒紧急制动；100ms PLC 帧在多个 20ms 动力学周期中复用属于正常行为。
- 瞬时按钮统一在 `Train.step_manual()` 输入边界做上升沿检测，事件只保留到下一个 `step_tick()`。
- `ato_start_btn`、强迫缓解/泵风、停放制动施加/缓解、鸣笛、车门按钮、模式确认、确认按钮、自动折返触发、牵引辅助复位和警惕按钮均属于瞬时事件。
- 钥匙、方向、紧急按钮、洗车模式、ATO 回读状态和车门模式属于持续状态，不做边沿检测。
- 支持可选 `frame_seq` / `message_id` 整帧去重，防止同一通信帧被重复投递。

### 15.5 `train_state` 单位与输出所有权

- 车辆内部及规范输出使用 `position_m`、`speed_mps`、`acceleration_mps2`，速度表使用额外的 `speed_kmh` / `vehicle_speed_kmh`。
- 输出必须区分请求与最终实际施加值，并提供最终牵引/制动级位、百分比及牛顿力。
- 输出 ATP 干预、ATO 能力/激活状态、推荐速度、自动折返、物理车门、停放制动和供电灯状态。
- 旧 `position`、`speed`、`acceleration`、`mode` 暂时兼容保留；不得在 `Train` 中生成 cm、cm/s 或小端二进制数据。
- `network_fault` 不属于车辆状态，由通信模块自行生成。

### 15.6 PLC 单一发送权与 ZMQ 信封

- `vehicle_sim` 只发布状态，不得导入 `DriverDeskSource` 或直接调用 `send_to_plc()`。
- 通信层 `PlcFeedbackAggregator` 订阅并缓存车辆、ATO、车门和通信状态，每 100ms 仅发送一次完整 PLC 快照，避免局部调用的默认值覆盖其他模块状态。
- 当前 ZMQ 线格式为单帧 `<topic> <json-envelope>`，不是纯 `send_json`，也不是 multipart；topic 前缀支持原生 SUB 过滤。
- 接收端校验帧前缀和 JSON `topic` 一致，并在边界解包 `data`；车辆路由仍兼容旧扁平 `type` 消息。
- 真实 PLC 上行 28 字节序列化归通信模块，必须等待正式字段偏移与校验定义，不得在车辆模块猜测实现。

### 15.7 多车隔离与完整车辆输入

- 实体司机台输入必须显式携带 `vehicle_id=TRAIN-001`；不得按 `train_index` 猜测，更不得广播给所有列车。
- `TRAIN-002..N` 使用虚拟司机台或各自车载 ATO，并继续严格按 `vehicle_id` 路由。
- 车辆除司机台外还订阅 `ma_state`、`speed_constraint`、`signal_state/interlocking_state`、`track_info`、`power_state`、`comm_state`、`fault_event`。
- 临时限速与 MA 限速取严格值进入 ATP；红灯或禁止许可阻止运行；车辆故障默认只影响目标车，只有显式系统 scope 才能广播。
- 完整输出链为 `train_state`、`ato_state`、`atp_state`、`door_state`、`alarm_event`。

以下内容发生变化时，必须先更新本文档并由相关模块负责人共同确认：

- 级位范围或含义；
- 52 点曲线、传动比、车辆质量或制动模型；
- `mode` / `driving_mode` 枚举；
- 控制优先级；
- MA 字段、合法性与时效规则；
- 停车目标坐标和列车参考点；
- `train_state` / `stop_result` 字段；
- 动力学积分入口；
- ATP 与 ATO 的职责边界。

禁止仅依据临时口头约定改变接口。代码、自动化测试、前端适配和本文档必须同步更新。
