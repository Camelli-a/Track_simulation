# 轨道交通仿真系统

前后端分离架构，覆盖供电、车辆、轨道、信号四大子系统。

## 技术栈

| 端 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite + Tailwind CSS + ECharts |
| 后端 | FastAPI + Pydantic v2 |

## 目录结构

```
Track_simulation/
├── frontend/               # Vue 3 前端
│   └── src/
│       ├── api/            # axios 请求封装（power / vehicle / track / signal）
│       ├── stores/         # Pinia 状态管理
│       ├── views/          # 四个子系统页面
│       ├── components/     # 通用组件（StatusCard, EChartsContainer）
│       ├── layouts/        # 页面布局
│       └── router/         # 路由配置
└── backend/                # FastAPI 后端
    ├── main.py
    └── app/
        ├── api/v1/         # 路由 & 端点（power / vehicle / track / signal）
        ├── schemas/        # Pydantic 数据模型
        ├── services/       # 业务逻辑（Mock / UDP / ZMQ 三档切换）
        └── core/           # 配置（config.py）
```

## 快速启动

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
# 访问 http://localhost:8000/docs
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

## 切换数据源

修改 `backend/.env` 中的 `DATA_SOURCE` 字段：

```
DATA_SOURCE=mock   # 当前：Mock 随机数据
DATA_SOURCE=udp    # 切换为 UDP 真实设备
DATA_SOURCE=zmq    # 切换为 ZMQ 真实设备
```

UDP / ZMQ 接入点位于各 `app/services/*_service.py` 的 `elif self.source == "udp"` 分支中。

---

## ZMQ 通信总线

系统内部使用 ZMQ 消息总线实现各子系统（供电/车辆/轨道/信号）之间的消息互联。

### 消息格式

所有消息遵循统一包装格式：

```json
{
  "topic": "train_state",
  "timestamp": 1720000000.123,
  "data": { ...各模块自定义... }
}
```

详细格式规范见 [docs/message-spec.md](docs/message-spec.md)

### 启动 ZMQ Broker

**必须先启动 Broker，才能进行消息通信：**

```bash
cd backend
python -m app.communication.broker
```

### 启动 Mock 数据发布器（可选）

用于测试，定时发送假数据：

```bash
python -m app.communication.mock_publisher
```

### 测试订阅

验证消息流通：

```bash
python -m app.communication.test_subscriber
```

### 在代码中使用

```python
from app.communication.message_bus import MessageBus

bus = MessageBus()
bus.start()

# 发布消息
bus.publish("train_state", {"vehicle_id": "TRAIN-001", "speed": 80})

# 订阅消息
def on_train_state(topic, data):
    print(f"收到: {data}")
bus.subscribe("train_state", on_train_state)

bus.stop()
```

### 支持的消息类型

| topic | 说明 |
|-------|------|
| `train_state` | 车辆运动状态 |
| `signal_state` | 信号灯/区段/道岔状态 |
| `ma_state` | 移动授权边界 |
| `power_state` | 供电系统状态 |
| `comm_state` | 通信连接状态 |
| `alarm_event` | 告警事件 |
