# ATO Stop Position Mapping

当前 TRAIN-001 单车下行验收中，ATO 停车点仍使用车辆内部线路坐标 `position_m`，不使用三维视景坐标 `viewer_position_m`。

## 数据链路

ATO 停车点来源：

1. `frontend/public/data/line-layout.json`
2. `backend/app/vehicle_sim/line_data_loader.py::build_track_map_from_line_layout()`
3. `TrackSection.stop_position`
4. `Train._track_stop_positions()` / `Train._resolve_stop_target_m()`

`viewer_position_m` 只用于 dashboard / 3D 视景显示，不参与 ATO 控车、停车、MA、ATP 或动力学计算。

## 当前规则

- `TrainState.position_m` 表示车头位置。
- TRAIN-001 当前固定按下行 `Track=0` 演示。
- 原始停车点接近站台 `StopLeftKm`，会让车头停在站台近端，车厢落在站台外。
- 车辆侧 loader 现在把站台目标修正为 `StopRightKm`，即车头停到站台远端。
- `StopRightKm` 来自 `视景系统公里标最新数据+站台位置20260703.xlsx` 的 `站台位置` sheet。
- `station_id=null` 的 `stop_position` 不作为站台停车目标，`2DG-A` 的 `11424.2m` 不参与 ATO 停站。

## 当前车头停车点序列

| Station | front_cab_stop_position_m |
| --- | ---: |
| ST-01 | 431.0 |
| ST-02 | 1778.52 |
| ST-03 | 2566.61 |
| ST-04 | 3547.32 |
| ST-05 | 5133.834 |
| ST-06 | 6459.274 |
| ST-07 | 8238.204 |
| ST-08 | 9547.344 |
| ST-09 | 10718.11378 |
| ST-10 | 12117.07 |
| ST-11 | 14029.28014 |
| ST-12 | 15072.91 |
| ST-13 | 16169.01966 |

## 检查命令

```powershell
cd D:\大三下\小学期\Track_simulation\backend
.\.venv\Scripts\python.exe scripts\inspect_stop_positions.py
```

输出中的 `ATO usable stop sequence` 应包含上表 13 个停车点，且不应包含 `11424.2m`。
