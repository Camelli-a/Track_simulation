# Signal Control Module

本文档说明当前信号控制最小版本的职责、输入输出协议、HTTP 接口返回结构和演示场景。

## 模块职责

信号控制模块位于 `backend/app/services/signal_control.py`，当前负责：

- 区段占用：根据列车 `position` 判断列车所在区段，并输出 `sections`。
- 道岔闭锁：维护 demo 道岔 `SW-01` 的位置和锁闭状态，并输出 `switches`。
- 进路冲突：根据临时进路申请判断道岔位置和锁闭方是否冲突，并输出 `route_results`。
- MA 计算：根据同一进路前车位置和安全距离计算移动授权终点，并输出 `ma_limits`。
- 信号约束输出：根据列车到 MA 的距离输出 `permission`、`signal_state`、`speed_limit` 等约束。

核心入口：

```python
calculate_signal_snapshot(
    train_states: list[dict],
    route_requests: list[dict] | None = None,
) -> dict
```

## 输入协议

### train_states

`train_states` 表示当前所有列车状态。每项包含：

```json
{
  "vehicle_id": "TRAIN-001",
  "position": 300.0,
  "speed": 40.0,
  "route_id": "R_MAIN"
}
```

字段说明：

- `vehicle_id`：列车 ID。
- `position`：列车当前位置，单位为 m。
- `speed`：列车当前速度。
- `route_id`：列车当前运行进路。

### route_requests

`route_requests` 表示临时进路申请，只用于进路冲突判断，不影响 `ma_limits` 的当前运行进路计算。每项包含：

```json
{
  "vehicle_id": "TRAIN-003",
  "route_id": "R_BRANCH"
}
```

字段说明：

- `vehicle_id`：申请进路的列车 ID。
- `route_id`：申请的目标进路。

## 输出字段

`calculate_signal_snapshot()` 返回：

```json
{
  "lights": [],
  "signals": [],
  "sections": [],
  "switches": [],
  "ma_limits": [],
  "route_results": []
}
```

字段说明：

- `lights`：兼容旧前端的信号灯列表，只包含 `signal_id`、`position`、`state`。
- `signals`：信号约束列表，包含 `state`、`signal_state`、`permission`、`route_id`。
- `sections`：区段状态列表，包含占用、锁闭和区段状态。
- `switches`：道岔状态列表，包含位置、锁闭方、关联区段和原因。
- `ma_limits`：移动授权和速度约束列表。
- `route_results`：临时进路申请结果列表。

## HTTP 接口

### 获取 mock 信号状态

当前 mock 快照接口保持不变：

```http
GET /api/v1/signal/status
```

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

`SignalService.get_status()` 当前仍使用内部 mock 数据，但已经通过协议字段调用：

```python
calculate_signal_snapshot(mock_train_states, mock_route_requests)
```

因此后续接真实车辆状态时，可以复用同一个核心入口。

### 调试计算真实输入

后端同学或车辆算法同学可以使用调试接口传入真实 `train_states` 和临时 `route_requests`，直接调用信号控制核心：

```http
POST /api/v1/signal/evaluate
```

请求示例：

```json
{
  "train_states": [
    {
      "vehicle_id": "TRAIN-001",
      "position": 300.0,
      "speed": 40.0,
      "route_id": "R_MAIN"
    },
    {
      "vehicle_id": "TRAIN-002",
      "position": 620.0,
      "speed": 40.0,
      "route_id": "R_MAIN"
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

`route_requests` 可以不传，默认按空列表处理：

```json
{
  "train_states": [
    {
      "vehicle_id": "TRAIN-001",
      "position": 300.0,
      "speed": 40.0,
      "route_id": "R_MAIN"
    }
  ]
}
```

返回结构与 `/api/v1/signal/status` 一致：

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

该接口只用于 HTTP 联调和算法验证，不接 ZMQ、WebSocket 或 UDP。

## 演示场景

### 多车 MA 防追尾

当同一进路上存在前车时，后车 MA 按以下规则计算：

```text
ma_limit = front_vehicle.position - safe_distance
```

当前 demo 中：

```json
{
  "vehicle_id": "TRAIN-001",
  "front_vehicle_id": "TRAIN-002",
  "safe_distance": 120.0,
  "ma_limit": 500.0,
  "reason": "front_vehicle_protection"
}
```

### yellow 限速

当列车距离 MA 的距离满足：

```text
80m < distance_to_ma <= 200m
```

输出：

```json
{
  "permission": "restricted",
  "signal_state": "yellow",
  "speed_limit": 30.0
}
```

### switch_locked_conflict 道岔闭锁冲突

当前 demo 道岔：

```json
{
  "switch_id": "SW-01",
  "position": "normal",
  "locked": true,
  "locked_by_route_id": "R_MAIN"
}
```

进路要求：

- `R_MAIN` 需要 `SW-01 = normal`
- `R_BRANCH` 需要 `SW-01 = reverse`

当 `TRAIN-003` 临时申请 `R_BRANCH` 时，因为 `SW-01` 已被 `R_MAIN` 锁闭为 `normal`，返回：

```json
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
```

## 后续接 ZMQ 的使用方式

当前版本不接 ZMQ、WebSocket 或 UDP。

后续接 ZMQ 时，建议流程为：

1. 后端接收车辆模块发送的 `train_state` 消息。
2. 在后端维护当前所有列车状态表。
3. 每次需要计算信号快照时，将所有列车状态整理成 `train_states`。
4. 如有临时进路申请，将其整理成 `route_requests`。
5. 调用：

```python
snapshot = calculate_signal_snapshot(train_states, route_requests)
```

6. 如需对外发布协议消息，可使用：

```python
signal_message = build_signal_state_message(snapshot)
ma_message = build_ma_state_message(snapshot)
```

其中 ZMQ 只负责消息传输，信号控制规则仍保持在 `calculate_signal_snapshot()` 内部。
