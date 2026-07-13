# 司机台通信接口说明

---

## 1. 架构概述

```
司机台 PLC ──TCP 下行 46字节/100ms──▶ DriverDeskSource ──▶ ZMQ: driver_input
                                                          ──▶ ZMQ: comm_state

其他模块 ──▶ DriverDeskSource.send_to_plc() ──TCP 上行 28字节──▶ 司机台 PLC
```

- 司机台 PLC 是 TCP Server，上位机主动连接
- PLC 每 100ms 主动推送一帧，上位机被动接收后解析发布到 ZMQ
- 上位机发送无固定周期，由业务模块按需调用

---

## 2. 我的输出（发布到 ZMQ）

### 2.1 driver_input

每收到一帧 PLC 报文发布一次，约 100ms/次。

**topic**：`driver_input`

```json
{
  "topic": "driver_input",
  "timestamp": 1783821594.321,
  "data": {
    "vehicle_id": "TRAIN-001",

    "direction":            "forward",
    "main_handle_raw":      1,
    "traction_level":       2,
    "brake_level":          0,
    "traction_percent":     53,
    "brake_percent":        0,
    "control_mode":         "manual",

    "ato_capable":          false,
    "ato_active":           false,
    "auto_reverse_cap":     false,
    "auto_reverse_active":  false,
    "ato_start_btn":        false,
    "wash_mode_status":     false,

    "emergency_button":     false,
    "bus_ctrl_btn":         false,
    "forced_release":       false,
    "forced_pump":          false,
    "emergency_cmd":        false,
    "parking_apply":        false,
    "parking_release":      false,
    "horn":                 false,

    "open_left_door":       false,
    "open_right_door":      false,
    "close_left_door":      false,
    "close_right_door":     false,
    "door_mode":            "manual",

    "high_voltage_light":   true,
    "brake_bad_light":      false,
    "door_closed_light":    true,
    "network_fault_light":  false,

    "key_switch":           true,
    "high_accel_btn":       false,
    "cab_light_switch":     false,
    "mode_up_confirm":      false,
    "mode_dn_confirm":      false,
    "confirm_flag":         false,
    "auto_rev_flag":        false,
    "trac_aux_reset":       false,
    "wash_mode_switch":     false,
    "vigilance":            false,
    "vigilance_allow":      false,
    "light_switch":         "off"
  }
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `vehicle_id` | string | 列车编号 |
| `direction` | string | 方向手柄：`forward` / `backward` / `neutral` |
| `main_handle_raw` | int | 主手柄原始值：`0`=惰行 `1`=牵引 `2`=制动 `4`=快制 |
| `traction_level` | int | 牵引档位 0~4，由 `traction_percent` 映射 |
| `brake_level` | int | 制动档位 0~7，由 `brake_percent` 映射；快制固定=7 |
| `traction_percent` | int | 牵引极位百分比 0~100 |
| `brake_percent` | int | 制动极位百分比 0~100 |
| `control_mode` | string | `manual` / `ato`，由 `ato_active` 推断 |
| `ato_capable` | bool | 具备ATO模式标志 |
| `ato_active` | bool | 激活ATO模式标志 |
| `auto_reverse_cap` | bool | 具备自动折返模式标志 |
| `auto_reverse_active` | bool | 激活自动折返模式标志 |
| `ato_start_btn` | bool | ATO启动按钮（瞬时触发） |
| `wash_mode_status` | bool | 进入洗车模式（状态，非操作开关） |
| `emergency_button` | bool | 紧急制动按钮，`true`=锁定 |
| `bus_ctrl_btn` | bool | 母线控制按钮 |
| `forced_release` | bool | 强迫缓解（瞬时触发） |
| `forced_pump` | bool | 强迫泵风（瞬时触发） |
| `emergency_cmd` | bool | 应急指挥按钮 |
| `parking_apply` | bool | 停放制动施加（瞬时触发） |
| `parking_release` | bool | 停放制动缓解（瞬时触发） |
| `horn` | bool | 电笛（瞬时触发） |
| `open_left_door` | bool | 开左门（瞬时触发） |
| `open_right_door` | bool | 开右门（瞬时触发） |
| `close_left_door` | bool | 关左门（瞬时触发） |
| `close_right_door` | bool | 关右门（瞬时触发） |
| `door_mode` | string | 门模式：`semi_auto` / `manual` / `auto` |
| `high_voltage_light` | bool | 高断合指示灯状态 |
| `brake_bad_light` | bool | 制动缓解不良指示灯状态 |
| `door_closed_light` | bool | 门关好指示灯状态 |
| `network_fault_light` | bool | 网络故障指示灯状态 |
| `key_switch` | bool | 钥匙开关，`true`=已接通 |
| `high_accel_btn` | bool | 高加速按钮 |
| `cab_light_switch` | bool | 司机室照明开关 |
| `mode_up_confirm` | bool | 模式升级确认（瞬时触发） |
| `mode_dn_confirm` | bool | 模式降级确认（瞬时触发） |
| `confirm_flag` | bool | 确认标志（瞬时触发） |
| `auto_rev_flag` | bool | 自动折返标志（瞬时触发） |
| `trac_aux_reset` | bool | 牵引辅助复位（瞬时触发） |
| `wash_mode_switch` | bool | 洗车模式开关拨位状态 |
| `vigilance` | bool | 警惕标志（瞬时触发） |
| `vigilance_allow` | bool | 警惕允许解除 |
| `light_switch` | string | 外部照明：`off` / `auto` / `low_beam` / `high_beam` |

---

### 2.2 comm_state

每帧发布一次，用于监控 TCP 连接是否在线。

**topic**：`comm_state`

```json
{
  "topic": "comm_state",
  "timestamp": 1783821594.321,
  "data": {
    "source":                   "driver_tcp",
    "driver_console_connected": true,
    "zmq_connected":            true,
    "last_message_at":          1783821594.298
  }
}
```

---

## 3. 我需要的输入（其他模块提供，用于回传给司机台）

其他模块通过调用 `send_to_plc()` 把数据发回给司机台 PLC，驱动司机台上的指示灯显示。

**调用方式：**

```python
from app.communication.driver_desk_source import DriverDeskSource

source.send_to_plc(
    vehicle_speed_kmh   = 45.0,   # 当前实际速度（km/h）
    high_voltage_on     = True,   # 高断合指示灯
    brake_bad_light     = False,  # 制动缓解不良指示灯
    door_open_light     = False,  # 开门灯
    door_closed_light   = True,   # 门关好指示灯
    network_fault       = False,  # 网络故障指示灯
    auto_reverse_cap    = False,  # 具备自动折返模式标志
    ato_capable         = True,   # 具备ATO模式标志
    wash_mode_status    = False,  # 进入洗车模式标志
    ato_active          = True,   # 激活ATO模式标志
    auto_reverse_active = False,  # 激活自动折返模式标志
)
```

**参数说明：**

| 参数 | 类型 | 说明 | 来源模块 |
|------|------|------|----------|
| `vehicle_speed_kmh` | float | 当前实际速度（km/h） | 车辆算法 |
| `high_voltage_on` | bool | 高断合指示灯亮灭 | 车辆算法 |
| `brake_bad_light` | bool | 制动缓解不良指示灯 | 车辆算法 |
| `door_open_light` | bool | 开门灯 | 车辆算法 |
| `door_closed_light` | bool | 门关好指示灯 | 车辆算法 |
| `network_fault` | bool | 网络故障指示灯 | 通信模块 |
| `auto_reverse_cap` | bool | 具备自动折返模式 | ATO/信号模块 |
| `ato_capable` | bool | 具备ATO模式 | ATO/信号模块 |
| `wash_mode_status` | bool | 进入洗车模式 | ATO/信号模块 |
| `ato_active` | bool | 激活ATO模式 | ATO/信号模块 |
| `auto_reverse_active` | bool | 激活自动折返模式 | ATO/信号模块 |

所有参数均有默认值（`False` / `0.0`），未提供的参数按默认值发送。  
建议以 100ms 为周期调用，与 PLC 下行帧对齐。

---

## 4. 已知问题

| 编号 | 问题 | 状态 |
|------|------|------|
| 1 | PLC 实际发来帧头为 `55 AA 55 AA`（0xAA55AA55），与协议文档 7.1 节定义不符，代码已兼容两种帧头 | 待 PLC 方确认 |
| 2 | `verify_type=1, verify_code=7492`，PLC 启用了校验，上位机当前未做校验计算 | 待 PLC 方提供算法 |
| 3 | 发送 `door_open_light=True` 后观察到门关好灯亮 | 需隔离测试确认 bit 偏移 |
| 4 | ATO 激活（`ato_active=True`）后司机台按钮灭 | 需 PLC 方确认激活态预期显示 |

---

## 5. 调试

```cmd
# 只接收，观察司机台操作
python debug_driver_desk.py --no-zmq

# 接收 + 交互式发送
python debug_driver_desk.py --no-zmq --send
```

日志文件保存在 `backend/logs/`：
- `driver_TRAIN-001_*.jsonl`：每帧解析结果（JSON，含全部字段）
- `driver_TRAIN-001_*_raw.txt`：原始字节（`timestamp|hex` 格式）
