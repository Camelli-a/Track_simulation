# 外部 Mock 司机台联调步骤

这套流程把 mock 司机台作为独立进程放在另一个终端里运行，用来模拟外部硬件。

当前外部 mock 司机台通过项目现有 ZMQ 总线持续发布三类消息：

- `driver_input`：司机台按钮、钥匙、方向、ATO 启动、牵引/制动等输入
- `comm_state`：司机台通信在线状态
- `ma_state`：带 `--publish-ma` 时发布单车 demo MA 授权

它验证的是：

- mock 司机台进程能否把消息发进 ZMQ
- `TRAIN-001` 车辆仿真进程能否收到并进入 ATO 前置校验
- 后端 dashboard / 前端能否看到司机台输入和车辆状态

它不等价于真实 PLC 二进制协议验收。二进制 TCP 协议双向收发仍可用 `/driver-desk-sim` 页面做补充检查。

## 一、启动顺序

### 终端 1：启动 ZMQ Broker

```powershell
cd C:\Users\konng\Desktop\Track_simulation\backend
& 'C:\Users\konng\miniconda3\python.exe' -m app.communication.broker
```

原理：所有模块都通过 ZMQ Broker 交换消息，外部 mock 司机台、车辆进程、后端 dashboard 都要连它。

### 终端 2：启动后端 API

推荐先用 `8001`，避免你机器上已有旧后端占用 `8000`。

```powershell
cd C:\Users\konng\Desktop\Track_simulation\backend
$env:DATA_SOURCE='zmq'
& 'C:\Users\konng\miniconda3\python.exe' -m uvicorn main:app --host 127.0.0.1 --port 8001
```

检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/
```

期望看到：

```json
{"status":"ok","data_source":"zmq"}
```

### 终端 3：启动 TRAIN-001 车辆进程

```powershell
cd C:\Users\konng\Desktop\Track_simulation\backend
& 'C:\Users\konng\miniconda3\python.exe' -m app.vehicle_sim.main_integrated --vehicle-id TRAIN-001 --train-index 1 --initial-position 0
```

原理：车辆进程订阅 `driver_input`、`comm_state`、`ma_state`，并根据 `vehicle_id=TRAIN-001` 判断是否处理消息。

### 终端 4：启动外部 mock 司机台

```powershell
cd C:\Users\konng\Desktop\Track_simulation\backend
& 'C:\Users\konng\miniconda3\python.exe' scripts\mock_driver_console.py --vehicle-id TRAIN-001 --mode ato --publish-ma
```

期望持续看到类似日志：

```text
[MockDriverConsole] 已下发driver_input | 周期: 1 | vehicle_id: TRAIN-001 | control_mode: ato | ATO启动按钮: true
[MockDriverConsole] 已下发comm_state | 周期: 1 | 司机台在线: true | ZMQ在线: true
[MockDriverConsole] 已下发demo MA授权 | 周期: 1 | 限速40.0km/h
```

原理：这个进程不在 FastAPI 后端里，它是单独进程，持续以 0.1 秒周期向 ZMQ 发布模拟司机台消息。

### 终端 5：启动前端

```powershell
cd C:\Users\konng\Desktop\Track_simulation\frontend
$env:VITE_PROXY_TARGET='http://127.0.0.1:8001'
npx vite --host 127.0.0.1 --port 5180
```

打开：

```text
http://127.0.0.1:5180/vehicle-status
```

也可以打开：

```text
http://127.0.0.1:5180/driver-desk-sim
```

注意：外部 mock 模式下，不需要在 `/driver-desk-sim` 页面点击“启动本地联调”。那个按钮用于 TCP 二进制协议自检，不是这次外部 ZMQ mock 的启动入口。

如果之前点过“启动本地联调”，先停止它：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8001/api/v1/driver-desk-sim/stop -Body '{}' -ContentType 'application/json'
```

原因：外部 ZMQ mock 和内置 TCP 联调都会给 `TRAIN-001` 写 `driver_input`，同时运行会互相覆盖，测试结论会变混。

## 二、通断检查

### 检查 dashboard 是否收到司机台输入

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8001/api/v1/dashboard/snapshot | ConvertTo-Json -Depth 5
```

重点看：

- `driver_inputs[0].vehicle_id` 应为 `TRAIN-001`
- `driver_inputs[0].control_mode` 应为 `ato`
- `driver_inputs[0].ato_start_btn` 应为 `true`
- `driver_inputs[0].key_switch` 应为 `true`
- `driver_inputs[0].door_closed_light` 应为 `true`
- `ma_limits` 或车辆状态里应能看到 `permission=allow`、`signal_state=green`

### 检查信号状态接口不再 500

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8001/api/v1/signal/status | ConvertTo-Json -Depth 4
```

期望：返回 `lights`、`signals`、`sections`、`switches`、`ma_limits` 字段，而不是 500。

### 保存一次测试记录

```powershell
cd C:\Users\konng\Desktop\Track_simulation
powershell -ExecutionPolicy Bypass -File .\scripts\check_external_mock_driver_console.ps1 -BaseUrl http://127.0.0.1:8001 -VehicleId TRAIN-001
```

重点看：

- `backend.data_source=zmq`
- `dashboard.mock_driver_input_received=True`
- `dashboard.ma_received=True`
- `dashboard.train_visible=True`
- `signal_api.reachable=True`

## 三、异常场景命令

方向手柄不在前进位：

```powershell
cd C:\Users\konng\Desktop\Track_simulation\backend
& 'C:\Users\konng\miniconda3\python.exe' scripts\mock_driver_console.py --vehicle-id TRAIN-001 --mode ato --publish-ma --direction backward
```

钥匙未上电：

```powershell
cd C:\Users\konng\Desktop\Track_simulation\backend
& 'C:\Users\konng\miniconda3\python.exe' scripts\mock_driver_console.py --vehicle-id TRAIN-001 --mode ato --publish-ma --key-switch false
```

车门未关闭：

```powershell
cd C:\Users\konng\Desktop\Track_simulation\backend
& 'C:\Users\konng\miniconda3\python.exe' scripts\mock_driver_console.py --vehicle-id TRAIN-001 --mode ato --publish-ma --door-closed false
```

司机台通信断开：

```powershell
cd C:\Users\konng\Desktop\Track_simulation\backend
& 'C:\Users\konng\miniconda3\python.exe' scripts\mock_driver_console.py --vehicle-id TRAIN-001 --mode ato --publish-ma --driver-console-connected false
```

无 MA 授权：

```powershell
cd C:\Users\konng\Desktop\Track_simulation\backend
& 'C:\Users\konng\miniconda3\python.exe' scripts\mock_driver_console.py --vehicle-id TRAIN-001 --mode ato
```

紧急制动：

```powershell
cd C:\Users\konng\Desktop\Track_simulation\backend
& 'C:\Users\konng\miniconda3\python.exe' scripts\mock_driver_console.py --vehicle-id TRAIN-001 --mode ato --publish-ma --emergency true
```

## 四、单次自测命令

不连 ZMQ，只打印一轮消息：

```powershell
cd C:\Users\konng\Desktop\Track_simulation\backend
& 'C:\Users\konng\miniconda3\python.exe' scripts\mock_driver_console.py --vehicle-id TRAIN-001 --mode ato --publish-ma --cycles 1 --print-only --json-log
```

这个命令用于确认脚本能启动、三类消息结构正确、日志能打印。

## 五、验收标准

通过标准：

- mock 司机台独立终端持续打印三类消息日志
- dashboard 快照里出现 `source=mock_driver_console` 的 `driver_input`
- `TRAIN-001` 车辆进程能收到 `driver_input`、`comm_state`、`ma_state`
- 默认命令带 `--publish-ma` 时，车辆具备进入 AM/ATO 的前置条件
- 去掉 `--publish-ma` 后，车辆不能通过 MA 授权校验
- `/api/v1/signal/status` 不再返回 500

客观限制：

- 这条外部 mock 路径验证的是 ZMQ JSON 消息链路。
- 如果要验证真实司机台 PLC 二进制协议和灯光回写，需要再跑 TCP 协议联调页 `/driver-desk-sim`。
