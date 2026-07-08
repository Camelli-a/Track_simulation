# ZMQ 通信总线 - 快速测试指南

本文档说明当前 ZMQ 通信模块的本地联调方式。所有命令默认在 `backend` 目录下执行。

```bash
cd backend
```

如果使用虚拟环境，请先激活：

```bash
.venv\Scripts\activate
```

## 测试流程

### 1. 启动 ZMQ Broker（必须）

终端 1：

```bash
python -m app.communication.broker
```

应该看到类似输出：

```text
[INFO] Starting ZMQ Broker...
[INFO]   Frontend (XPUB): tcp://127.0.0.1:5555
[INFO]   Backend  (XSUB): tcp://127.0.0.1:5556
[INFO] Broker is running...
```

保持这个终端运行，不要关闭。

### 2. 启动 Mock 数据发布器

终端 2：

```bash
python -m app.communication.mock_publisher
```

Mock 发布器会周期性发布车辆、信号、MA、供电等测试消息。

### 3. 启动信号模块 ZMQ Worker

终端 3：

```bash
python -m app.communication.signal_worker
```

信号 worker 的数据流：

1. 订阅 `topic=train_state`。
2. 缓存当前所有车辆状态。
3. 调用 `calculate_signal_snapshot(train_states, route_requests)`。
4. 发布 `topic=signal_state`。
5. 发布 `topic=ma_state`。

信号 worker 发布的 `signal_state.data` 包含：

```json
{
  "system_mode": "normal",
  "signals": [],
  "sections": [],
  "switches": [],
  "route_results": []
}
```

信号 worker 发布的 `ma_state.data` 包含：

```json
{
  "ma_limits": []
}
```

可以通过以下特征识别信号 worker 发出的消息：

- `signal_state.data` 包含 `route_results`。
- `ma_state.data.ma_limits[]` 包含 `braking_model`。

注意：`mock_publisher` 本身也会发布 `signal_state` 和 `ma_state`，因此联调时会看到两套信号 / MA 消息混杂。以 `route_results` 和 `braking_model` 字段区分即可。

### 4. 启动测试订阅器

终端 4：

```bash
python -m app.communication.test_subscriber
```

应该可以看到：

```text
[INFO] Subscribed to topic: train_state
[INFO] Subscribed to topic: signal_state
[INFO] Subscribed to topic: ma_state
[INFO] Test subscriber started, press Ctrl+C to stop
```

持续输出中应包含：

- `train_state`
- `signal_state`
- `ma_state`

## 信号模块 ZMQ 接入

信号模块当前新增独立运行入口：

```bash
python -m app.communication.signal_worker
```

topic 关系：

| 方向 | topic | 说明 |
|------|-------|------|
| 订阅 | `train_state` | 车辆状态，包含 `vehicle_id`、`position`、`speed`、`route_id`、`train_length` |
| 发布 | `signal_state` | 信号、区段、道岔、进路冲突结果 |
| 发布 | `ma_state` | 每辆车的 MA、permission、signal_state、speed_limit、制动曲线字段 |

`MessageBus.publish()` 会自动包装 `topic / timestamp / data`。信号 worker 发布时只把业务字段放入 `data`，不会在 `data` 内再放 `type` 或 `timestamp`。

正确格式：

```json
{
  "topic": "ma_state",
  "timestamp": 1720000000.0,
  "data": {
    "ma_limits": [
      {
        "vehicle_id": "TRAIN-001",
        "ma_limit": 455.0,
        "permission": "restricted",
        "signal_state": "yellow",
        "braking_model": "simplified_atp_braking_curve"
      }
    ]
  }
}
```

错误格式：

```json
{
  "topic": "ma_state",
  "timestamp": 1720000000.0,
  "data": {
    "type": "ma_state",
    "timestamp": 1720000000.0,
    "ma_limits": []
  }
}
```

## 验证要点

- Broker 正常启动：看到 `Broker is running`。
- Mock 发布器连接成功：看到 publisher / subscriber connected。
- 信号 worker 正常启动：订阅 `train_state`。
- 测试订阅器能收到 `train_state`、`signal_state`、`ma_state`。
- 信号 worker 的 `signal_state.data` 包含 `sections`、`switches`、`signals`、`route_results`。
- 信号 worker 的 `ma_state.data.ma_limits[]` 包含 `braking_model`、`required_stop_distance`、`emergency_stop_distance`、`warning_distance`、`braking_curve_speed_limit`。
- `data` 中不存在双层 `type` / `timestamp`。

## 故障排查

### 订阅器收不到消息

可能原因：

- Broker 没有启动。
- 端口 `5555 / 5556` 被占用。
- 发布器或订阅器没有连接到同一组地址。

排查命令：

```bash
netstat -ano | findstr 5555
netstat -ano | findstr 5556
```

### Import 错误

可能原因：

- 当前目录不是 `backend`。
- 虚拟环境未激活。
- 依赖未安装。

处理方式：

```bash
cd backend
.venv\Scripts\activate
pip install -r requirements.txt
```

## 相关文档

- [消息格式规范](../docs/message-spec.md)
- [信号控制模块说明](app/services/signal_control_README.md)
