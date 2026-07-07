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
