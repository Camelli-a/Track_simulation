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
DATA_SOURCE=zmq
ENABLE_DASHBOARD_MOCK=false
ENABLE_ZMQ_DASHBOARD_LISTENER=true
```

当前架构中，ZMQ 是系统内部统一总线，不是可选“模式”。`DATA_SOURCE`
只保留为兼容字段和状态显示；是否生成演示数据由
`ENABLE_DASHBOARD_MOCK` 控制。真实联调时保持 mock 关闭，由车辆、信号、
司机台等模块向 ZMQ 发布真实 `train_state` / `ma_state` / `signal_state`
等消息，后端 `data_flow` 订阅并写入 `state_store`，前端只消费统一的
`dashboard_snapshot`。

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


---

## 项目管理

### 项目生命周期

本项目采用**分阶段交付**的生命周期模型，分为两个主要阶段：

#### 第一阶段：软件仿真阶段
- **时间**：2024年X月 - 2024年Y月
- **主要目标**：完成软件架构搭建、核心算法验证、UI界面开发
- **工作范围**：
  - FastAPI后端架构设计
  - Vue3前端界面开发
  - ZMQ消息总线实现
  - 车辆动力学仿真、信号控制、供电系统仿真算法
  - 纯软件环境下的系统联调
- **交付成果**：可独立运行的完整软件仿真系统

#### 第二阶段：硬件集成阶段
- **时间**：2024年Y月 - 2024年Z月
- **主要目标**：与实际硬件设备对接联调
- **工作范围**：
  - 司机台PLC接口对接
  - 信号设备硬件通信
  - 视景系统集成
  - 硬件适配层开发
  - 真实环境下的全系统测试
- **交付成果**：软硬件协同工作的完整轨道交通仿真系统

### 团队组成与管理

#### 团队结构（5人）
1. **项目负责人**：总体协调、需求分析、进度跟踪
2. **后端开发**（2人）：FastAPI架构、ZMQ通信、算法实现
3. **前端开发**：Vue3界面、数据可视化、用户体验
4. **测试与集成**：系统联调、硬件对接、测试验证

#### 风险管理与应急响应
项目执行期间遇到**团队成员生病**的不可预见风险，采取了以下应急措施：
- **资源再分配**：紧急调整任务安排，确保关键路径工作不受影响
- **工作负载平衡**：将受影响成员的工作合理分配给其他团队成员
- **进度缓冲利用**：充分利用项目计划中的缓冲时间，确保整体进度目标
- **沟通强化**：加强每日站会，确保信息同步和问题及时解决

### 版本控制策略

本项目采用GitFlow工作流，使用GitHub进行版本控制：

#### 分支策略
```
main (稳定版本)
├── develop (开发主分支)
│   ├── feature/* (功能分支)
│   ├── bugfix/* (修复分支)
│   └── release/* (发布分支)
└── hotfix/* (紧急修复分支)
```

#### 开发流程
1. **功能开发**：从`develop`分支创建`feature/xxx`分支，开发完成后通过Pull Request合并到`develop`
2. **Bug修复**：从`develop`分支创建`bugfix/xxx`分支，修复完成后合并到`develop`
3. **版本发布**：从`develop`分支创建`release/v1.x`分支，进行测试和文档完善，稳定后合并到`main`和`develop`
4. **紧急修复**：从`main`分支创建`hotfix/xxx`分支，修复完成后合并到`main`和`develop`

#### 提交规范
- feat: 新功能
- fix: Bug修复
- docs: 文档更新
- style: 代码格式调整
- refactor: 代码重构
- test: 测试相关
- chore: 构建过程或辅助工具变动

### 质量保证

1. **代码审查**：所有Pull Request必须经过至少一名团队成员审查
2. **自动化测试**：关键模块配备单元测试和集成测试
3. **持续集成**：GitHub Actions实现自动化构建和测试
4. **文档维护**：代码注释、API文档、用户手册同步更新

### 沟通机制

1. **每日站会**：15分钟同步进度、问题和计划
2. **周度评审**：回顾进展、调整计划、风险识别
3. **技术分享**：定期分享技术难点和解决方案
4. **文档协同**：使用Markdown文档和代码注释保持知识传承