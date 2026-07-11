# 后端数据流转 ZMQ 动态加车联调测试报告

测试日期：2026-07-09  
测试分支：`zyl`  
相关合并提交：`04c4e58 Merge remote-tracking branch 'origin/feature/vehicle-track' into zyl`

## 1. 测试目的

本次测试主要验证后端数据流转模块在 `DATA_SOURCE=zmq` 模式下，能否完成动态加车以及和子模块之间的数据联通。

重点验证链路如下：

1. 后端通过车辆管理接口发起动态加车。
2. 后端将加车指令发布到 ZMQ 总线。
3. 车辆算法模块从 ZMQ 接收到加车指令，并在算法侧新增车辆。
4. 车辆算法模块持续向 ZMQ 发布真实/算法侧车辆状态 `train_state`。
5. 信号模块从 ZMQ 接收车辆状态，计算 MA / 移动授权结果。
6. 信号模块将 `ma_state` 发布回 ZMQ。
7. 后端数据流转模块接收 `train_state` 和 `ma_state`，汇总到 dashboard 快照，供前端展示。

本次测试没有启动 mock 数据发布器，测试数据来自车辆算法模块和信号模块的 ZMQ 输出。

## 2. 测试环境

后端配置文件 `.env` 中数据源模式为：

```env
DATA_SOURCE=zmq
ZMQ_BROKER_FRONTEND=tcp://127.0.0.1:5555
ZMQ_BROKER_BACKEND=tcp://127.0.0.1:5556
```

测试启动的服务：

```powershell
# ZMQ broker
.\.venv\Scripts\python.exe -m app.communication.broker

# 后端 API 服务
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000

# 信号模块 ZMQ worker
.\.venv\Scripts\python.exe -m app.communication.signal_worker

# 车辆算法集成进程
.\.venv\Scripts\python.exe -m app.vehicle_sim.main_integrated --dt 0.2
```

未启动：

```powershell
.\.venv\Scripts\python.exe -m app.communication.mock_publisher
```

因此本次联调不是 dashboard mock 数据测试。

## 3. 测试前状态

车辆算法模块启动后，会维护自己的车辆列表，并持续发布 `train_state`。

测试前从后端 dashboard 快照观察到：

```json
{
  "source": "zmq",
  "count": 10,
  "ids": [
    "TRAIN-001",
    "TRAIN-002",
    "TRAIN-003",
    "TRAIN-004",
    "TRAIN-005",
    "TRAIN-006",
    "TRAIN-007",
    "TRAIN-008",
    "TRAIN-009",
    "TRAIN-010"
  ],
  "ma_count": 10
}
```

说明动态加车前，车辆算法模块已经通过 ZMQ 上报了 10 辆车，信号模块也已经为这 10 辆车计算并发布了 MA 结果。

## 4. 动态加车测试步骤

调用车辆管理接口新增一辆车：

接口：

```http
POST /api/v1/vehicle/manage
```

请求体：

```json
{
  "type": "add_train",
  "vehicle_id": "TRAIN-011",
  "train_index": 11,
  "line_id": "LINE-1",
  "position": 3050.0
}
```

接口返回：

```json
{
  "accepted": true,
  "ok": true,
  "published": true,
  "topic": "add_train",
  "result": {
    "ok": true,
    "vehicle_id": "TRAIN-011",
    "train_index": 11,
    "position": 3050.0,
    "line_id": "LINE-1"
  }
}
```

这里的关键字段是：

- `ok=true`：后端车辆管理接口接受了加车请求。
- `published=true`：后端已经把 `add_train` 指令发布到 ZMQ 总线。
- `topic=add_train`：车辆算法模块订阅该 topic 后，可以接收动态加车指令。

## 5. ZMQ 子模块联调观察结果

动态加车后等待约 3 秒，再读取后端 dashboard 快照，结果如下：

```json
{
  "source": "zmq",
  "train_count": 11,
  "has_011": true,
  "ids_tail": [
    "TRAIN-007",
    "TRAIN-008",
    "TRAIN-009",
    "TRAIN-010",
    "TRAIN-011"
  ],
  "train_011_age": 0.043,
  "train_011": {
    "position": 3050.0,
    "speed": 0.0,
    "train_index": null,
    "ma_limit": 2500.0,
    "mode": "emergency"
  },
  "ma_count": 11,
  "ma_has_011": true,
  "ma_011_age": 0.005,
  "ma_011": {
    "ma_limit": 2500.0,
    "distance_to_ma": -550.0,
    "permission": "stop"
  }
}
```

观察结论：

- `source=zmq`，说明后端当前读取的是 ZMQ 数据源。
- `train_count=11`，说明新增车辆已经进入后端汇总快照。
- `has_011=true`，说明 `TRAIN-011` 已经出现。
- `train_011_age=0.043`，说明 `TRAIN-011` 不是只写入后端本地缓存，而是在持续接收车辆算法模块的实时上报。
- `ma_count=11`，说明信号模块也对新增后的 11 辆车进行了计算。
- `ma_has_011=true`，说明信号模块已经为 `TRAIN-011` 返回 MA 结果。
- `ma_011_age=0.005`，说明 `TRAIN-011` 的 MA 结果也是实时从 ZMQ 收到的。

同时，车辆算法进程输出中可以看到 `TRAIN-011` 持续发布：

```json
{
  "type": "train_state",
  "vehicle_id": "TRAIN-011",
  "train_index": 11,
  "line_id": "LINE-1",
  "position": 3050.0,
  "speed": 0.0,
  "mode": "emergency",
  "emergency_brake": true
}
```

这说明车辆算法模块确实接收到了加车指令，并开始把新增车辆作为算法侧车辆状态持续发布到 ZMQ。

## 6. 本次验证通过的链路

本次已经验证通过的完整链路为：

```text
后端车辆管理接口
  -> 发布 add_train 到 ZMQ
  -> 车辆算法模块接收 add_train
  -> 车辆算法模块新增 TRAIN-011
  -> 车辆算法模块持续发布 TRAIN-011 的 train_state
  -> 信号模块接收 train_state
  -> 信号模块计算并发布 ma_state
  -> 后端 data_flow 接收 train_state / ma_state
  -> dashboard 快照中出现 TRAIN-011 及其 MA 结果
```

因此，动态加车链路和“子模块往 ZMQ 发真实/算法侧数据”的联调链路是通的。

## 7. 测试中发现的提醒

后端日志中出现过如下提示：

```text
Unknown dashboard message type: add_train
```

这个提示表示后端 data_flow 的 ZMQ 监听器自身不把 `add_train` 当作 dashboard 数据直接消费。

这不影响本次联调结果，因为真实数据更新链路不是靠 `add_train` 直接展示，而是：

1. `add_train` 发给车辆算法模块。
2. 车辆算法模块新增车辆。
3. 车辆算法模块再发布 `train_state`。
4. 后端 data_flow 通过 `train_state` 更新 dashboard。

所以该日志属于非阻塞提醒，不是本次动态加车链路失败。

## 8. 验证命令结果

尝试运行相关 pytest：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_vehicle_management_api.py tests/test_signal_zmq_adapter.py app/vehicle_sim/tests/test_adapters.py
```

结果：

```text
No module named pytest
```

原因是当前后端虚拟环境没有安装 `pytest`，所以未能执行单元测试。

随后执行语法编译检查：

```powershell
.\.venv\Scripts\python.exe -m compileall app tests
```

结果：通过。

说明当前合并后的 Python 模块没有语法编译错误。

## 9. 最终结论

本次测试结论：

1. `feature/vehicle-track` 合并后，车辆算法模块已经具备动态车辆管理能力。
2. 后端可以通过 `/api/v1/vehicle/manage` 发起动态加车。
3. 动态加车指令会通过 ZMQ topic `add_train` 发给车辆算法模块。
4. 车辆算法模块可以接收加车指令，并持续向 ZMQ 发布新增车辆的真实/算法侧 `train_state`。
5. 信号模块可以基于新增车辆继续计算 MA，并通过 ZMQ 返回 `ma_state`。
6. 后端数据流转模块可以接收这些 ZMQ 数据，并汇总到前端需要的 dashboard 快照中。

因此，本次联调验证通过。
