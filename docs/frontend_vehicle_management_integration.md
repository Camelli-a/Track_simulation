# 前端车辆增删管理对接说明

本文档给前端说明“添加车辆 / 删除车辆 / 清空车辆 / 重置车辆”如何与车辆仿真模块对接。

## 1. 总体原则

车辆实例由后端车辆模块创建和维护，前端只负责发送管理请求、展示结果。

前端不要在浏览器里长期维护一份“真实车辆列表”。车辆列表应以后端输出的 `train_state` / `dashboard_snapshot.trains` 为准。

推荐链路：

```text
前端按钮
  -> 后端 API / ZMQ 管理消息
  -> vehicle_sim.message_router
  -> TrainManager.add_train/remove_train/clear_trains/reset_trains
  -> 后续 train_state/dashboard_snapshot 自动刷新
```

## 2. 当前车辆模块能力

车辆管理核心在：

```text
backend/app/vehicle_sim/train_manager.py
```

默认行为：

- `TrainManager()` 启动后默认创建 10 辆车。
- 默认车辆为 `TRAIN-001` 到 `TRAIN-010`。
- 每辆车占用正式协议中的一个 `train_index` 槽位。
- 正式 UDP 协议固定 1~20 槽位，但车辆模块内部只维护激活车辆。
- 空槽位只在 UDP 打包时补 `0.0`，不会输出空车 JSON。

关键限制：

- 最大车辆数：20。
- `train_index` 范围：1~20。
- 添加车辆时如果不指定 `train_index`，后端会自动分配最小空闲槽位。
- 删除车辆会释放对应槽位。

## 3. 前端按钮建议

建议前端提供这些操作：

| 按钮 | 后端消息类型 | 说明 |
|---|---|---|
| 添加车辆 | `add_train` | 添加一辆激活车辆 |
| 删除车辆 | `remove_train` | 删除指定车辆或指定槽位 |
| 清空车辆 | `clear_trains` | 删除所有激活车辆 |
| 重置车辆 | `reset_trains` | 清空后重新创建指定数量车辆 |

## 4. 管理消息格式

### 4.1 添加车辆

指定车辆编号和槽位：

```json
{
  "type": "add_train",
  "timestamp": 1720000000.123,
  "vehicle_id": "TRAIN-011",
  "train_index": 11,
  "line_id": "LINE-1",
  "position": 1200.0
}
```

自动分配最小空闲槽位：

```json
{
  "type": "add_train",
  "timestamp": 1720000000.123,
  "line_id": "LINE-1",
  "position": 1200.0
}
```

说明：

- `vehicle_id` 可选。
- `train_index` 可选。
- `position` 可选，默认 `0.0`，单位 m。
- `line_id` 可选，默认 `LINE-1`。
- 如果 `train_index` 已被占用，后端会返回失败，不会覆盖旧车。
- 如果已经有 20 辆车，后端会返回失败。

### 4.2 删除车辆

按车辆编号删除：

```json
{
  "type": "remove_train",
  "timestamp": 1720000000.123,
  "vehicle_id": "TRAIN-011"
}
```

按槽位删除：

```json
{
  "type": "remove_train",
  "timestamp": 1720000000.123,
  "train_index": 11
}
```

说明：

- 删除不存在的车辆不会导致后端崩溃。
- 删除成功后，该 `train_index` 会被释放，后续自动添加车辆可以复用。

### 4.3 清空车辆

```json
{
  "type": "clear_trains",
  "timestamp": 1720000000.123
}
```

说明：

- 清空后 `step_all()` 不再输出任何 `train_state`。
- 正式 UDP 打包仍然会输出固定 20 槽位，但全部填 `0.0`。

### 4.4 重置车辆

重置为 10 辆：

```json
{
  "type": "reset_trains",
  "timestamp": 1720000000.123,
  "count": 10
}
```

重置为 5 辆：

```json
{
  "type": "reset_trains",
  "timestamp": 1720000000.123,
  "count": 5
}
```

说明：

- `count` 会被限制在 `0~20`。
- 如果不传，建议前端默认传 `10`。

## 5. 预期返回结果

车辆模块内部方法返回结构如下，前端 API 可以直接透传。

添加成功：

```json
{
  "ok": true,
  "vehicle_id": "TRAIN-011",
  "train_index": 11,
  "position": 1200.0,
  "line_id": "LINE-1"
}
```

添加失败，槽位已占用：

```json
{
  "ok": false,
  "reason": "slot_occupied",
  "slot": 11
}
```

添加失败，达到 20 辆上限：

```json
{
  "ok": false,
  "reason": "max_trains_reached"
}
```

删除成功：

```json
{
  "ok": true,
  "vehicle_id": "TRAIN-011",
  "train_index": 11
}
```

删除失败，找不到车辆：

```json
{
  "ok": false,
  "reason": "train_not_found",
  "vehicle_id": "TRAIN-011"
}
```

清空成功：

```json
{
  "ok": true,
  "removed": 10
}
```

重置成功：

```json
{
  "ok": true,
  "count": 10
}
```

## 6. 前端如何刷新车辆列表

车辆管理请求成功后，前端不需要自己拼接车辆列表。

推荐做法：

1. 发出添加/删除/清空/重置请求。
2. 根据返回结果显示 toast。
3. 优先使用 `/api/v1/vehicle/manage` 返回体里的 `trains` 直接刷新车辆列表。
4. 如需主动查询，调用 `GET /api/v1/vehicle/trains`。
5. 真实联调使用 `DATA_SOURCE=zmq` 时，也可以等待 WebSocket `/ws/dashboard` 下一帧推送，再用 `dashboard_snapshot.trains` 统一刷新。

注意：默认开发配置 `DATA_SOURCE=mock` 下，dashboard mock 服务会继续生成演示快照。这个模式下车辆增删页面应以 `/api/v1/vehicle/manage` 返回的 `trains` 或 `GET /api/v1/vehicle/trains` 为准；真实多模块联调时再以 ZMQ/dashboard 快照为准。

如果 WebSocket 断开，可以轮询：

```http
GET /api/v1/dashboard/snapshot
```

车辆列表字段位置：

```json
{
  "type": "dashboard_snapshot",
  "trains": [
    {
      "vehicle_id": "TRAIN-001",
      "train_index": 1,
      "line_id": "LINE-1",
      "position": 0.0,
      "speed": 0.0,
      "acceleration": 0.0,
      "mode": "manual",
      "is_running": false,
      "emergency_brake": false
    }
  ]
}
```

## 7. 前端表单建议

添加车辆弹窗建议字段：

| 字段 | 是否必填 | 默认值 | 说明 |
|---|---|---|---|
| `vehicle_id` | 否 | 空 | 不填则由后端按槽位生成 |
| `train_index` | 否 | 空 | 不填则后端自动分配最小空闲槽位 |
| `position` | 否 | `0.0` | 初始位置，单位 m |
| `line_id` | 否 | `LINE-1` | 线路编号 |

删除车辆弹窗建议字段：

| 字段 | 是否必填 | 说明 |
|---|---|---|
| `vehicle_id` | 与 `train_index` 二选一 | 推荐从当前车辆列表选择 |
| `train_index` | 与 `vehicle_id` 二选一 | 可以用于删除某个槽位 |

重置车辆弹窗建议字段：

| 字段 | 是否必填 | 默认值 | 说明 |
|---|---|---|---|
| `count` | 是 | `10` | 范围 0~20 |

## 8. 当前后端对接状态

车辆模块内部已经支持这些消息：

- `add_train`
- `remove_train`
- `clear_trains`
- `reset_trains`

处理入口：

```text
backend/app/vehicle_sim/message_router.py
```

真正创建/删除车辆的位置：

```text
backend/app/vehicle_sim/train_manager.py
```

当前已经补好 REST 桥接接口：

```http
POST /api/v1/vehicle/manage
```

这个接口会做两件事：

- 在 API 进程内调用 `MessageRouter -> TrainManager`，立即完成本地车辆列表增删。
- 同时向模块总线发布同名管理消息，让独立运行的车辆仿真进程也能执行同样操作。

车辆仿真独立进程的 ZMQ 订阅列表也已经包含：

- `add_train`
- `remove_train`
- `clear_trains`
- `reset_trains`

前端还可以查询当前 API 进程内维护的车辆列表：

```http
GET /api/v1/vehicle/trains
```

## 9. HTTP API 设计

统一使用一个 endpoint：

```http
POST /api/v1/vehicle/manage
```

请求体直接使用管理消息：

```json
{
  "type": "add_train",
  "vehicle_id": "TRAIN-011",
  "train_index": 11,
  "line_id": "LINE-1",
  "position": 1200.0
}
```

返回体：

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
    "position": 1200.0,
    "line_id": "LINE-1"
  },
  "trains": [
    {
      "vehicle_id": "TRAIN-001",
      "train_index": 1,
      "line_id": "LINE-1",
      "position": 0.0,
      "speed": 0.0,
      "mode": "manual",
      "emergency_brake": false
    }
  ]
}
```

字段说明：

- `ok`：本地 `TrainManager` 是否执行成功。
- `published`：是否成功发布到模块消息总线。前端展示时以 `ok` 作为主要判断。
- `result`：本次 add/remove/clear/reset 的执行结果。
- `trains`：执行后的当前车辆列表，可直接用于局部刷新。

## 10. 前端伪代码

```js
async function addTrain(payload) {
  const response = await fetch('/api/v1/vehicle/manage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      type: 'add_train',
      ...payload,
    }),
  })

  const result = await response.json()
  if (!result.ok) {
    throw new Error(result.result?.reason || 'add_train_failed')
  }
  return result
}

async function removeTrain(vehicleId) {
  const response = await fetch('/api/v1/vehicle/manage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      type: 'remove_train',
      vehicle_id: vehicleId,
    }),
  })
  return response.json()
}

async function resetTrains(count = 10) {
  const response = await fetch('/api/v1/vehicle/manage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      type: 'reset_trains',
      count,
    }),
  })
  return response.json()
}

async function fetchManagedTrains() {
  const response = await fetch('/api/v1/vehicle/trains')
  return response.json()
}
```

## 11. 验证方法

后端验证命令：

```bash
cd C:\Users\Tsuki\Desktop\code\Track_simulation\backend
python -m app.vehicle_sim.tests.run_regression
```

关键输出：

```text
vehicle_sim regression passed
adapter checks passed
dynamic train manager checks passed
```

表示：

- 默认 10 辆车通过。
- add/remove/clear/reset 通过。
- UDP 固定 480 字节打包通过。
