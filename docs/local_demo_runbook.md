# TRAIN-001 单车全链路验收启动手册

本文只覆盖明天 `TRAIN-001` 单车、下行、本地联调验收。不要在此流程中扩展多车、上行、反向、对向逻辑。

默认项目路径：

```powershell
D:\大三下\小学期\Track_simulation
```

如果现场路径不同，请把所有命令里的路径替换成实际路径。

## 一、进程总览

### A. 必须启动

| 进程                   | 负责什么                                                                                                               | 输入                                                    | 输出                                                      | 依赖                        | 明天是否必须                                  |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | --------------------------------------------------------- | --------------------------- | --------------------------------------------- |
| ZMQ broker             | XPUB/XSUB 消息总线代理，转发所有 topic                                                                                 | 各模块 PUB 到 `tcp://127.0.0.1:5556`                    | 各模块 SUB 从 `tcp://127.0.0.1:5555` 收                   | 无，必须第一个启动          | 是                                            |
| FastAPI dashboard 后端 | REST/WebSocket dashboard；`DATA_SOURCE=zmq` 时内置 `DriverDeskSource`、`PlcFeedbackAggregator`、ZMQ dashboard listener | ZMQ topic、司机台 PLC TCP、REST 控制                    | dashboard snapshot、WebSocket、driver_input、PLC feedback | broker                      | 是                                            |
| TRAIN-001 车辆进程     | 单车动力学、ATO/ATP、车门状态；发布 `train_state/ato_state/atp_state/door_state`                                       | `driver_input`、`ma_state`、`comm_state`、`power_state` | `train_state` 等 ZMQ topic                                | broker，建议 FastAPI 已启动 | 是，若采用一车一进程演示                      |
| 司机台输入进程         | 真实司机台接入                                                                                                         | PLC TCP 46B/100ms                                       | ZMQ `driver_input`、`comm_state`                          | broker                      | 是，但推荐由 FastAPI 内置启动，不另开独立脚本 |
| 前端                   | 可视化 dashboard                                                                                                       | FastAPI `/api` 和 `/ws`                                 | 浏览器页面                                                | FastAPI                     | 需要展示页面时是                              |

说明：`backend/main.py` 在 `DATA_SOURCE=zmq` 时会自动启动 `DriverDeskSource` 和 `PlcFeedbackAggregator`。因此明天真实司机台联调时，推荐让 FastAPI 负责 PLC 连接，不要同时运行 `debug_driver_desk.py` 抢同一个 PLC 连接。

### B. 按演示需要启动

| 进程                    | 负责什么                                                           | 输入                                    | 输出                                                    | 依赖             | 何时启动                                           |
| ----------------------- | ------------------------------------------------------------------ | --------------------------------------- | ------------------------------------------------------- | ---------------- | -------------------------------------------------- |
| `signal_worker`         | 订阅 `train_state`，计算并发布 `signal_state/ma_state/ato_command` | `train_state`、`route_request`          | `signal_state`、`ma_state`、`ato_command`               | broker，车辆进程 | 要展示实时 MA/signal_state 时启动                  |
| `station_stop_scenario` | 发布最小 AM 到站停车 demo 输入                                     | 无外部输入                              | `driver_input`、`ma_state`、`comm_state`、`power_state` | broker，车辆进程 | 无真实司机台或不用 `signal_worker` 时用于单车 demo |
| `vehicle_flow_observer` | 观察一辆车的 ZMQ 流程摘要                                          | ZMQ topics                              | 控制台摘要，可写 jsonl                                  | broker           | 调试推荐启动                                       |
| 外部视觉系统            | 消费后端输出的车辆位置                                             | dashboard snapshot 或 ZMQ `train_state` | 三维显示                                                | FastAPI 或 ZMQ   | 需要联调三维视景时启动                             |
| `debug_scenery.py`      | 手动发 UDP 给视景系统                                              | 控制台命令                              | UDP 8302 -> 8303                                        | 视觉系统网络     | 仅手动硬件排查，不是自动车辆链路                   |

### C. 当前不要启动

| 进程/做法                                          | 原因                                                                                    |
| -------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 多个 `signal_worker`                               | 会重复发布 `ma_state/signal_state/ato_command`                                          |
| `mock_publisher` 与 `signal_worker` 同时跑         | `mock_publisher` 也会随机发布 `ma_state/signal_state`，会混入真实链路                   |
| 多辆车 `TRAIN-002/003`                             | 明天验收先限定 `TRAIN-001` 单车                                                         |
| 上行/反向/对向相关脚本或配置                       | 当前视景映射固定下行、`track=0`                                                         |
| `debug_driver_desk.py` 与 FastAPI 同时连接真实 PLC | 两个 TCP 客户端可能抢同一司机台连接，导致连接时好时坏                                   |
| 手动视景脚本当作自动适配器                         | `debug_scenery.py/manual_scenery_control.py` 是手动调试脚本，不会自动订阅 `train_state` |

## 二、是否需要 ZMQ broker

当前项目需要单独启动 ZMQ broker。

证据：

- `backend/app/communication/broker.py` 是 XPUB/XSUB 代理，`frontend` XPUB 默认 `tcp://127.0.0.1:5555`，`backend` XSUB 默认 `tcp://127.0.0.1:5556`。
- `backend/app/communication/message_bus.py` 的 publisher 连接 `ZMQ_BROKER_BACKEND`，subscriber 连接 `ZMQ_BROKER_FRONTEND`。
- `backend/app/data_flow/zmq_listener.py` 订阅 `ZMQ_BROKER_FRONTEND`。
- `backend/COMMUNICATION_QUICKSTART.md` 和 `README.md` 都写明先启动 `python -m app.communication.broker`。

真实命令：

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe -m app.communication.broker
```

## 三、推荐启动顺序

### 推荐路径：真实司机台 + 独立 TRAIN-001 车辆进程

终端 1：ZMQ broker  
终端 2：FastAPI dashboard 后端，负责 dashboard、真实司机台接入、PLC 回传  
终端 3：`signal_worker`，如果要使用实时 MA/signal_state  
终端 4：`TRAIN-001` 车辆进程  
终端 5：前端  
终端 6：dashboard 查询 / ZMQ observer  
终端 7：外部视觉系统或手动视景调试，可选

### 无真实司机台的单车到站 demo

终端 1：ZMQ broker  
终端 2：FastAPI dashboard 后端  
终端 3：`TRAIN-001` 车辆进程  
终端 4：`station_stop_scenario` 发布 demo `driver_input/ma_state`  
终端 5：前端  
终端 6：dashboard 查询 / ZMQ observer

注意：使用 `station_stop_scenario` 时，不要同时启动 `signal_worker`，否则两个来源都会发布 `ma_state`。

## 四、每个终端命令

### 终端 1：ZMQ broker

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe -m app.communication.broker
```

成功特征：

```text
Starting ZMQ Broker...
Frontend (XPUB): tcp://127.0.0.1:5555
Backend  (XSUB): tcp://127.0.0.1:5556
Broker is running...
```

### 终端 2：FastAPI dashboard 后端

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

检查地址：

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/api/v1/dashboard/snapshot
```

`DATA_SOURCE=zmq` 时，`main.py` 会启动：

- `ZmqDashboardListener`
- `MessageBus`
- `DriverDeskSource(vehicle_id="TRAIN-001")`
- `PlcFeedbackAggregator`
- 内置 `SimulationLoop`

如果采用独立 `main_integrated` 车辆进程，FastAPI 仍可负责司机台输入和 dashboard；不要再额外运行 `debug_driver_desk.py` 连接同一个 PLC。

### 终端 3：signal_worker，可选

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe -m app.communication.signal_worker
```

职责：

- 订阅 `train_state`
- 计算并发布 `signal_state`
- 计算并发布 `ma_state`
- 发布 `ato_command`

建议：

- 要展示真实信号 MA/signal_state：启动。
- 只跑 `station_stop_scenario` 单车停车 demo：不要启动。
- 只能启动一个。

### 终端 4：TRAIN-001 车辆进程

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe -m app.vehicle_sim.main_integrated --vehicle-id TRAIN-001 --train-index 1 --initial-position 0 --dt 0.1
```

说明：

- 车辆进程启动后只是 `TRAIN-001` 上线待命。
- 是否发车取决于 `driver_input`、ATO 启动按钮、precheck、MA/stop target。
- 车辆进程发布 `train_state/ato_state/atp_state/door_state`。
- 车辆进程订阅 `driver_input/ma_state/signal_state/comm_state/power_state` 等 topic。

### 终端 4B：无真实司机台时的 demo 输入，可选

项目中没有找到 `backend/scripts/mock_driver_console.py`，也没有 `scripts` 目录下的司机台 mock。当前可用的单车 demo 输入脚本是：

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe -m app.communication.station_stop_scenario --vehicle-id TRAIN-001 --ma-limit 500 --allowed-speed 45 --stop-target 313 --duration 60 --dt 0.1
```

它会发布：

- `driver_input`
- `ma_state`
- `comm_state`
- `power_state`

不要和 `signal_worker` 同时用于同一个 demo，避免 `ma_state` 冲突。

### 终端 5：真实司机台接入

推荐方式：由终端 2 的 FastAPI 自动接入。

配置来自 `backend/app/core/config.py` 和 `backend/.env`：

```text
PLC_HOST=192.168.100.123
PLC_PORT=8001
vehicle_id=TRAIN-001
```

独立调试脚本存在：

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe debug_driver_desk.py --host 192.168.100.123 --port 8001
```

但它用于单独排查 PLC 接收/发送，不建议与 FastAPI 同时连接真实司机台。当前工作区版本的 `debug_driver_desk.py` 没有 `--auto-feedback` 参数。

### 终端 6：前端

```powershell
cd D:\大三下\小学期\Track_simulation\frontend
npm install
npm run dev
```

Vite 配置端口为：

```text
http://localhost:5173
```

前端代理：

- `/api` -> `http://127.0.0.1:8000`
- `/ws` -> `ws://127.0.0.1:8000`

### 终端 7：ZMQ 单车观察器，可选但推荐

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe -m app.communication.vehicle_flow_observer --vehicle-id TRAIN-001 --sample-interval 1 --only-changes
```

如果要看原始 payload：

```powershell
.\.venv\Scripts\python.exe -m app.communication.vehicle_flow_observer --vehicle-id TRAIN-001 --raw --topics train_state,ato_state,door_state,ma_state,driver_input
```

### 终端 8：视觉/3D

未找到正式的自动 `train_state -> ScenerySource UDP` 独立启动入口。

当前后端对外 `train_state` / dashboard payload 已包含：

- `vehicle_id`
- `position_m`
- `speed_mps`
- `direction`
- `edge_id`
- `edge_offset_m`
- `viewer_position_m`
- `line_id`

视觉系统可以从 dashboard snapshot 或 ZMQ `train_state` 读取这些字段。

手动 UDP 调试脚本存在，但仅用于手动排查，不是自动联动：

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe debug_scenery.py --host 18.32.115.28 --port 8303
```

## 五、配置检查

启动前检查 `backend/.env` 和 `backend/app/core/config.py`。

当前关键项：

```text
DATA_SOURCE=zmq
ZMQ_BROKER_FRONTEND=tcp://127.0.0.1:5555
ZMQ_BROKER_BACKEND=tcp://127.0.0.1:5556
ZMQ_ADDRESS=tcp://localhost:5555
PLC_HOST=192.168.100.123
PLC_PORT=8001
VISUAL_TRACK=0
VISUAL_DIRECTION_NAME=down
SCENERY_SECTION_DIRECTION=-1
SIGNAL_COORD_OFFSET_M=216.46
VIEWER_ABS_OFFSET_M=4028.28
```

注意：

- `backend/.env` 当前看到 `DATA_SOURCE=zmq` 和 `ZMQ_ADDRESS=tcp://localhost:5555`。
- `ZMQ_BROKER_FRONTEND/BACKEND` 若 `.env` 未写，则使用 `config.py` 默认值。
- 司机台默认绑定 `TRAIN-001`，见 `main.py` 和 `debug_driver_desk.py`。
- 端口占用重点检查：`8000`、`5173`、`5555`、`5556`、`8001`、视景 UDP `8302/8303`。

## 六、成功判据

### 1. FastAPI 成功

- `http://127.0.0.1:8000/docs` 能打开。
- `http://127.0.0.1:8000/api/v1/dashboard/snapshot` 返回 JSON。

### 2. ZMQ broker 成功

- broker 进程无报错。
- FastAPI、车辆进程、signal_worker、observer 日志能看到连接到 `5555/5556`。
- 没有端口冲突。

### 3. TRAIN-001 上线成功

dashboard snapshot 中能看到：

- `vehicle_id=TRAIN-001`
- `position_m` 有值
- `speed_mps/speed_kmh` 有值
- `edge_id` 在 `1..48`
- `viewer_position_m` 有值

### 4. 司机台输入成功

- FastAPI 日志或 observer 能看到 `driver_input`。
- dashboard 中 `driver_input/input_lights` 相关字段变化。
- 重点字段正确：`ato_start_btn`、`direction`、`key_switch`、`door_closed_light`、`main_handle_raw`、`brake_level`。

### 5. ATO 启动成功

- `ato_start_btn=true`
- `precheck.can_start_ato=true` 或 `required_actions` 为空
- `driving_mode=AM`
- `ato_active=true`
- `control_source=ato`
- `ato_guidance.control_authority=control`
- `ato_guidance.action_text` 显示 ATO 自动驾驶中或类似含义

### 6. 车辆运动成功

- `applied_traction_level/applied_brake_level` 有变化。
- `speed_kmh` 从 0 增加。
- `position_m` 持续增加。

### 7. 自动停车成功

- `distance_to_stop_m` 或 `distance_to_stop` 逐渐减小。
- 接近站点后 `applied_brake_level` 增加。
- `speed_kmh` 降到 0。
- `door_state` 从 `closed` 到 `open`。
- dwell 后 `door_state` 从 `open` 到 `closed`。
- 后续停车目标切到下一站；字段可能表现为 `stop_target` 或 `ato_state.stop_target_m`，当前代码未在 `train_state` 顶层固定输出 `next_stop_target_m`。

### 8. 视觉字段成功

- `edge_id` 不为 null。
- `edge_id <= 48`。
- `edge_offset_m` 不为 null。
- `viewer_position_m` 有值。
- `position_m` 和 `viewer_position_m` 同时保留。

## 七、dashboard 查询命令

```powershell
cd D:\大三下\小学期\Track_simulation\backend

$r = Invoke-RestMethod http://127.0.0.1:8000/api/v1/dashboard/snapshot
$r.trains | Where-Object {$_.vehicle_id -eq "TRAIN-001"} | ConvertTo-Json -Depth 30
```

关键字段版本：

```powershell
$r = Invoke-RestMethod http://127.0.0.1:8000/api/v1/dashboard/snapshot
$t = ($r.trains | Where-Object {$_.vehicle_id -eq "TRAIN-001"})

$t.vehicle_id
$t.position_m
$t.speed_kmh
$t.speed_mps
$t.edge_id
$t.edge_offset_m
$t.viewer_position_m
$t.ato_guidance
$t.input_lights
$t.output_lights
$t.plc_feedback
$t.door_state
```

如果 `$t` 为空，说明 dashboard 还没有收到或登记 `TRAIN-001`。

## 八、常见问题排查

### 1. FastAPI 启动失败

- 确认在 `backend` 目录。
- 确认使用 `.\.venv\Scripts\python.exe`。
- 检查 `8000` 端口是否占用。

### 2. broker 端口占用

- 检查是否重复启动 broker。
- 检查 `5555/5556` 是否被其他进程占用。
- broker 必须先于 ZMQ 发布/订阅进程启动。

### 3. dashboard 没有 TRAIN-001

- 检查车辆进程是否启动。
- 检查 `DATA_SOURCE=zmq`。
- 检查 broker 是否运行。
- 检查车辆进程是否连接到 broker 并持续打印/发布 `train_state`。

### 4. 前端有司机台变化但车不动

- `driver_input` 可能只进了 dashboard，没进 `TRAIN-001` 车辆进程。
- 看车辆进程日志或 `vehicle_flow_observer` 是否收到 `driver_input`。
- 不要同时用两个进程连接真实 PLC。

### 5. 车上线但不跑

检查：

- `ato_start_btn`
- `direction` 是否 `forward`
- `key_switch`
- `door_closed_light`
- `main_handle_raw` 是否安全位
- `brake_level` 是否为 0
- `emergency_button/emergency_cmd`
- `parking_apply/parking_release`
- `ma_state/stop_target`

### 6. ATO 一直 degraded

检查：

- `comm_state`
- `ma_state`
- `ato_guidance.precheck.required_actions`
- `driver_console_connected`
- `zmq_connected`

### 7. edge_id 超过 48

说明误用了内部 `LinkId/track_seg_id/section_id`，不是视景边号。应使用 `backend/app/data_flow/visual_edges_down.json` 中的视景边号。

### 8. edge_id 为 null

- 检查 `position_m` 是否落在下行视景边号表范围内。
- 检查 `backend/app/data_flow/visual_edges_down.json` 是否存在并可加载。
- 当前位置如果越界，代码会返回 `edge_id=null` 并记录 warning。

### 9. ma_state 冲突

- 不要同时启动多个 `signal_worker`。
- 不要同时让 `mock_publisher`、`station_stop_scenario`、`signal_worker` 都发布同一辆车的 `ma_state`。
- 当前 `signal_worker` 发布的 `ma_state` 是 `ma_limits[]` 批量结构。

## 九、不要做的事

明天 `TRAIN-001` 单车演示阶段，不要：

- 启动多个 `signal_worker`
- 同时用多个脚本发布 `ma_state`
- 启动 `TRAIN-002/003`，除非明确要展示多车
- 改上行/反向/对向逻辑
- 改 `dynamics.py`
- 改 `atp.py`
- 改 ATO 停车点
- 把 `LinkId` 当视景 `edge_id`
- 把 `viewer_position_m` 用于控车
- 同时用 FastAPI 和 `debug_driver_desk.py` 连接同一个真实司机台 PLC

## 自动错峰发车模式

这个模式用于明天的 TRAIN-001 单车为主、附带虚拟车错峰发车演示。它会按顺序启动多个独立车辆进程；每辆车仍然从 `position_m=0` 上线。launcher 只负责启动进程和观察上一辆车是否离开起点，不负责控车。

终端 1：broker

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe -m app.communication.broker
```

终端 2：FastAPI dashboard 后端

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

终端 3：signal_worker

如果展示真实 MA / `signal_state`，启动：

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe -m app.communication.signal_worker
```

如果使用 demo MA 或 `station_stop_scenario`，不要同时启动 `signal_worker`，避免同一辆车收到冲突的 `ma_state`。

终端 4：手动启动 TRAIN-001 车辆进程

`TRAIN-001` 是硬件绑定车，必须单独启动，并等待真实司机台状态、ATO 按钮和 precheck 通过后才运行。launcher 不启动 `TRAIN-001`。

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe -m app.vehicle_sim.main_integrated --vehicle-id TRAIN-001 --train-index 1 --initial-position 0 --dt 0.1
```

终端 5：auto_departure_launcher

launcher 只监控 `TRAIN-001`，并从 `TRAIN-002` 开始自动错峰启动后续 virtual ATO 车辆。

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe scripts\auto_departure_launcher.py --anchor-vehicle-id TRAIN-001 --launch-from-index 2 --max-index 3 --initial-position 0 --clear-distance 200 --dt 0.1 --poll-interval 1.0
```

### 终端 4B：无真实司机台时的 demo 输入，可选

项目中没有找到 `backend/scripts/mock_driver_console.py`，也没有 `scripts` 目录下的司机台 mock。当前可用的单车 demo 输入脚本是：

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe -m app.communication.station_stop_scenario --vehicle-id TRAIN-001 --ma-limit 500 --allowed-speed 45 --stop-target 313 --duration 60 --dt 0.1
```

它会发布：

- `driver_input`
- `ma_state`
- `comm_state`
- `power_state`

不要和 `signal_worker` 同时用于同一个 demo，避免 `ma_state` 冲突。

### 终端 5：真实司机台接入

推荐方式：由终端 2 的 FastAPI 自动接入。

配置来自 `backend/app/core/config.py` 和 `backend/.env`：

```text
PLC_HOST=192.168.100.123
PLC_PORT=8001
vehicle_id=TRAIN-001
```

独立调试脚本存在：

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe debug_driver_desk.py --host 192.168.100.123 --port 8001
```

但它用于单独排查 PLC 接收/发送，不建议与 FastAPI 同时连接真实司机台。当前工作区版本的 `debug_driver_desk.py` 没有 `--auto-feedback` 参数。

终端 6：前端

```powershell
cd D:\大三下\小学期\Track_simulation\frontend
npm run dev
```

### 终端 8：视觉/3D

未找到正式的自动 `train_state -> ScenerySource UDP` 独立启动入口。

当前后端对外 `train_state` / dashboard payload 已包含：

- `vehicle_id`
- `position_m`
- `speed_mps`
- `direction`
- `edge_id`
- `edge_offset_m`
- `viewer_position_m`
- `line_id`

视觉系统可以从 dashboard snapshot 或 ZMQ `train_state` 读取这些字段。

手动 UDP 调试脚本存在，但仅用于手动排查，不是自动联动：

````powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe debug_scenery.py --host 18.32.115.28 --port 8303

终端 7：dashboard 查询

```powershell
$r = Invoke-RestMethod http://127.0.0.1:8000/api/v1/dashboard/snapshot
$r.trains | Where-Object {$_.vehicle_id -like "TRAIN-*"} | Select-Object vehicle_id, position_m, speed_kmh, edge_id, viewer_position_m, door_state
````

说明：

- `auto_departure_launcher` 不启动 `TRAIN-001`。
- `TRAIN-001` 由终端 4 单独手动启动，上线后仍然需要真实司机台状态和 ATO 按钮才会移动。
- 前端普通“添加车辆”只创建/启动车辆进程，不会自动进入 virtual ATO；需要自动错峰时使用本节 launcher 命令。
- launcher 只监控 `TRAIN-001.position_m`。
- 当 `TRAIN-001.position_m >= clear-distance`，例如 `200m`，launcher 才启动 `TRAIN-002`。
- `TRAIN-002` 是 virtual ATO，不需要真实司机台。
- 当 `TRAIN-002` 离开起点后，launcher 启动 `TRAIN-003`。
- 明天现场推荐先把 `--max-index 2`，确认稳定后再改成 `--max-index 3`。
- launcher 有演示安全上限，`--max-index` 最大为 `5`。
- 所有车都从 `initial-position=0` 启动。
- launcher 不发布 `driver_input`、`ma_state`、`ato_command`，不会和 `signal_worker` 或 demo MA 脚本抢 `ma_state`。
- 这个 launcher 只是演示级发车器，不是完整运行图调度系统。
