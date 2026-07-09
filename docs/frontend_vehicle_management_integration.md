# 前端车辆管理与车辆接口对接说明

本文档面向前端说明车辆增删管理如何调用，以及哪些字段来自正式车辆接口文档。注意：前端页面使用的是平台内部 REST/ZMQ 接口；《轨交多系统平台接口协议汇总20260630.docx》里的车辆 UDP/API 是车辆模型对外正式适配层，不等同于前端 REST API。

## 1. 前端调用原则

车辆实例由后端车辆模块创建和维护，前端只负责发送管理请求和展示返回结果。

推荐链路：

```text
前端按钮
  -> POST /api/v1/vehicle/manage
  -> vehicle_sim.message_router
  -> TrainManager.add_train/remove_train/clear_trains/reset_trains
  -> 返回最新 trains
  -> 同时发布 ZMQ 管理消息给独立车辆仿真进程
```

前端不要自己维护“真实车辆列表”。车辆管理页面优先使用 `/api/v1/vehicle/manage` 返回体里的 `trains`，或主动查询 `/api/v1/vehicle/trains`。

## 2. 车辆数量规则

- `TrainManager()` 默认创建 10 辆车：`TRAIN-001` 到 `TRAIN-010`。
- 内部车辆数量不设置固定上限，可以继续添加 `TRAIN-011`、`TRAIN-021` 等。
- `train_index` 只要求大于等于 1。
- 如果不传 `train_index`，后端自动使用最小空闲槽位。
- 如果某个 `train_index` 已被占用，添加会失败，不覆盖旧车。
- 正式 UDP 报文只携带 1 到 20 号槽位，这是协议帧限制，不是车辆数量限制。
- `train_index > 20` 的车辆仍会存在于内部、REST、ZMQ、JSON 状态里，但不会进入固定 480 字节 UDP 报文。

## 3. 前端按钮

| 按钮 | 请求类型 | 说明 |
|---|---|---|
| 添加车辆 | `add_train` | 添加一辆激活车辆 |
| 删除车辆 | `remove_train` | 删除指定车辆或槽位 |
| 清空车辆 | `clear_trains` | 删除所有激活车辆 |
| 重置车辆 | `reset_trains` | 清空后重新创建指定数量车辆 |

## 4. REST 接口

统一使用：

```http
POST /api/v1/vehicle/manage
```

查询当前车辆列表：

```http
GET /api/v1/vehicle/trains
```

### 添加车辆

指定编号和槽位：

```json
{
  "type": "add_train",
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
  "line_id": "LINE-1",
  "position": 1200.0
}
```

### 删除车辆

按车辆编号：

```json
{
  "type": "remove_train",
  "vehicle_id": "TRAIN-011"
}
```

按槽位：

```json
{
  "type": "remove_train",
  "train_index": 11
}
```

### 清空车辆

```json
{
  "type": "clear_trains"
}
```

### 重置车辆

```json
{
  "type": "reset_trains",
  "count": 10
}
```

`count` 只要求大于等于 0，不受 UDP 20 槽位限制。

## 5. 返回体

添加成功示例：

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

- `ok`：本地 `TrainManager` 是否执行成功，前端主要看这个字段。
- `published`：是否成功发布到模块消息总线。
- `result`：本次 add/remove/clear/reset 的执行结果。
- `trains`：执行后的当前车辆列表，可直接刷新 UI。

常见失败：

```json
{
  "ok": false,
  "reason": "slot_occupied",
  "slot": 11
}
```

```json
{
  "ok": false,
  "reason": "train_not_found",
  "vehicle_id": "TRAIN-011"
}
```

## 6. 列表刷新策略

推荐流程：

1. 发出 add/remove/clear/reset 请求。
2. 根据返回 `ok` 显示 toast。
3. 用返回体里的 `trains` 刷新车辆列表。
4. 如需主动查询，调用 `GET /api/v1/vehicle/trains`。
5. 真实联调 `DATA_SOURCE=zmq` 时，可以再用 WebSocket `/ws/dashboard` 的 `dashboard_snapshot.trains` 做全局刷新。

默认开发配置 `DATA_SOURCE=mock` 下，dashboard mock 服务会继续生成演示快照。车辆管理页面应以 `/api/v1/vehicle/manage` 返回的 `trains` 或 `/api/v1/vehicle/trains` 为准。

## 7. 正式车辆接口文档边界

根据《轨交多系统平台接口协议汇总20260630.docx》的车辆系统部分：

- UDP 使用小端模式。
- UDP 通讯周期为 20 ms。
- API 通讯周期为 500 ms。
- 模型侧 IP：`192.168.200.110`，端口 `23001`。
- 平台侧 IP：`192.168.200.102`，端口 `23002`。
- 模型到平台 UDP：1 到 20 号列车，每车 3 个 `double`：加速度、速度、累计里程。
- 平台到模型 UDP：1 到 20 号列车，每车 2 个 `double`：指令、加减速百分比。
- RT-LAB API 输出变量：1 到 20 号列车，每车 6 个 `float`：编号、激活端、方向、加速度、速度、累计里程。
- RT-LAB API 输入变量：1 到 20 号列车，每车 6 个 `float`：编号、操作指令、seg 号、偏移、方向、激活端。

车辆模块里的正式适配层位置：

```text
backend/app/vehicle_sim/adapters/vehicle_udp_codec.py
backend/app/vehicle_sim/adapters/vehicle_api_codec.py
```

前端不需要直接调用这两个适配层。它们用于车辆模型正式协议联调。

## 8. data-flow 对接注意

车辆模块会输出 `train_state`，字段包含：

```json
{
  "type": "train_state",
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
```

车辆模块接收 `ma_state` 时，支持两种内部形态：

```json
{
  "type": "ma_state",
  "ma_limits": [
    {
      "vehicle_id": "TRAIN-001",
      "ma_limit": 500.0,
      "speed_limit": 45.0,
      "distance_to_ma": 120.0,
      "permission": "restricted",
      "signal_state": "yellow"
    }
  ]
}
```

```json
{
  "type": "ma_state",
  "vehicle_id": "TRAIN-001",
  "ma_limit": 500.0,
  "speed_limit": 45.0,
  "distance_to_ma": 120.0,
  "permission": "restricted",
  "signal_state": "yellow"
}
```

这只是车辆模块兼容内部消息形态，不改变正式车辆 UDP/API 协议。

## 9. 前端伪代码

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

## 10. 验证命令

```bash
cd C:\Users\Tsuki\Desktop\code\Track_simulation\backend
python -m app.vehicle_sim.tests.run_regression
python -m pytest tests app\vehicle_sim\tests
```

通过表示：

- 默认 10 辆车通过。
- add/remove/clear/reset 通过。
- 内部车辆可超过 20 辆通过。
- UDP 固定 480 字节打包通过。
- RT-LAB API 120 float 适配通过。
