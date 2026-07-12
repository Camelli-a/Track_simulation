# 前端接入说明

这份文档给前端接入后端实时数据用。主 UI 建议使用 WebSocket 获取实时快照，REST 接口主要用于调试、兜底和少量静态资源加载。

## 本地地址

后端默认地址：

```text
http://localhost:8000
```

前端默认地址：

```text
http://localhost:5173
```

启动后可以先打开后端文档确认服务正常：

```text
http://localhost:8000/docs
```

## 接入优先级

前端主页面建议按下面顺序接入：

1. 先请求静态线路文件 `GET /data/line-layout.json`
2. 再连接实时 WebSocket `ws://localhost:8000/ws/dashboard`
3. 每次收到 `dashboard_snapshot` 后，将动态字段和静态线路几何合并展示
4. `GET /api/v1/dashboard/snapshot` 只作为调试或 WebSocket 断开时的兜底

旧的 REST 子接口，例如 `/api/v1/power/status`、`/api/v1/signal/status`，可以保留，但主 UI 不建议依赖这些零散接口。

## 静态线路数据

请求：

```http
GET http://localhost:8000/data/line-layout.json
```

用途：

- 全线长度：`total_length_m`
- 车站：`stations[]`
- 闭塞分区边界：`blocks[]`
- 信号机静态位置：`signals[]`
- 道岔静态位置：`turnouts[]`
- 电子地图拓扑：`graph.edges[]`
- 坡度图：`slope_profile[]`
- 站台：`platforms[]`

前端合并规则建议：

- `blocks[].segment_id` 对应实时快照里的 `sections[].section_id`
- `blocks[].track_seg_id` 对应实时快照里的 `sections[].track_seg_id`
- `signals[].signal_id` 对应实时快照里的 `signals[].signal_id`
- `turnouts[].switch_id` 对应实时快照里的 `switches[].switch_id`

## WebSocket 实时快照

连接地址：

```text
ws://localhost:8000/ws/dashboard
```

后端会持续推送完整快照，消息类型固定为：

```json
{
  "type": "dashboard_snapshot",
  "protocol_version": "1.0",
  "timestamp": 1720000000.123,
  "system": {},
  "communication": {},
  "trains": [],
  "sections": [],
  "signals": [],
  "switches": [],
  "power": {},
  "alarms": []
}
```

前端收到消息后可以用 `type === "dashboard_snapshot"` 判断。

## 前端推荐状态字段

连接态建议前端自己维护：

```js
const connected = ref(false)
const dataStale = computed(() => Date.now() - lastTickAt.value > 2000)
```

建议逻辑：

- WebSocket `open` 后设置 `connected = true`
- WebSocket `message` 后更新 `lastTickAt`
- 超过 2 秒没有新消息，显示 `dataStale`
- WebSocket `close/error` 后设置 `connected = false`，并延迟重连

## 快照字段说明

### system

| 字段 | 说明 |
|---|---|
| `status` | 系统状态，通常为 `running` |
| `system_mode` | 系统模式，前端 Signal/Dashboard 可展示 |
| `data_source` | 数据源：`mock` / `udp` / `zmq` / `unknown` |
| `zmq_connected` | ZMQ 是否连接 |
| `websocket_clients` | 当前 WebSocket 客户端数量 |

### trains[]

| 字段 | 单位 | 说明 |
|---|---|---|
| `vehicle_id` | - | 车号 |
| `line_id` | - | 线路 ID |
| `position` | m | 里程位置 |
| `speed` | km/h | 当前速度 |
| `acceleration` | m/s^2 | 加速度 |
| `mode` | - | `manual` / `ato` / `atp` / `emergency` / `unknown` |
| `is_running` | bool | 是否运行中 |
| `emergency_brake` | bool | 是否紧急制动 |
| `ma_limit` | m | 移动授权终点 |
| `target_speed` | km/h | 目标限速 |
| `energy_kwh` | kWh | 能耗 |
| `stop_distance` | m | 距下一站停车点距离 |
| `station_name` | - | 下一站/站台名称 |
| `parking_phase` | - | `cruising` / `approaching` / `braking` / `docking` / `stopped` |
| `stop_error_cm` | cm | 对标误差 |
| `platform_id` | - | 站台 ID |

### sections[]

| 字段 | 说明 |
|---|---|
| `section_id` | 闭塞分区 ID |
| `track_seg_id` | 静态拓扑段 ID |
| `start` / `end` | 区段起止里程 |
| `occupied` | 是否占用 |
| `aspect` | 显示色：`red` / `yellow` / `green` / `unknown` |
| `vehicle_id` | 占用车辆 |
| `occupied_by` | 占用车辆，前端可直接用这个字段 |
| `condition` | 区段状态 |

### signals[]

| 字段 | 说明 |
|---|---|
| `signal_id` | 信号机 ID |
| `position` | 里程位置 |
| `state` | 灯色：`red` / `yellow` / `green` / `unknown` |
| `signal_type` | 信号机类型，例如区间、出站、防护 |

### switches[]

| 字段 | 说明 |
|---|---|
| `switch_id` | 后端道岔 ID |
| `turnout_id` | 前端展示用道岔 ID，默认等于 `switch_id` |
| `position` | 当前定/反位 |
| `routing` | 当前定/反位，前端也可用这个字段 |
| `state` | 当前定/反位，前端也可用这个字段 |
| `locked` | 是否锁闭 |
| `related_section` | 关联区段 |

### power

| 字段 | 单位 | 说明 |
|---|---|---|
| `voltage` | V | 接触网电压 |
| `current` | A | 总电流 |
| `power` | kW | 牵引功率 |
| `substation_id` | - | 变电所 ID |
| `is_fault` | bool | 是否供电故障 |

### alarms[]

| 字段 | 说明 |
|---|---|
| `alarm_id` | 告警 ID |
| `level` | `info` / `warning` / `critical` |
| `source` | 告警来源 |
| `vehicle_id` | 关联车辆，可为空 |
| `message` | 告警内容 |
| `timestamp` | 告警时间戳 |

## REST 调试接口

获取一次完整快照：

```http
GET http://localhost:8000/api/v1/dashboard/snapshot
```

用途：

- 前端调试字段结构
- WebSocket 断开后的兜底刷新
- 在浏览器或 Postman 中快速查看当前数据

## WebSocket 示例代码

```js
const ws = new WebSocket('ws://localhost:8000/ws/dashboard')

ws.onopen = () => {
  connected.value = true
}

ws.onmessage = (event) => {
  const tick = JSON.parse(event.data)
  if (tick.type !== 'dashboard_snapshot') return

  lastTickAt.value = Date.now()
  protocolVersion.value = tick.protocol_version
  systemMode.value = tick.system?.system_mode ?? tick.system?.status
  dataSource.value = tick.system?.data_source

  trains.value = tick.trains ?? []
  sections.value = tick.sections ?? []
  signals.value = tick.signals ?? []
  switches.value = tick.switches ?? []
  power.value = tick.power ?? {}
  alarms.value = tick.alarms ?? []
}

ws.onclose = () => {
  connected.value = false
  setTimeout(connectDashboardWs, 1000)
}

ws.onerror = () => {
  connected.value = false
  ws.close()
}
```

## 注意事项

- 主页面不要分别轮询 `power/status`、`track/status`、`signal/status`、`vehicle/status`，否则不同页面的数据时间戳可能不一致。
- `dashboard_snapshot` 是完整快照，不是增量更新；前端可以每次直接覆盖 store。
- 静态线路文件只需要启动时加载一次，后续用实时快照覆盖动态状态。
- 如果 2 秒以上没有收到 WebSocket 消息，前端应显示数据过期状态。
- 开发环境 CORS 默认允许 `http://localhost:5173`。
