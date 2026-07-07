# ZMQ 通信总线 - 快速测试指南

## 测试流程

### 1. 启动 ZMQ Broker（必须）

**打开终端 1**，运行：

```bash
cd d:\myGithub\Track_simulation\backend
.venv\Scripts\activate
python -m app.communication.broker
```

应该看到：

```
[INFO] Starting ZMQ Broker...
[INFO]   Frontend (XPUB): tcp://127.0.0.1:5555
[INFO]   Backend  (XSUB): tcp://127.0.0.1:5556
[INFO] Broker is running...
```

**保持这个终端运行，不要关闭。**

---

### 2. 启动 Mock 数据发布器

**打开终端 2**，运行：

```bash
cd d:\myGithub\Track_simulation\backend
.venv\Scripts\activate
python -m app.communication.mock_publisher
```

应该看到：

```
[INFO] MessageBus publisher connected: tcp://127.0.0.1:5556
[INFO] MessageBus subscriber connected: tcp://127.0.0.1:5555
[INFO] MockPublisher started (interval=1.0s)
```

Mock 发布器会每秒发送一组消息（车辆、信号、供电等）。

---

### 3. 启动测试订阅器

**打开终端 3**，运行：

```bash
cd d:\myGithub\Track_simulation\backend
.venv\Scripts\activate
python -m app.communication.test_subscriber
```

应该看到：

```
[INFO] Subscribed to topic: train_state
[INFO] Subscribed to topic: signal_state
...
[INFO] Test subscriber started, press Ctrl+C to stop
[INFO] [train_state] {'vehicle_id': 'TRAIN-001', 'speed': 62.4, ...}
[INFO] [signal_state] {'system_mode': 'normal', 'signals': [...], ...}
...
```

说明消息流通成功！

---

## 验证要点

✅ **Broker 正常启动** — 看到 "Broker is running"  
✅ **发布器连接成功** — 看到 "connected"  
✅ **订阅器收到消息** — 持续打印消息内容

---

## 故障排查

### 问题：订阅器收不到消息

**原因**：Broker 未启动，或端口被占用

**解决**：
1. 检查 Broker 是否在运行
2. 检查端口 5555 / 5556 是否被占用：`netstat -ano | findstr 5555`
3. 修改 `.env` 里的端口配置

### 问题：Import 错误

**原因**：虚拟环境未激活，或缺少依赖

**解决**：
```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## 下一步

- 阅读 [docs/message-spec.md](../docs/message-spec.md) 了解消息格式
- 在你的模块中引入 `MessageBus` 类进行发布/订阅
- 联系车辆/信号/供电同学确认各自的 data 字段格式
