# 车辆仿真模块开发记录 - 2026-07-08

## 一、今天开发范围

今天只开发车辆与轨道这一侧的功能，主要包括：

- 协议数据模型
- 单车状态对象
- 轨道信息查询
- 牵引 / 制动映射
- 动力学 step 更新
- `train_state` 状态输出
- ATP 紧急制动
- ATO 指令执行
- 本地多车运行
- ZMQ 发布模块雏形

没有做这些内容：

- 没有写复杂 PID / AI 控制算法
- 没有接真实 UDP
- 没有做一车一进程的正式运行模式
- 没有做后端 `dashboard_snapshot`
- 没有帮其他同学计算道岔、闭塞、MA
- 没有追求厘米级停车精度

当前目标是先把车辆侧最小闭环跑通。

## 二、当前完成进度

步骤里的 9 个功能点已经完成第一版。

| 顺序 | 功能点 | 当前状态 |
| --- | --- | --- |
| 1 | 协议数据模型 | 已完成 |
| 2 | 单车状态对象 | 已完成 |
| 3 | 轨道查询 | 已完成 |
| 4 | 牵引 / 制动映射 | 已完成 |
| 5 | 动力学 step | 已完成 |
| 6 | `train_state` 输出 | 已完成 |
| 7 | ATP 紧急制动 | 已完成 |
| 8 | ATO 指令执行 | 已完成 |
| 9 | 多车支持 + ZMQ | 已完成第一版 |

## 三、今天新增和修改的文件

### 1. `backend/app/vehicle_sim/models.py`

作用：定义车辆侧协议数据模型。

包含的数据结构：

- `TrainState`
- `DriverInput`
- `AtoCommand`
- `MaLimit`
- `PowerState`
- `CommState`
- `TrackSection`

其中 `TrainState.to_protocol()` 用来输出协议规定的 `train_state` JSON。

输出字段包括：

- `type`
- `timestamp`
- `vehicle_id`
- `line_id`
- `position`
- `speed`
- `acceleration`
- `mode`
- `is_running`
- `emergency_brake`

单位约定：

- `position`：米
- 内部 `speed_ms`：米/秒
- 输出 `speed`：千米/小时
- `acceleration`：米/秒²

### 2. `backend/app/vehicle_sim/mock_data.py`

作用：提供本地测试用的轨道数据。

当前 mock 轨道：

- `SEG-01`：0 到 500 米，限速 60 km/h
- `SEG-02`：500 到 1000 米，坡度 8‰，限速 45 km/h
- `SEG-03`：1000 到 1600 米，限速 35 km/h，停车点 1500 米

### 3. `backend/app/vehicle_sim/track_map.py`

作用：根据车辆当前位置查询轨道信息。

提供的方法：

- `get_section(position)`
- `get_gradient(position)`
- `get_speed_limit(position)`
- `get_stop_position(position)`

已验证：

```text
600m  -> 坡度 8.0
1200m -> 限速 35.0
1200m -> 停车点 1500.0
```

### 4. `backend/app/vehicle_sim/dynamics.py`

作用：实现简化版车辆动力学。

已经实现：

- 牵引级位 0 到 4 映射为牵引力
- 制动级位 0 到 4 映射为制动力
- 牵引和制动同时存在时，制动优先
- 速度越高，运行阻力越大
- 支持上坡 / 下坡阻力
- 紧急制动时牵引清零，制动力最大

核心函数：

```python
update_dynamics(...)
```

它每一步更新：

- 速度
- 位置
- 加速度
- 牵引力
- 制动力

### 5. `backend/app/vehicle_sim/train.py`

作用：封装单辆车对象。

`Train` 类负责把输入、轨道查询、ATP 检查、动力学更新、状态输出串起来。

支持的方法：

- `step_manual(driver_input, dt)`
- `step_ato(ato_command, dt)`
- `apply_ma_state(ma_limit)`
- `apply_power_state(power)`
- `apply_comm_state(comm)`

每辆车都有独立状态：

- 车辆 ID
- 线路 ID
- 位置
- 速度
- 加速度
- 当前模式
- 是否紧急制动
- 最近一次 ATP 报警

### 6. `backend/app/vehicle_sim/atp.py`

作用：实现 ATP 紧急制动逻辑。

ATP 会在这些情况下触发紧急制动：

- 当前速度超过轨道区段限速
- 当前位置超过 MA 限制
- 供电故障
- 通信断开

触发后：

- `emergency_brake = True`
- `mode = "emergency"`
- `last_alarm` 保存一条 `alarm_event`

### 7. `backend/app/vehicle_sim/main_local.py`

作用：本地单车手动驾驶测试入口。

运行逻辑：

- 前 50 步：牵引级位 3
- 后 50 步：制动级位 2
- 每步时间：0.1 秒
- 每步输出一条 `train_state` JSON

验证结果：

```text
速度先上升，再下降
0.531 km/h -> 26.462 km/h -> 3.408 km/h
```

### 8. `backend/app/vehicle_sim/main_ato_local.py`

作用：本地 ATO 指令执行测试入口。

运行逻辑：

- 前 50 步：ATO 给牵引级位 3
- 后 50 步：ATO 给制动级位 2
- 输出状态的 `mode` 为 `ato`
- 如果 ATP 触发，会覆盖 ATO，强制进入 `emergency`

验证结果：

```text
ATO 牵引时速度上升
ATO 制动时速度下降
ATP 触发时 mode 从 ato 变成 emergency
```

### 9. `backend/app/vehicle_sim/main_multi_local.py`

作用：本地多车运行测试入口。

当前在一个 Python 进程里维护三辆车：

- `TRAIN-001`
- `TRAIN-002`
- `TRAIN-003`

每辆车都有独立状态，并分别输出 `train_state`。

这是第一阶段的简单多车方案，方便调试。

### 10. `backend/app/vehicle_sim/zmq_publisher.py`

作用：提供 ZMQ 发布模块。

默认地址：

```text
tcp://localhost:5555
```

当前采用 `connect`，假设后端中心服务负责 `bind`。

后面需要和后端同学确认最终到底谁 `bind`，谁 `connect`。

## 四、运行方式

下面命令都在 `backend` 目录下运行。

建议使用项目虚拟环境：

```powershell
..\.venv\Scripts\python.exe
```

### 1. 编译检查

```powershell
..\.venv\Scripts\python.exe -m compileall app\vehicle_sim
```

结果：已通过。

### 2. 单车手动驾驶

```powershell
..\.venv\Scripts\python.exe -m app.vehicle_sim.main_local
```

结果：前 5 秒加速，后 5 秒制动。

### 3. ATO 指令执行

```powershell
..\.venv\Scripts\python.exe -m app.vehicle_sim.main_ato_local
```

结果：ATO 能控制牵引和制动。

### 4. 多车本地运行

```powershell
..\.venv\Scripts\python.exe -m app.vehicle_sim.main_multi_local --steps 100
```

结果：能输出三辆车的 `train_state`。

### 5. 多车 + ZMQ 发布

```powershell
..\.venv\Scripts\python.exe -m app.vehicle_sim.main_multi_local --steps 100 --use-zmq
```

结果：可以向 `tcp://localhost:5555` 发布消息。

## 五、今天验证过的结果

### 单车手动驾驶

```text
第 1 步速度：0.531 km/h
第 50 步速度：26.462 km/h
第 100 步速度：3.408 km/h
```

说明车辆能先加速，再制动减速。

### 轨道查询

```text
get_gradient(600) = 8.0
get_speed_limit(1200) = 35.0
get_stop_position(1200) = 1500.0
```

说明轨道区段查询正常。

### ATP 紧急制动

已验证四种触发情况：

```text
超速 -> emergency
超过 MA 限制 -> emergency
供电故障 -> emergency
通信断开 -> emergency
```

### ATO 指令执行

已验证：

```text
ATO 给牵引级位 -> 车辆加速
ATO 给制动级位 -> 车辆减速
ATP 触发 -> 覆盖 ATO，进入 emergency
```

### 多车运行

已验证输出包含：

```text
TRAIN-001
TRAIN-002
TRAIN-003
```

说明多个 `Train` 对象可以在本地独立运行。

### ZMQ

项目虚拟环境里有：

```text
pyzmq==26.0.3
```

使用虚拟环境运行时，ZMQ publisher 可以正常创建并发送消息。

## 六、注意事项

1. 系统 Python 里不一定有 `zmq`，所以运行 ZMQ 相关功能时要用项目 `.venv`。
2. 当前多车是一个进程里维护多个 `Train` 对象，不是一车一进程。
3. 当前 ATO 只是执行外部传来的牵引 / 制动级位，不负责计算目标速度曲线。
4. 当前 ATP 是第一版规则判断，还没有做复杂限速曲线。
5. ZMQ 默认使用 `connect("tcp://localhost:5555")`，需要和后端确认中心端是否负责 `bind`。

## 七、下一步建议

1. 和后端同学确认 ZMQ 的 `bind/connect` 关系。
2. 把现在的手动测试整理成自动测试文件，方便以后改代码时快速确认没坏。
3. 如果后面需要正式多车运行，再增加 `main_train_process.py`，实现一辆车一个进程。
4. 后续对接 B 同学的 ATO 时，只需要把收到的 `ato_command` 转成当前 `AtoCommand` 数据结构，再调用 `train.step_ato(...)`。
