# 后端数据流转模块接口文档

本文档说明 `backend/app/data_flow` 模块对前端、通信模块、车辆算法模块、信号算法模块提供和消费的接口。

`data_flow` 的职责是：

- 从 ZMQ 总线接收各子模块消息。
- 归一化字段名和数据结构。
- 缓存在内存状态仓库 `state_store` 中。
- 通过 REST 和 WebSocket 向前端提供统一的 `dashboard_snapshot`。
- 在前端下发或需要广播线路数据时，向 ZMQ 总线发布消息。

## 一、运行方式

### 1. Mock 模式

不依赖 ZMQ，总是由后端本地生成演示数据。

```bash
cd backend
set DATA_SOURCE=mock
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

### 2. ZMQ 联调模式

后端会启动 `ZmqDashboardListener`，订阅 ZMQ broker 的 frontend 地址，接收其他模块上报的数据。

```bash
cd backend
python -m app.communication.broker
```

另开终端：

```bash
cd backend
set DATA_SOURCE=zmq
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

可选：启动通信 mock publisher 或各算法模块自己的 publisher。

```bash
cd backend
python -m app.communication.mock_publisher
```

## 二、前端接口

### 1. 获取当前大屏快照

```http
GET /api/v1/dashboard/snapshot
```

完整本地地址：

```text
http://127.0.0.1:8000/api/v1/dashboard/snapshot
```

返回类型：`DashboardSnapshot`

用途：

- 前端首次加载时获取当前全局状态。
- WebSocket 断开时作为降级轮询接口。
- 调试时直接查看后端当前缓存了哪些数据。

示例返回：

```json
{
  "type": "dashboard_snapshot",
  "protocol_version": "1.0",
  "timestamp": 1720000000.123,
  "system": {
    "status": "running",
    "system_mode": "normal",
    "data_source": "zmq",
    "zmq_connected": true,
    "websocket_clients": 1
  },
  "communication": {},
  "driver_inputs": [],
  "ato_commands": [],
  "trains": [],
  "ma_limits": [],
  "sections": [],
  "signals": [],
  "switches": [],
  "route_results": [],
  "power": {},
  "alarms": []
}
```

### 2. WebSocket 实时推送

```text
ws://127.0.0.1:8000/ws/dashboard
```

如果前端通过 Vite 代理启动，也可以连接：

```text
ws://127.0.0.1:5173/ws/dashboard
```

推送频率：

- 约每 `0.2s` 推送一次。
- 每次推送的数据结构和 `GET /api/v1/dashboard/snapshot` 完全一致。

前端只需要监听消息并按 `dashboard_snapshot` 渲染，不需要直接订阅 ZMQ。

### 3. 发布线路信息到 ZMQ

```http
POST /api/v1/dashboard/publish-track-info
```

用途：

- 将后端当前缓存的线路区段信息整理为 `track_info` topic。
- 发布给车辆算法模块，用于更新车辆侧轨道坡度、限速、站台停车点等信息。

返回示例：

```json
{
  "accepted": true,
  "published": true,
  "topic": "track_info",
  "section_count": 10
}
```

### 4. 注册车辆 / 加车

```http
POST /api/v1/dashboard/vehicles/register
```

用途：

- 在 data_flow 本地快照里新增或更新一辆车。
- 同时向 ZMQ 发布 `vehicle_register` 和 `set_train_state`，方便车辆算法模块接收初始车辆状态。
- 如果车辆算法模块暂时还没有动态加车能力，前端仍然可以先从 data_flow 快照看到这辆车。

请求示例：

```json
{
  "vehicle_id": "TRAIN-004",
  "line_id": "LINE-1",
  "route_id": "R_MAIN",
  "position": 2200.0,
  "speed": 0.0,
  "acceleration": 0.0,
  "train_length": 120.0,
  "mode": "manual"
}
```

返回示例：

```json
{
  "accepted": true,
  "vehicle_id": "TRAIN-004",
  "published": true,
  "topics": {
    "vehicle_register": true,
    "set_train_state": true
  }
}
```

### 5. 发起进路申请

```http
POST /api/v1/dashboard/route-request
```

用途：

- 在 data_flow 本地快照里记录车辆进路申请。
- 向 ZMQ 发布 `route_request`，供信号算法模块后续订阅和计算。

请求示例：

```json
{
  "vehicle_id": "TRAIN-003",
  "route_id": "R_BRANCH",
  "request_id": "REQ-TRAIN-003-R-BRANCH",
  "priority": 1
}
```

返回示例：

```json
{
  "accepted": true,
  "published": true,
  "topic": "route_request",
  "request_key": "REQ-TRAIN-003-R-BRANCH"
}
```

## 三、DashboardSnapshot 字段

### 1. system

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | 后端服务状态，通常为 `running` |
| `system_mode` | string | 系统模式，如 `normal` / `degraded` / `emergency` |
| `data_source` | string | 数据来源：`mock` / `udp` / `zmq` / `frontend` / `unknown` |
| `zmq_connected` | boolean | 后端 ZMQ listener 是否连接 |
| `websocket_clients` | number | 当前 WebSocket 客户端数量 |

### 2. communication

| 字段 | 类型 | 说明 |
|---|---|---|
| `source` | string | 通信数据来源 |
| `driver_console_connected` | boolean | 司机台是否连接 |
| `udp_connected` | boolean | UDP 是否连接 |
| `zmq_connected` | boolean | ZMQ 是否连接 |
| `latency_ms` | number/null | 通信延迟，单位 ms |
| `packet_loss_count` | number | 丢包数量 |
| `last_message_at` | number/null | 最近消息时间戳 |

### 3. trains

`trains` 是前端展示车辆位置、速度、MA、停车状态的主要数据源。

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `vehicle_id` | string | - | 车辆编号 |
| `line_id` | string | - | 线路编号 |
| `route_id` | string | - | 当前进路 |
| `position` | number | m | 当前里程位置 |
| `speed` | number | km/h | 当前速度 |
| `acceleration` | number | m/s² | 当前加速度 |
| `train_length` | number/null | m | 列车长度，供信号 MA 计算使用 |
| `mode` | string | - | `manual` / `ato` / `atp` / `emergency` / `unknown` |
| `is_running` | boolean | - | 是否运行中 |
| `emergency_brake` | boolean | - | 是否紧急制动 |
| `ma_limit` | number/null | m | 移动授权边界 |
| `distance_to_ma` | number/null | m | 距离 MA 边界的剩余距离 |
| `permission` | string | - | `allow` / `restricted` / `stop` / `unknown` |
| `signal_state` | string | - | `red` / `yellow` / `green` / `unknown` |
| `speed_limit` | number/null | km/h | 当前限速 |
| `target_speed` | number/null | km/h | 目标速度 |
| `route_speed_limit` | number/null | km/h | 进路限速 |
| `required_stop_distance` | number/null | m | 常用制动停车距离 |
| `emergency_stop_distance` | number/null | m | 紧急制动停车距离 |
| `warning_distance` | number/null | m | 预警距离 |
| `braking_curve_speed_limit` | number/null | km/h | 制动曲线反推限速 |
| `braking_model` | string/null | - | 制动模型名称 |
| `front_vehicle_id` | string/null | - | 前车编号 |
| `front_protection_point` | number/null | m | 前车保护点 |
| `energy_kwh` | number/null | kWh | 累计能耗 |
| `stop_distance` | number/null | m | 到停车点距离 |
| `station_name` | string/null | - | 站名 |
| `parking_phase` | string | - | `cruising` / `approaching` / `braking` / `docking` / `stopped` |
| `stop_error_cm` | number/null | cm | 停车误差 |
| `platform_id` | string/null | - | 站台编号 |
| `updated_at` | number | s | 后端更新时间戳 |
| `raw_data` | object | - | 原始输入数据，便于调试 |

说明：

- `ma_limit`、`speed_limit`、`target_speed` 等字段来自 `ma_state` 后会同步回对应车辆的 `TrainSnapshot`。
- 前端通常优先读 `trains`，不需要自己再把 `ma_limits` 合并到车辆上。

### 4. ma_limits

`ma_limits` 保存信号模块发布的移动授权结果原始归一化快照。

| 字段 | 类型 | 说明 |
|---|---|---|
| `vehicle_id` | string | 车辆编号 |
| `position` | number/null | 车辆当前位置 |
| `route_id` | string | 进路编号 |
| `ma_limit` | number | 移动授权边界 |
| `distance_to_ma` | number/null | 距离 MA 边界的剩余距离 |
| `permission` | string | 授权状态 |
| `signal_state` | string | 信号状态 |
| `speed_limit` | number/null | 当前限速 |
| `target_speed` | number/null | 目标速度 |
| `reason` | string/null | MA 来源原因 |
| `front_vehicle_id` | string/null | 前车编号 |
| `front_train_length` | number/null | 前车长度 |
| `location_uncertainty` | number/null | 定位误差裕量 |
| `communication_margin` | number/null | 通信裕量 |
| `safety_margin` | number/null | 安全裕量 |
| `front_protection_point` | number/null | 前车保护点 |
| `safe_distance` | number/null | 安全距离 |
| `current_speed` | number/null | 当前速度 |
| `route_speed_limit` | number/null | 进路限速 |
| `required_stop_distance` | number/null | 常用制动停车距离 |
| `emergency_stop_distance` | number/null | 紧急制动停车距离 |
| `warning_distance` | number/null | 预警距离 |
| `braking_curve_speed_limit` | number/null | 制动曲线限速 |
| `braking_model` | string/null | 制动模型 |
| `updated_at` | number | 更新时间 |
| `raw_data` | object | 原始输入 |

### 5. sections

| 字段 | 类型 | 说明 |
|---|---|---|
| `section_id` | string | 区段编号 |
| `line_id` | string | 线路编号 |
| `track_seg_id` | string/null | 轨道 Seg 编号 |
| `start` | number | 起点里程，单位 m |
| `end` | number | 终点里程，单位 m |
| `gradient` | number/null | 坡度 |
| `speed_limit` | number/null | 区段限速 |
| `station_id` | string/null | 车站编号 |
| `stop_position` | number/null | 停车点 |
| `occupied` | boolean | 是否占用 |
| `vehicle_id` | string/null | 占用车辆 |
| `occupied_by` | string/null | 占用车辆兼容字段 |
| `aspect` | string | `green` / `yellow` / `red` / `unknown` |
| `locked` | boolean | 是否锁闭 |
| `locked_by_route_id` | string/null | 锁闭进路 |
| `condition` | string | `normal` / `warning` / `fault` |

### 6. signals

| 字段 | 类型 | 说明 |
|---|---|---|
| `signal_id` | string | 信号机编号 |
| `position` | number | 位置，单位 m |
| `state` | string | `red` / `yellow` / `green` / `unknown` |
| `signal_type` | string/null | 信号机类型 |
| `route_id` | string/null | 关联进路 |
| `signal_state` | string | 信号状态兼容字段 |
| `permission` | string | 授权状态 |

### 7. switches

| 字段 | 类型 | 说明 |
|---|---|---|
| `switch_id` | string | 道岔编号 |
| `position` | string | `normal` / `reverse` / `unknown` |
| `turnout_id` | string/null | 道岔兼容编号 |
| `routing` | string | 当前开通方向 |
| `state` | string | 状态兼容字段 |
| `locked` | boolean | 是否锁闭 |
| `locked_by_route_id` | string/null | 锁闭进路 |
| `related_section` | string/null | 关联区段 |
| `reason` | string/null | 锁闭原因 |

### 8. route_results

| 字段 | 类型 | 说明 |
|---|---|---|
| `vehicle_id` | string/null | 车辆编号 |
| `route_id` | string/null | 进路编号 |
| `allowed` | boolean | 进路是否允许 |
| `reason` | string/null | 拒绝或允许原因 |
| `required_switch_id` | string/null | 需要的道岔 |
| `required_position` | string/null | 需要的道岔位置 |
| `current_position` | string/null | 当前道岔位置 |
| `locked_by_route_id` | string/null | 当前锁闭进路 |

### 9. route_requests

`route_requests` 保存 data_flow 收到或发出的进路申请，用于联调“车辆申请进路 -> 信号模块计算 -> 返回 route_results/ma_state”这条链路。

| 字段 | 类型 | 说明 |
|---|---|---|
| `request_id` | string/null | 进路申请编号 |
| `vehicle_id` | string | 申请车辆 |
| `route_id` | string | 申请进路 |
| `origin_section_id` | string/null | 起始区段 |
| `destination_section_id` | string/null | 目标区段 |
| `start_position` | number/null | 起点位置 |
| `end_position` | number/null | 终点位置 |
| `priority` | number | 优先级 |
| `status` | string | `pending` / `accepted` / `rejected` / `unknown` |
| `reason` | string/null | 状态原因 |
| `updated_at` | number | 更新时间 |
| `raw_data` | object | 原始输入 |

### 10. power

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `substation_id` | string | - | 变电站编号 |
| `voltage` | number | V | 网压 |
| `current` | number | A | 电流 |
| `power` | number | kW | 功率 |
| `is_fault` | boolean | - | 是否故障 |
| `updated_at` | number/null | s | 更新时间 |
| `raw_data` | object | - | 原始输入 |

### 11. alarms

| 字段 | 类型 | 说明 |
|---|---|---|
| `alarm_id` | string | 告警编号 |
| `level` | string | `info` / `warning` / `critical` |
| `level_label` | string/null | 中文等级：`信息` / `警告` / `严重` |
| `source` | string | 原始来源，如 `ATP` / `SIGNAL` / `POWER` |
| `source_label` | string/null | 中文来源，如 `ATP 安全防护` / `信号系统` |
| `vehicle_id` | string/null | 关联车辆 |
| `message` | string | 展示给前端的告警文案，已做中文化映射 |
| `timestamp` | number | 告警时间 |
| `raw_data` | object | 原始告警，保留英文原文用于排查 |

## 四、ZMQ 输入 topic

后端在 `DATA_SOURCE=zmq` 时订阅所有 topic，并根据 `topic/type` 分发。

支持三种输入格式。

### 1. MessageBus 标准包装

通信模块 `MessageBus.publish(topic, data)` 会自动生成这种结构：

```json
{
  "topic": "train_state",
  "timestamp": 1720000000.123,
  "data": {
    "vehicle_id": "TRAIN-001",
    "position": 1234.5,
    "speed": 62.4
  }
}
```

### 2. 兼容包装

```json
{
  "type": "train_state",
  "timestamp": 1720000000.123,
  "source": "vehicle_algo",
  "data": {
    "vehicle_id": "TRAIN-001",
    "position": 1234.5,
    "speed": 62.4
  }
}
```

### 3. 旧版扁平格式

```json
{
  "type": "train_state",
  "timestamp": 1720000000.123,
  "source": "vehicle_algo",
  "vehicle_id": "TRAIN-001",
  "position": 1234.5,
  "speed": 62.4
}
```

### 4. topic 清单

| topic | 发送方 | data_flow 处理 |
|---|---|---|
| `train_state` | 车辆模块 / Mock | 更新 `trains` |
| `vehicle_register` / `vehicle_spawn` / `add_vehicle` | 前端 / 车辆模块 | 新增或更新 `trains` 中的车辆 |
| `set_train_state` | 前端 / 测试脚本 / 车辆模块 | 设置车辆初始状态或手动修正车辆状态 |
| `driver_input` | 通信模块 / 前端控车 | 更新 `driver_inputs` |
| `ato_command` | ATO / 前端控车 | 更新 `ato_commands` |
| `signal_state` | 信号模块 | 更新 `sections/signals/switches/route_results/system_mode` |
| `ma_state` | 信号模块 | 更新 `ma_limits`，并同步到对应 `trains` |
| `route_request` / `route_apply` / `route_application` | 前端 / 车辆模块 / 调度逻辑 | 更新 `route_requests` |
| `route_result` | 信号模块 | 追加更新 `route_results` |
| `track_info` | 轨道模块 / 后端发布 | 更新线路区段静态信息 |
| `power_state` | 供电模块 / Mock | 更新 `power` |
| `comm_state` | 通信模块 | 更新 `communication` |
| `alarm_event` | 任意模块 | 更新 `alarms` |

## 五、各 topic 的 data 示例

### 1. train_state

```json
{
  "vehicle_id": "TRAIN-001",
  "line_id": "LINE-1",
  "route_id": "R_MAIN",
  "position": 1234.5,
  "speed": 62.4,
  "acceleration": 0.32,
  "mode": "ato",
  "is_running": true,
  "emergency_brake": false,
  "energy_kwh": 52.5,
  "stop_distance": 120.0,
  "station_name": "中心站",
  "parking_phase": "approaching",
  "stop_error_cm": 45.0,
  "platform_id": "PF-01"
}
```

### 2. driver_input

```json
{
  "vehicle_id": "TRAIN-001",
  "line_id": "LINE-1",
  "source": "udp",
  "traction_level": 3,
  "brake_level": 0,
  "direction": "forward",
  "control_mode": "manual",
  "emergency_button": false
}
```

### 3. ato_command

```json
{
  "vehicle_id": "TRAIN-001",
  "line_id": "LINE-1",
  "control_mode": "ato",
  "target_speed": 60.0,
  "target_position": 1600.0,
  "traction_level": 2,
  "brake_level": 0,
  "reason": "cruise"
}
```

### 4. signal_state

```json
{
  "system_mode": "normal",
  "sections": [
    {
      "section_id": "JZ1",
      "start": 0.0,
      "end": 758.0,
      "occupied": true,
      "vehicle_id": "TRAIN-001",
      "locked": false,
      "locked_by_route_id": null,
      "condition": "normal"
    }
  ],
  "signals": [
    {
      "signal_id": "SIG-01",
      "position": 300.0,
      "state": "yellow",
      "signal_state": "yellow",
      "route_id": "R_MAIN",
      "permission": "restricted"
    }
  ],
  "switches": [
    {
      "switch_id": "SW-01",
      "position": "normal",
      "locked": true,
      "locked_by_route_id": "R_MAIN",
      "related_section": "JZ4",
      "reason": "route_locked"
    }
  ],
  "route_results": [
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
  ]
}
```

### 5. ma_state

```json
{
  "ma_limits": [
    {
      "vehicle_id": "TRAIN-001",
      "position": 300.0,
      "route_id": "R_MAIN",
      "ma_limit": 455.0,
      "distance_to_ma": 155.0,
      "permission": "restricted",
      "signal_state": "yellow",
      "speed_limit": 51.8,
      "target_speed": 51.8,
      "reason": "front_vehicle_protection",
      "front_vehicle_id": "TRAIN-002",
      "front_train_length": 120.0,
      "location_uncertainty": 5.0,
      "communication_margin": 10.0,
      "safety_margin": 30.0,
      "front_protection_point": 455.0,
      "safe_distance": 165.0,
      "current_speed": 40.0,
      "route_speed_limit": 80.0,
      "required_stop_distance": 108.4,
      "emergency_stop_distance": 98.1,
      "warning_distance": 158.4,
      "braking_curve_speed_limit": 51.8,
      "braking_model": "simplified_atp_braking_curve"
    }
  ]
}
```

### 6. track_info

```json
{
  "line_id": "LINE-1",
  "sections": [
    {
      "section_id": "SEG-01",
      "start": 0.0,
      "end": 500.0,
      "gradient": 0.0,
      "speed_limit": 60.0,
      "station_id": null,
      "stop_position": null
    }
  ]
}
```

### 7. power_state

```json
{
  "substation_id": "SS-01",
  "voltage": 1500.0,
  "current": 300.0,
  "power": 450.0,
  "is_fault": false
}
```

### 8. comm_state

```json
{
  "source": "zmq",
  "driver_console_connected": true,
  "udp_connected": true,
  "zmq_connected": true,
  "latency_ms": 12.5,
  "packet_loss_count": 0,
  "last_message_at": 1720000000.001
}
```

### 9. alarm_event

```json
{
  "alarm_id": "ALM-001",
  "level": "warning",
  "source": "ATP",
  "vehicle_id": "TRAIN-001",
  "message": "Train is close to MA limit"
}
```

说明：

- `message` 可以由模块传英文，data_flow 会对已知告警做中文展示映射。
- 前端看到的 `alarms[].message` 是展示文案。
- 原始英文会保留在 `alarms[].raw_data.message`。

## 六、字段兼容映射

为方便各模块联调，data_flow 会兼容部分别名。

常见别名：

| 输入字段 | 归一化字段 |
|---|---|
| `id` / `train_id` / `vehicleId` | `vehicle_id` |
| `v` / `velocity` | `speed` |
| `km_post` / `kilometerPost` / `pos` | `position` |
| `acc` | `acceleration` |
| `ctrlMode` | `mode` |
| `eb` | `emergency_brake` |
| `routeId` / `route` | `route_id` |
| `limitSpeed` | `speed_limit` |
| `targetVelocity` / `targetSpeed` | `target_speed` |
| `maLimit` / `limit` | `ma_limit` |
| `frontTrainId` | `front_vehicle_id` |
| `safeDistance` | `safe_distance` |
| `distanceToMa` | `distance_to_ma` |
| `brakingCurveSpeedLimit` | `braking_curve_speed_limit` |
| `brakingModel` | `braking_model` |
| `segment_id` | `section_id` |
| `occupiedBy` / `occupied_by` | `occupied_by` |
| `signalState` | `signal_state` |
| `turnoutId` | `turnout_id` |

建议新代码优先使用 snake_case 标准字段。

## 七、数据流说明

```text
车辆 / 信号 / 供电 / 通信模块
        |
        | ZMQ topic
        v
ZmqDashboardListener
        |
        v
DashboardStateStore
        |
        | REST snapshot / WebSocket dashboard
        v
Vue 前端 OCC 大屏
```

`DashboardStateStore` 是内存缓存，不落库。重启后端后历史状态会清空，等待新的 ZMQ 或 mock 数据重新填充。

## 八、联调检查

### 1. 检查 REST snapshot

```bash
curl http://127.0.0.1:8000/api/v1/dashboard/snapshot
```

重点看：

- `system.data_source` 是否是预期的 `mock` 或 `zmq`。
- `system.zmq_connected` 是否为 `true`。
- `trains` 是否有车辆数据。
- `ma_limits` 是否有信号 MA 数据。
- `sections/signals/switches` 是否有信号状态。

### 2. 检查 WebSocket

前端连接：

```text
/ws/dashboard
```

后端日志正常时会出现：

```text
WebSocket /ws/dashboard [accepted]
connection open
```

如果看到 `403`，优先检查：

- 前端 Vite proxy 是否配置 `/ws` 且 `ws: true`。
- 后端是否正常启动。
- 连接地址是否为 `/ws/dashboard`。

### 3. 检查 ZMQ

ZMQ 模式需要先启动 broker：

```bash
python -m app.communication.broker
```

后端启动时设置：

```bash
set DATA_SOURCE=zmq
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

如果 `system.zmq_connected=false`：

- 确认 broker 是否启动。
- 确认 `ZMQ_BROKER_FRONTEND` 默认是 `tcp://127.0.0.1:5555`。
- 确认发布者连接的是 broker backend 地址 `tcp://127.0.0.1:5556`。

## 九、模块边界

`data_flow` 只负责数据接收、归一化、缓存和转发，不负责修改其他模块业务逻辑。

- 多车动力学由车辆算法模块负责。
- 信号 MA / 道岔 / 闭塞逻辑由信号模块负责。
- UDP/司机台解析和 ZMQ 总线由通信模块负责。
- 前端渲染和交互由前端模块负责。

如果某个模块暂时没有真实数据，可以在 `data_flow/mock_service.py` 或模块自己的 mock publisher 中补演示数据，但应避免越界修改其他同学模块。
