# 视景边号映射说明

## 当前验收范围

当前明天验收只按单车场景处理：

- 车辆：`TRAIN-001`
- 方向：下行
- 视景 `track`：`0`
- 视景方向名：`down`

后续如果要扩展上行或多车，需要按车辆方向选择上行/下行边号表，并增加多车视景发送调度。

## 坐标分离

`position_m` 是车辆/ATO 内部线路坐标，用于动力学、ATO、ATP、停车点和 MA 判断。不要为了视景系统修改 `Train.position_m`、`stop_target_m` 或 ATO 停车点。

`viewer_position_m` 是三维视景显示坐标，只用于展示和视景发送：

```text
viewer_position_m = position_m + SIGNAL_COORD_OFFSET_M + VIEWER_ABS_OFFSET_M
```

当前配置为：

- `SIGNAL_COORD_OFFSET_M = 216.46`
- `VIEWER_ABS_OFFSET_M = 4028.28`

也就是：

```text
viewer_position_m = position_m + 4244.74
```

## edge_id 来源

三维视景系统需要的 `edge_id` 来自《视景系统公里标最新数据+站台位置20260703.xlsx》的 sheet：

```text
下行连接次序数据
```

读取列：

- `视景边号`
- `起始公里标（m）`
- `终点公里标（m）`
- `长度（m）`

注意：`LinkId`、计轴区段号、内部 `track_seg_id` 都不能作为三维视景 `edge_id`。当前下行视景边号表已固化到：

```text
backend/app/data_flow/visual_edges_down.json
```

## 运行时映射

对每个 `train_state.position_m`：

1. 在下行视景边号表中查找 `start_m <= position_m <= end_m` 的边。
2. `edge_id = 该行视景边号`。
3. `edge_offset_m = position_m - start_m`。
4. `viewer_position_m = position_m + 216.46 + 4028.28`。
5. 找不到边时输出 `edge_id = null`、`edge_offset_m = null`，并记录 warning，不中断仿真。

示例：

```json
{
  "vehicle_id": "TRAIN-001",
  "track": 0,
  "direction": 1,
  "direction_name": "down",
  "position_m": 2448.61,
  "speed_mps": 0.0,
  "edge_id": 17,
  "edge_offset_m": 1937.42,
  "viewer_position_m": 6693.35,
  "line_id": "LINE-1"
}
```

这里 `edge_id=17` 来自视景边号表，不是 LinkId。
