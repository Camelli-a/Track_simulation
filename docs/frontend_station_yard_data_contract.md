# Page 1 站场图前后端数据对接说明

## 结论

当前 `scripts/convert_line_data.py` 已经把 `backend/线路数据(1).xls` 解析成前端 Page 1 站场图所需的主要数据。

已覆盖：

- 13 个站点顺序：`GGZ、FSP、KYL、FTN、FTD、QLZ、LLQ、LLE、BWR、JBG、BDZ、BQS、GTG`
- 每站站场图基础对象：
  - 股道 / track
  - 区段 / section
  - 信号机 / signal
  - 道岔 / switch / turnout
  - 二维绘图坐标 / geometry
- 实时状态叠加所需字段：
  - 区段占用
  - 信号灯色
  - 道岔定位 / 反位 / 锁闭
- 全 workbook 33 个分表原始结构化记录：
  - 每个 sheet 都进入 `workbook_tables`
  - 关键业务表额外进入面向模块消费的派生结构
- 进路、保护区段、接近区段、触发区段、应答器、防淹门、区域属性、限速、安全设备等结构化数据。

需要明确限制：

- 当前二维坐标来自线路拓扑和 Seg 关系推导，不是老师提供的逐站 CAD/联锁图纸坐标。
- 因此现在可以稳定画出站场图，并贴近联锁表示盘风格；但如果要求“每个站和真实站场图纸完全一致”，还需要额外提供每站人工校准的股道、道岔、信号机二维坐标。

## 数据来源

源文件：

```text
backend/线路数据(1).xls
```

转换脚本：

```text
scripts/convert_line_data.py
```

生成文件：

```text
frontend/public/data/line-layout.json
```

当前生成结果规模：

| 数据 | 数量 |
|---|---:|
| stations | 13 |
| platforms | 56 |
| blocks | 386 |
| signals | 157 |
| turnouts | 60 |
| slope_profile | 182 |
| graph.edges | 319 / 319 |
| track_info.sections | 386 |
| signal_state.sections | 386 |
| signal_state.signals | 157 |
| signal_state.switches | 60 |
| yard_layout.stations | 13 |
| yard_layout.yard_tracks | 72 |
| yard_layout.yard_switches | 15 |
| yard_layout.yard_signals | 40 |
| yard_layout.yard_sections | 125 |
| workbook_tables | 33 sheets |
| points | 297 |
| axle_sections | 259 |
| physical_sections | 199 |
| axle_counters | 243 |
| routes | 249 |
| protection_sections | 49 |
| point_approach_sections | 109 |
| cbtc_approach_sections | 112 |
| point_trigger_sections | 109 |
| cbtc_trigger_sections | 112 |
| balises | 374 |
| static_speed_limits | 238 |
| unified_speed_limits | 2 |
| area_attributes | 12 |
| tunnels | 215 |
| device_mappings | 92 |
| collision_zones | 14 |
| platform_screen_doors | 26 |
| emergency_buttons | 26 |
| flood_gates | 4 |
| spks_switches | 56 |
| stop_blocks | 8 |
| garage_doors | 8 |

## 全 workbook 解析结果

`line-layout.json` 现在包含两类数据：

1. 面向 Page 1 站场图和前端显示的稳定结构。
2. 面向信号、联锁、MA、故障注入、设备状态的全量结构化线路底表。

### 1. 原始分表结构化保留

所有 Excel 分表都会进入：

```json
workbook_tables
```

结构：

```json
{
  "进路表": {
    "sheet_name": "进路表",
    "row_count": 249,
    "columns": [],
    "records": []
  }
}
```

用途：

- 保证 33 个分表没有被转换流程丢弃。
- 前端或后端临时缺字段时，可以从 `workbook_tables[sheetName].records` 回查原始结构化记录。
- 后续如果老师又要求某张表新增字段，不需要重新读 Excel，先可以从这里查。

### 2. 模块可直接消费的派生结构

除 `workbook_tables` 外，脚本还生成这些更易用的结构：

| 字段 | 来源分表 | 用途 |
|---|---|---|
| `points` | 点表 | 点位、端点拓扑、区域归属 |
| `axle_sections` | 计轴区段表 | 计轴区段与 Seg 关系 |
| `physical_sections` | 物理区段表 | 物理区段与计轴区段关系 |
| `axle_counters` | 计轴器表 | 计轴器位置 |
| `routes` | 进路表 | 始端/终端信号、计轴区段、保护区段、接近区段、触发区段 |
| `protection_sections` | 保护区段表 | 保护区段包含的计轴区段 |
| `approach_sections.point` | 点式接近区段表 | 点式接近区段包含的计轴区段 |
| `approach_sections.cbtc` | CBTC接近区段表 | CBTC接近区段包含的逻辑区段 |
| `trigger_sections.point` | 点式触发区段表 | 点式触发区段包含的计轴区段 |
| `trigger_sections.cbtc` | CBTC触发区段表 | CBTC触发区段包含的逻辑区段 |
| `balises` | 应答器表 | 应答器位置、属性、关联信号机 |
| `speed_limits.static` | 静态限速表 | 分段限速 |
| `speed_limits.unified` | 线路统一限速信息表 | 统一限速 |
| `gradients.profile` | 坡度表 | 坡度剖面 |
| `gradients.unified` | 线路统一坡度信息表 | 统一坡度 |
| `area_attributes` | 区域属性表 | ZC / CI / ATS 等区域属性 |
| `safety_devices.platform_screen_doors` | 屏蔽门表 | 站台屏蔽门设备 |
| `safety_devices.emergency_buttons` | 紧急按钮表 | 站台紧急按钮 |
| `safety_devices.flood_gates` | 防淹门表 | 防淹门、防护信号、防护区段 |
| `safety_devices.spks_switches` | SPKS开关表 | SPKS 开关位置 |
| `safety_devices.stop_blocks` | 车档表 | 车档位置与类型 |
| `safety_devices.garage_doors` | 车库门表 | 车库门、防护区段、入库/出库进路 |
| `tunnels` | 隧道表 | 隧道区间 |
| `device_mappings` | 设备编号映射表 | 互联互通 ID 映射 |
| `collision_zones` | 碰撞区域表 | 碰撞区、碰撞限速、逻辑区段 |

### 3. 进路数据结构

`routes[]` 示例结构：

```json
{
  "route_id": 1,
  "route_name": "xxx",
  "route_type": 1,
  "start_signal_id": 1,
  "end_signal_id": 2,
  "axle_section_ids": [],
  "protection_section_ids": [],
  "point_approach_section_ids": [],
  "cbtc_approach_section_ids": [],
  "point_trigger_section_ids": [],
  "cbtc_trigger_section_ids": [],
  "ci_area_id": 1,
  "direction": 1
}
```

用途：

- 信号模块可以用它做进路锁闭、冲突判断。
- MA 模块可以用进路包含区段、保护区段、接近区段推导授权终点。
- 前端可以用它展示当前进路所需区段和道岔。

### 4. 应答器数据结构

`balises[]` 示例结构：

```json
{
  "balise_index": 1,
  "balise_id": 101,
  "name": "B001",
  "seg_id": 12,
  "offset_cm": 3456,
  "position_m": 1234.5,
  "attribute": 1,
  "related_signal_id": 10,
  "direction": 1
}
```

用途：

- 车辆/ATP 可以按 `position_m` 做通过应答器事件。
- 信号/联锁可以按 `related_signal_id` 查应答器与信号机关系。

### 5. 安全设备数据结构

安全设备统一放在：

```json
safety_devices
```

包含：

- `platform_screen_doors`
- `emergency_buttons`
- `flood_gates`
- `spks_switches`
- `stop_blocks`
- `garage_doors`

这些数据不是 Page 1 站场图必须项，但对故障注入、防淹门、SPKS、安全边界展示有用。

## Page 1 推荐使用字段

### 1. 站点横向列表

前端 Page 1 上方站点名建议使用：

```json
lineLayout.stations[]
```

关键字段：

| 字段 | 含义 |
|---|---|
| `station_id` | 站点 ID，例如 `ST-01` |
| `name` | 前端显示站名，例如 `GGZ` |
| `station_name` | 同站名，给后端 / yard_layout 兼容 |
| `position` | 线路绝对里程，单位 m |
| `seg_id` | 站点关联 Seg |
| `graph_x` / `graph_y` | 全线拓扑图坐标 |
| `platform_ids` | 车站包含的平台编号 |

当前顺序已经按 `position` 排序，前端可直接渲染。

### 2. 当前站站场图

优先使用：

```json
lineLayout.yard_layout.stations[]
```

根据用户选中的 `station_id` 找到对应站：

```js
const yardStation = lineLayout.yard_layout.stations.find(
  item => item.station_id === selectedStationId
)
```

站场图对象结构：

```json
{
  "station_id": "ST-02",
  "station_name": "FSP",
  "track_ids": [],
  "switch_ids": [],
  "signal_ids": [],
  "section_ids": [],
  "tracks": [],
  "switches": [],
  "signals": [],
  "sections": []
}
```

### 3. 股道 tracks

字段：

| 字段 | 含义 |
|---|---|
| `track_id` | 股道 ID |
| `track_name` | 股道显示名 |
| `station_id` | 所属站 |
| `track_type` | `main` / `arrival_departure` / `siding` / `unknown` |
| `direction` | `up` / `down` |
| `section_ids` | 该股道包含的区段 |
| `geometry` | 绘图几何 |

`geometry` 示例：

```json
{
  "type": "polyline",
  "points": [[0, 280], [120, 280]]
}
```

前端画蓝色轨道时，主要使用 `geometry.points`。

### 4. 区段 sections

字段：

| 字段 | 含义 |
|---|---|
| `section_id` | 区段 ID |
| `station_id` | 所属站 |
| `track_id` | 所属股道 |
| `start` / `end` | 线路绝对里程，单位 m |
| `geometry` | 站场图绘制坐标 |

静态绘制用 `yard_layout.yard_sections` 或站内 `sections`。

动态状态叠加用：

```json
signal_state.sections[]
```

对应字段：

| 字段 | 含义 |
|---|---|
| `section_id` | 与静态 section 对齐 |
| `occupied` | 是否占用 |
| `vehicle_id` / `occupied_by` | 占用车辆 |
| `aspect` | `red` / `yellow` / `green` |
| `locked` | 是否锁闭 |
| `locked_by_route_id` | 锁闭进路 |
| `condition` | 区段状态 |

### 5. 信号机 signals

静态位置：

```json
yard_layout.yard_signals[]
```

字段：

| 字段 | 含义 |
|---|---|
| `signal_id` | 信号机 ID |
| `station_id` | 所属站 |
| `track_id` | 所属股道 |
| `direction` | 防护方向 |
| `protects_switch_id` | 防护道岔 |
| `protects_section_id` | 防护区段 |
| `geometry` | 小圆信号灯绘制坐标 |

动态灯色：

```json
signal_state.signals[]
```

字段：

| 字段 | 含义 |
|---|---|
| `signal_id` | 与静态 signal 对齐 |
| `state` | `red` / `yellow` / `green` / `unknown` |
| `signal_state` | 同 `state` |
| `permission` | `stop` / `restricted` / `allow` |
| `section_id` | 关联区段 |
| `protects_section_id` | 防护区段 |

### 6. 道岔 switches / turnouts

注意：这里必须区分“物理里程位置”和“定位/反位状态”。

前端静态图使用：

```json
lineLayout.turnouts[]
```

或站场图内：

```json
yard_layout.yard_switches[]
```

静态字段：

| 字段 | 含义 |
|---|---|
| `turnout_id` | 静态道岔 ID |
| `switch_id` | 后端状态道岔 ID |
| `position` | 道岔在线路上的里程位置，单位 m |
| `position_m` | 同上，显式单位字段 |
| `merge_seg_id` | 汇合 Seg |
| `normal_seg` | 定位 Seg |
| `reverse_seg` | 反位 Seg |
| `graph_x` / `graph_y` | 绘图坐标 |

动态状态使用：

```json
signal_state.switches[]
```

动态字段：

| 字段 | 含义 |
|---|---|
| `switch_id` | 与静态道岔对齐 |
| `turnout_id` | 静态道岔 ID |
| `position` | `normal` / `reverse` / `unknown` |
| `routing` | `normal` / `reverse` / `unknown` |
| `state` | `normal` / `reverse` / `unknown` |
| `locked` | 是否锁闭 |
| `locked_by_route_id` | 锁闭进路 |
| `related_section` | 关联区段 |

前端不要把 `lineLayout.turnouts[].position` 当成道岔状态。它是米制里程。

## 当前每站数据覆盖情况

| station_id | 站名 | tracks | switches | signals | sections |
|---|---:|---:|---:|---:|---:|
| ST-01 | GGZ | 2 | 0 | 3 | 6 |
| ST-02 | FSP | 6 | 3 | 3 | 10 |
| ST-03 | KYL | 8 | 3 | 6 | 10 |
| ST-04 | FTN | 3 | 0 | 1 | 8 |
| ST-05 | FTD | 3 | 0 | 2 | 9 |
| ST-06 | QLZ | 14 | 7 | 8 | 16 |
| ST-07 | LLQ | 7 | 0 | 3 | 10 |
| ST-08 | LLE | 4 | 0 | 1 | 9 |
| ST-09 | BWR | 6 | 1 | 3 | 9 |
| ST-10 | JBG | 5 | 0 | 2 | 11 |
| ST-11 | BDZ | 5 | 0 | 2 | 10 |
| ST-12 | BQS | 4 | 1 | 2 | 7 |
| ST-13 | GTG | 5 | 0 | 4 | 10 |

说明：

- `switches = 0` 不代表数据错误，只表示当前按线路拓扑和站点窗口归属时，该站没有映射到站内道岔。
- 如果现场确认某站应显示咽喉道岔，但当前为 0，需要补人工站场窗口或道岔归属规则。

## 推荐后端接口形态

如果 Page 1 继续从静态文件读取，可直接使用：

```http
GET /data/line-layout.json
```

如果要求“由后端 API 提供”，建议后端返回同一份转换结果中的 `yard_layout`：

```http
GET /api/v1/dashboard/stations/yards
```

返回结构：

```json
{
  "line_id": "LINE-1",
  "stations": [],
  "yard_tracks": [],
  "yard_switches": [],
  "yard_signals": [],
  "yard_sections": [],
  "updated_at": 1780000000.0
}
```

同时建议后端可以提供或广播：

```json
{
  "topic": "track_info",
  "data": {
    "line_id": "LINE-1",
    "sections": []
  }
}
```

和：

```json
{
  "topic": "signal_state",
  "data": {
    "system_mode": "normal",
    "sections": [],
    "signals": [],
    "switches": [],
    "route_results": []
  }
}
```

这样前端的静态站场图和实时红黄绿 / 道岔锁闭状态可以自然合并。

## 前端合并规则

建议合并顺序：

1. `yard_layout` 提供站场静态几何。
2. `track_info.sections` 提供区段基础属性、坡度、限速、停车点。
3. `signal_state.sections` 覆盖区段占用、锁闭和颜色。
4. `signal_state.signals` 覆盖信号机灯色和许可。
5. `signal_state.switches` 覆盖道岔定位/反位和锁闭。

核心对齐键：

| 静态对象 | 动态对象 | 对齐键 |
|---|---|---|
| `yard_sections[]` | `signal_state.sections[]` | `section_id` |
| `yard_signals[]` | `signal_state.signals[]` | `signal_id` |
| `yard_switches[]` | `signal_state.switches[]` | `switch_id` |
| `turnouts[]` | `signal_state.switches[]` | `switch_id` 或 `turnout_id` |

## 验收标准

当前已满足：

- `stations` 顺序与 13 个站一致。
- 每个站都有可绘制的站场对象。
- `graph.edges` 覆盖全部 319 个 Seg。
- 60 个道岔都有 `graph_x / graph_y`。
- `track_info.sections` 数量与 `blocks` 一致。
- `signal_state.sections / signals / switches` 数量分别与静态对象一致。
- 后端 Pydantic schema 可解析：
  - `YardLayoutSnapshot`
  - `TrackSectionSnapshot`
  - `SignalSnapshot`
  - `SwitchSnapshot`

仍需前后端确认：

- Page 1 最终是读取 `/data/line-layout.json`，还是改为读取 `/api/v1/dashboard/stations/yards`。
- 是否要求真实站场图纸级坐标。如果要求，需要人工补充每站标准站场图坐标，不能只靠拓扑自动推导。
