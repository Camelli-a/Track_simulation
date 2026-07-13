# ATO Stop Position Mapping

当前 TRAIN-001 单车下行验收中，ATO 停车点使用车辆内部线路坐标 `position_m`，不使用三维视景坐标 `viewer_position_m`。

## 数据链路

ATO 停车点来源：

1. `frontend/public/data/line-layout.json`
2. `backend/app/vehicle_sim/line_data_loader.py::build_track_map_from_line_layout()`
3. `TrackSection.stop_position`
4. `Train._track_stop_positions()` / `Train._resolve_stop_target_m()`

`viewer_position_m` 只用于 dashboard / 3D 视景显示，不参与 ATO 控车、停车、MA、动力学计算。

## 当前规则

- 只有 `station_id` 非空且 `stop_position` 非空的 section 才参与自动停站。
- `station_id=null` 的 `stop_position` 被视为非站台停车点或可疑数据，不作为站台停车目标。
- `2DG-A` 上的 `11424.2m` 没有站点归属，不参与 ATO 停站。
- ST-03 已补内部停车点 `2448.6m`，位于 `11DG-B` section。

## 正确停车点序列

| Station | stop_position_m |
| --- | ---: |
| ST-01 | 313.0 |
| ST-02 | 1660.5 |
| ST-03 | 2448.6 |
| ST-04 | 3429.3 |
| ST-05 | 5014.5 |
| ST-06 | 6339.9 |
| ST-07 | 8118.8 |
| ST-08 | 9429.2 |
| ST-09 | 10598.7 |
| ST-10 | 11997.0 |
| ST-11 | 13906.8 |
| ST-12 | 14954.0 |
| ST-13 | 16048.9 |

## 检查命令

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe scripts\inspect_stop_positions.py
```

输出中的 `ATO usable stop sequence` 不应包含 `11424.2m`，并应包含 ST-01 到 ST-13 的 13 个停车点。
