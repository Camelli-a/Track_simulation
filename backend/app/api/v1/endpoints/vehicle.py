import logging
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.data_flow.message_publisher import publish_module_message
from app.data_flow.state_store import state_store
from app.schemas.vehicle import (
    LineOperationRequest,
    StationDemoRequest,
    VehicleControlRequest,
    VehicleControlResponse,
    VehicleManagementRequest,
    VehicleManagementResponse,
    VehicleStatus,
)
from app.services.line_operation_service import LineOperationConfig, line_operation_service
from app.services.station_demo_service import StationDemoConfig, station_demo_service
from app.services.vehicle_service import VehicleService
from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.process_manager import vehicle_process_manager
from app.vehicle_sim.train_manager import TrainManager

router = APIRouter()
service = VehicleService()
logger = logging.getLogger("uvicorn.error")


# ---------------------------------------------------------------------------
# Driver Desk response models (新增，不影响任何现有接口)
# ---------------------------------------------------------------------------

class DriverDeskResponse(BaseModel):
    """司机台 PLC 下行帧解析结果，供前端司机台状态面板使用。
    字段直接对应 data_flow.schemas.DriverInput，精简为前端关注的部分。
    """
    vehicle_id: str
    source: str = "unknown"
    # --- 方向 / 模式 ---
    direction: str = "forward"           # forward / backward / neutral
    control_mode: str = "manual"         # manual / ato
    # --- 牵引制动 ---
    traction_level: int = 0              # 0~4
    brake_level: int = 0                 # 0~7
    traction_percent: float = 0.0        # 0~100
    brake_percent: float = 0.0           # 0~100
    main_handle_raw: Optional[int] = None
    # --- 紧急 ---
    emergency_button: bool = False
    emergency_cmd: bool = False
    # --- ATO ---
    ato_start_btn: bool = False
    ato_capable: Optional[bool] = None
    ato_active: Optional[bool] = None
    auto_reverse_cap: Optional[bool] = None
    auto_reverse_active: Optional[bool] = None
    # --- 车门 ---
    open_left_door: bool = False
    open_right_door: bool = False
    close_left_door: bool = False
    close_right_door: bool = False
    door_mode: Optional[str] = None
    door_closed_light: Optional[bool] = None
    # --- 其他指示灯 / 开关 ---
    key_switch: Optional[bool] = None
    high_voltage_light: Optional[bool] = None
    brake_bad_light: Optional[bool] = None
    network_fault_light: Optional[bool] = None
    # --- 状态 ---
    is_stale: bool = False
    updated_at: float = Field(default_factory=time.time)


class DriverDeskListResponse(BaseModel):
    count: int
    items: List[DriverDeskResponse]

# ---------------------------------------------------------------------------
# Singleton TrainManager + MessageRouter shared across the whole application.
# Importing this module multiple times always returns the same objects.
# main.py reads `vehicle_manager` to wire up the SimulationLoop and the PLC
# feedback aggregator.
# ---------------------------------------------------------------------------
vehicle_manager = TrainManager()
vehicle_message_router = MessageRouter(vehicle_manager)


@router.get("/status", response_model=VehicleStatus, summary="Get current vehicle status")
def get_vehicle_status():
    status = service.get_status()
    logger.info(
        "Vehicle status requested: vehicle_id=%s position=%.2f speed=%.2f",
        status.vehicle_id,
        status.position,
        status.speed,
    )
    return status


@router.get("/history", summary="Get vehicle trajectory history")
def get_vehicle_history(limit: int = 100):
    history = service.get_history(limit)
    logger.info("Vehicle history requested: limit=%s returned=%s", limit, len(history))
    return history


@router.post("/control", response_model=VehicleControlResponse, summary="Send vehicle control command")
def control_vehicle(command: VehicleControlRequest) -> VehicleControlResponse:
    topic, message = _build_vehicle_control_message(command)
    published = publish_module_message(topic, message)

    if topic == "ato_command":
        state_store.update_ato_command(command.vehicle_id, message)
    else:
        state_store.update_driver_input(command.vehicle_id, message)

    logger.info(
        "Vehicle control: vehicle_id=%s command=%s topic=%s traction=%s brake=%s direction=%s published=%s",
        command.vehicle_id,
        command.command,
        topic,
        message.get("traction_level"),
        message.get("brake_level"),
        message.get("direction"),
        published,
    )
    return VehicleControlResponse(
        published=published,
        topic=topic,
        message=message,
    )


@router.get("/trains", summary="List managed vehicle simulation trains")
def list_vehicle_trains() -> dict:
    live_by_id = {
        item.vehicle_id: item.model_dump()
        for item in state_store.get_snapshot().trains
    }
    managed_trains = vehicle_manager.list_trains()
    if managed_trains:
        trains = []
        for managed in managed_trains:
            vehicle_id = str(managed.get("vehicle_id"))
            live = live_by_id.get(vehicle_id, {})
            trains.append({**managed, **live})
    else:
        trains = list(live_by_id.values())
    trains = vehicle_process_manager.enrich_trains(trains)
    logger.info("Vehicle trains listed: count=%s", len(trains))
    return {
        "count": len(trains),
        "trains": trains,
    }


# ---------------------------------------------------------------------------
# Driver Desk endpoints — 读 state_store._driver_inputs，不写任何共享状态
# ---------------------------------------------------------------------------

def _build_driver_desk_response(driver_input) -> DriverDeskResponse:
    """把 DriverInput schema 对象转成 DriverDeskResponse，兼容 stale 标记。"""
    d = driver_input.model_dump()
    # 只取 DriverDeskResponse 声明的字段，其余忽略
    fields = DriverDeskResponse.model_fields.keys()
    return DriverDeskResponse(**{k: d[k] for k in fields if k in d})


@router.get(
    "/driver-desk",
    response_model=DriverDeskListResponse,
    summary="[司机台] 所有车辆的司机台状态",
    description=(
        "返回 state_store 中缓存的所有车辆司机台输入状态。\n\n"
        "**数据来源**：`driver_input` ZMQ topic（司机台 PLC TCP 解析后发布）。\n"
        "**更新频率**：PLC 下行帧 100 ms/次，`is_stale=true` 表示超过 1 s 未更新。\n"
        "**不影响任何其他接口**：本接口只读，不写 state_store。"
    ),
)
def get_all_driver_desk() -> DriverDeskListResponse:
    now = time.time()
    stale_threshold = 1.0
    items = []
    with state_store._lock:
        inputs = list(state_store._driver_inputs.values())
    for di in inputs:
        resp = _build_driver_desk_response(di)
        # 实时计算 stale（比 schema 里的 is_stale 更准确）
        resp.is_stale = (now - float(di.updated_at)) > stale_threshold
        items.append(resp)
    return DriverDeskListResponse(count=len(items), items=items)


@router.get(
    "/driver-desk/{vehicle_id}",
    response_model=DriverDeskResponse,
    summary="[司机台] 指定车辆的司机台状态",
    description="按 vehicle_id 查询单辆车的司机台输入状态。找不到时返回 404。",
)
def get_driver_desk(vehicle_id: str) -> DriverDeskResponse:
    now = time.time()
    stale_threshold = 1.0
    with state_store._lock:
        di = state_store._driver_inputs.get(vehicle_id)
    if di is None:
        raise HTTPException(
            status_code=404,
            detail=f"No driver desk data for vehicle_id={vehicle_id!r}. "
                   "Make sure DATA_SOURCE=zmq and the PLC is connected.",
        )
    resp = _build_driver_desk_response(di)
    resp.is_stale = (now - float(di.updated_at)) > stale_threshold
    return resp


# ---------------------------------------------------------------------------
# Trip Status endpoints — 行驶状态（只读，不写任何共享状态）
# GET /api/v1/vehicle/trip-status           → 所有车辆
# GET /api/v1/vehicle/trip-status/:id       → 单辆车
# ---------------------------------------------------------------------------

class TripStatusResponse(BaseModel):
    """列车行驶区间状态，供前端 TripStatusPanel 使用。"""
    vehicle_id: str
    # --- 方向 ---
    direction: str = "forward"          # forward / reverse / neutral
    # --- 当前位置 ---
    current_position_m: float = 0.0
    speed_kmh: float = 0.0
    is_stopped: bool = False
    # --- 站点信息 ---
    from_station_id: Optional[str] = None
    from_station: Optional[str] = None  # 出发站名
    to_station_id: Optional[str] = None
    to_station: Optional[str] = None    # 下一站名（MA 目标站）
    # --- 距离 ---
    distance_to_next_m: Optional[float] = None   # 距下一站剩余距离
    segment_length_m: Optional[float] = None     # 区间全长
    traveled_m: Optional[float] = None           # 区间内已行驶距离
    # --- 数据来源标注 ---
    distance_source: str = "none"       # "ma" / "stop_target" / "inferred" / "none"
    is_stale: bool = False
    updated_at: float = Field(default_factory=time.time)


class TripStatusListResponse(BaseModel):
    count: int
    items: List[TripStatusResponse]


def _load_station_list() -> list[dict]:
    """从 line-layout.json 读取站点列表，失败时返回空列表（不影响主流程）。"""
    try:
        from app.vehicle_sim.line_data_loader import load_line_layout
        layout = load_line_layout()
        stations: dict[str, dict] = {}

        # 从 track_info.sections / blocks 中收集站点停车位置
        sections = (
            layout.get("track_info", {}).get("sections")
            or layout.get("blocks")
            or []
        )
        for sec in sections:
            sid = sec.get("station_id")
            if not sid:
                continue
            stop_pos = sec.get("stop_position")
            start = float(sec.get("start", 0))
            end = float(sec.get("end", start))
            pos = float(stop_pos) if stop_pos else (start + end) / 2.0
            if sid not in stations:
                stations[sid] = {"station_id": sid, "name": sid, "position": pos}
            else:
                # 取更小值（更靠近行程起点）作为代表位置
                stations[sid]["position"] = min(stations[sid]["position"], pos)

        # 补充站名（来自 yard_layout）
        yard_stations = (
            layout.get("yard_layout", {}).get("stations")
            or []
        )
        for ys in yard_stations:
            sid = ys.get("station_id")
            if sid and sid in stations:
                stations[sid]["name"] = ys.get("station_name") or sid

        return sorted(stations.values(), key=lambda s: s["position"])
    except Exception:
        return []


# 模块级缓存，避免每次请求都读文件
_STATION_LIST: list[dict] | None = None


def _get_station_list() -> list[dict]:
    global _STATION_LIST
    if _STATION_LIST is None:
        _STATION_LIST = _load_station_list()
    return _STATION_LIST


def _build_trip_status(train, ma) -> TripStatusResponse:
    """
    从 TrainSnapshot + MovementAuthoritySnapshot 组装行驶状态。

    出发站：已经过去的最近一站（按列车 position 和行驶方向判断）。
    下一站：MA 目标站 > ATO stop_target 最近站 > 前方最近站，按优先级取第一个有效值。
    距离：MA 的 distance_to_ma > train.distance_to_stop > 自算，按优先级取第一个有效值。
    """
    now = time.time()
    stale_threshold = 2.0

    position = float(train.position or 0.0)
    speed_kmh = float(train.speed or train.speed_kmh or 0.0)
    is_stopped = speed_kmh < 0.5

    # 行驶方向归一化
    raw_dir = train.direction  # 可能是 int(1/-1) 或 str
    if raw_dir in (-1, 2, "reverse", "backward", "down"):
        direction = "reverse"
    elif raw_dir in (0, "neutral"):
        direction = "neutral"
    else:
        direction = "forward"

    direction_sign = -1 if direction == "reverse" else 1

    stations = _get_station_list()

    # ── 推断出发站（列车已经过去的最近一站）──────────────────────────
    from_station_id: Optional[str] = None
    from_station_name: Optional[str] = None
    from_station_pos: Optional[float] = None

    if stations:
        if direction_sign >= 0:
            # 正向：找 position 最大且 <= 当前位置 的站
            passed = [s for s in stations if s["position"] <= position]
            if passed:
                best = passed[-1]
                from_station_id = best["station_id"]
                from_station_name = best["name"]
                from_station_pos = best["position"]
        else:
            # 反向：找 position 最小且 >= 当前位置 的站
            passed = [s for s in stations if s["position"] >= position]
            if passed:
                best = passed[0]
                from_station_id = best["station_id"]
                from_station_name = best["name"]
                from_station_pos = best["position"]

    # ── 推断下一站 ────────────────────────────────────────────────────
    to_station_id: Optional[str] = None
    to_station_name: Optional[str] = None
    to_station_pos: Optional[float] = None

    # 优先：MA 携带的目标站名
    if ma and ma.station_name:
        to_station_name = ma.station_name
        to_station_id = ma.station_id
        # 尝试从 station_list 中找到对应位置
        if stations and to_station_id:
            match = next((s for s in stations if s["station_id"] == to_station_id), None)
            if match:
                to_station_pos = match["position"]

    # 次优：从站点列表推断前方最近一站
    if to_station_name is None and stations:
        if direction_sign >= 0:
            ahead = [s for s in stations if s["position"] > position]
            if ahead:
                best = ahead[0]
                to_station_id = best["station_id"]
                to_station_name = best["name"]
                to_station_pos = best["position"]
        else:
            ahead = [s for s in stations if s["position"] < position]
            if ahead:
                best = ahead[-1]
                to_station_id = best["station_id"]
                to_station_name = best["name"]
                to_station_pos = best["position"]

    # ── 距下一站距离 ──────────────────────────────────────────────────
    distance_to_next: Optional[float] = None
    distance_source = "none"

    # 优先 MA distance_to_ma
    if ma and ma.distance_to_ma is not None:
        distance_to_next = float(ma.distance_to_ma)
        distance_source = "ma"
    # 次优 train.distance_to_stop（ATO stop_target 距离）
    elif train.distance_to_stop is not None:
        distance_to_next = float(train.distance_to_stop)
        distance_source = "stop_target"
    # 再次 train.stop_distance（由 MA 覆写到 train 上的值）
    elif train.stop_distance is not None:
        distance_to_next = float(train.stop_distance)
        distance_source = "stop_target"
    # 最后用站点坐标自算
    elif to_station_pos is not None:
        distance_to_next = abs(to_station_pos - position)
        distance_source = "inferred"

    if distance_to_next is not None:
        distance_to_next = max(0.0, round(distance_to_next, 1))

    # ── 区间信息（用于进度条） ────────────────────────────────────────
    segment_length: Optional[float] = None
    traveled: Optional[float] = None

    if from_station_pos is not None and to_station_pos is not None:
        segment_length = round(abs(to_station_pos - from_station_pos), 1)
        traveled = round(abs(position - from_station_pos), 1)

    # ── stale 判断 ────────────────────────────────────────────────────
    is_stale = (now - float(train.updated_at)) > stale_threshold

    return TripStatusResponse(
        vehicle_id=train.vehicle_id,
        direction=direction,
        current_position_m=round(position, 1),
        speed_kmh=round(speed_kmh, 1),
        is_stopped=is_stopped,
        from_station_id=from_station_id,
        from_station=from_station_name,
        to_station_id=to_station_id,
        to_station=to_station_name,
        distance_to_next_m=distance_to_next,
        segment_length_m=segment_length,
        traveled_m=traveled,
        distance_source=distance_source,
        is_stale=is_stale,
        updated_at=float(train.updated_at),
    )


@router.get(
    "/trip-status",
    response_model=TripStatusListResponse,
    summary="[行驶状态] 所有车辆的区间行驶状态",
    description=(
        "返回所有车辆的区间行驶状态：出发站、下一站、剩余距离。\n\n"
        "**数据来源**：state_store 中的 TrainSnapshot + MovementAuthoritySnapshot。\n"
        "**只读接口**：不写 state_store，不影响任何其他逻辑。"
    ),
)
def get_all_trip_status() -> TripStatusListResponse:
    snapshot = state_store.get_snapshot()
    ma_by_id = {ma.vehicle_id: ma for ma in snapshot.ma_limits}
    items = [
        _build_trip_status(train, ma_by_id.get(train.vehicle_id))
        for train in snapshot.trains
    ]
    return TripStatusListResponse(count=len(items), items=items)


@router.get(
    "/trip-status/{vehicle_id}",
    response_model=TripStatusResponse,
    summary="[行驶状态] 指定车辆的区间行驶状态",
    description="按 vehicle_id 查询单辆车的行驶状态。找不到时返回 404。",
)
def get_trip_status(vehicle_id: str) -> TripStatusResponse:
    snapshot = state_store.get_snapshot()
    train = next((t for t in snapshot.trains if t.vehicle_id == vehicle_id), None)
    if train is None:
        raise HTTPException(
            status_code=404,
            detail=f"No trip status data for vehicle_id={vehicle_id!r}. "
                   "Make sure the vehicle is registered and DATA_SOURCE=zmq.",
        )
    ma_by_id = {ma.vehicle_id: ma for ma in snapshot.ma_limits}
    return _build_trip_status(train, ma_by_id.get(vehicle_id))


@router.post("/manage", response_model=VehicleManagementResponse, summary="Manage vehicle simulation trains")
async def manage_vehicle(command: VehicleManagementRequest) -> VehicleManagementResponse:
    if command.type == "add_train" and not _is_physical_driver_train(command):
        return await _enqueue_ato_train(command)
    if command.type == "remove_train" and command.vehicle_id:
        line_operation_service.forget_train(command.vehicle_id)
    return _manage_vehicle_command(command)


@router.post("/station-demo/start", summary="Start continuous station arrival/departure demo")
async def start_station_demo(command: StationDemoRequest | None = None) -> dict:
    command = command or StationDemoRequest()
    await line_operation_service.stop()
    return await station_demo_service.start(
        _manage_vehicle_command,
        StationDemoConfig(
            station_id=command.station_id,
            station_name=command.station_name,
            headway_sec=command.headway_sec,
            dwell_sec=command.dwell_sec,
            max_active_trains=command.max_active_trains,
            approach_distance_m=command.approach_distance_m,
            exit_distance_m=command.exit_distance_m,
            min_train_spacing_m=command.min_train_spacing_m,
            cruise_speed_kmh=command.cruise_speed_kmh,
            start_index=command.start_index,
        ),
    )


@router.post("/station-demo/stop", summary="Stop continuous station demo")
async def stop_station_demo() -> dict:
    return await station_demo_service.stop()


@router.get("/station-demo/status", summary="Get station demo status")
def get_station_demo_status() -> dict:
    return station_demo_service.status()


@router.post("/line-operation/start", summary="Start continuous bidirectional line operation")
async def start_line_operation(command: LineOperationRequest | None = None) -> dict:
    command = command or LineOperationRequest()
    await station_demo_service.stop()
    return await line_operation_service.start(
        _manage_vehicle_command,
        LineOperationConfig(
            headway_sec=command.headway_sec,
            max_active_trains=command.max_active_trains,
            dwell_sec=command.dwell_sec,
            min_train_spacing_m=command.min_train_spacing_m,
            start_index_up=command.start_index_up,
            start_index_down=command.start_index_down,
        ),
    )


@router.post("/line-operation/stop", summary="Stop continuous bidirectional line operation")
async def stop_line_operation() -> dict:
    return await line_operation_service.stop()


@router.get("/line-operation/status", summary="Get continuous line operation status")
def get_line_operation_status() -> dict:
    return line_operation_service.status()


async def _enqueue_ato_train(command: VehicleManagementRequest) -> VehicleManagementResponse:
    await station_demo_service.stop()
    if not line_operation_service.active:
        await line_operation_service.start(_manage_vehicle_command)

    result = line_operation_service.enqueue_train(
        vehicle_id=command.vehicle_id,
        train_index=command.train_index,
    )
    trains = vehicle_process_manager.enrich_trains(vehicle_manager.list_trains())
    state_store.replace_trains(trains, prune_absent=True)
    return VehicleManagementResponse(
        ok=bool(result.get("ok", False)),
        published=not bool(result.get("queued", False)),
        topic="add_train",
        result={
            **result,
            "control_policy": "non_001_added_to_onboard_ato_queue",
        },
        trains=trains,
    )


def _is_physical_driver_train(command: VehicleManagementRequest) -> bool:
    if command.vehicle_id is not None:
        return str(command.vehicle_id).upper() == "TRAIN-001"
    return command.train_index == 1


def _manage_vehicle_command(command: VehicleManagementRequest) -> VehicleManagementResponse:
    message = _build_vehicle_management_message(command)
    result = vehicle_message_router.handle(message)
    if result is None:
        result = {"ok": False, "reason": "unsupported_vehicle_management_command"}

    topic = command.type
    published = publish_module_message(topic, _management_publish_payload(message))
    process_result = _sync_vehicle_processes(command, result)
    if process_result:
        result = {**result, "process": process_result}

    trains = vehicle_process_manager.enrich_trains(vehicle_manager.list_trains())
    state_store.replace_trains(trains, prune_absent=True)

    logger.info(
        "Vehicle management: type=%s vehicle_id=%s train_index=%s ok=%s published=%s active_trains=%s",
        command.type,
        command.vehicle_id,
        command.train_index,
        result.get("ok", False),
        published,
        len(trains),
    )
    return VehicleManagementResponse(
        ok=bool(result.get("ok", False)),
        published=published,
        topic=topic,
        result=result,
        trains=trains,
    )


def _build_vehicle_control_message(command: VehicleControlRequest) -> tuple[str, dict]:
    if command.command == "ato":
        return "ato_command", {
            "vehicle_id": command.vehicle_id,
            "line_id": command.line_id,
            "control_mode": "ato",
            "target_speed": float(command.target_speed or 0.0),
            "target_position": command.target_position,
            "traction_level": command.traction_level,
            "brake_level": command.brake_level,
            "traction_percent": command.traction_percent,
            "brake_percent": command.brake_percent,
            "reason": command.reason,
        }

    traction_level = command.traction_level
    brake_level = command.brake_level
    traction_percent = command.traction_percent
    brake_percent = command.brake_percent
    emergency_button = False

    if command.command == "traction":
        traction_level = max(traction_level, command.level)
        brake_level = 0
        traction_percent = traction_percent or traction_level / 4 * 100.0
        brake_percent = 0.0
    elif command.command == "brake":
        traction_level = 0
        brake_level = max(brake_level, command.level, 2)
        traction_percent = 0.0
        brake_percent = brake_percent or brake_level / 7 * 100.0
    elif command.command in {"emergency_stop", "emergency_brake"}:
        traction_level = 0
        brake_level = 4
        traction_percent = 0.0
        brake_percent = 100.0
        emergency_button = True
    elif brake_level > 0:
        traction_level = 0
        traction_percent = 0.0
        brake_percent = brake_percent or brake_level / 7 * 100.0
    elif traction_level > 0:
        traction_percent = traction_percent or traction_level / 4 * 100.0

    return "driver_input", {
        "vehicle_id": command.vehicle_id,
        "line_id": command.line_id,
        "source": "frontend",
        "command_source": command.source,
        "control_mode": "manual",
        "traction_level": traction_level,
        "brake_level": brake_level,
        "traction_percent": traction_percent,
        "brake_percent": brake_percent,
        "main_handle_raw": command.main_handle_raw,
        "key_switch": command.key_switch,
        "direction": command.direction,
        "emergency_button": emergency_button,
        "open_left_door": command.open_left_door,
        "open_right_door": command.open_right_door,
        "close_left_door": command.close_left_door,
        "close_right_door": command.close_right_door,
        "door_mode": command.door_mode,
        "door_closed_light": command.door_closed_light,
        "high_voltage_light": command.high_voltage_light,
        "brake_bad_light": command.brake_bad_light,
        "network_fault_light": command.network_fault_light,
    }


def _management_publish_payload(message: dict) -> dict:
    return {
        key: value
        for key, value in message.items()
        if key not in {"type"}
    }


def _build_vehicle_management_message(command: VehicleManagementRequest) -> dict:
    if command.type == "add_train":
        message = {
            "type": command.type,
            "line_id": command.line_id,
            "position": command.position,
        }
        if command.vehicle_id is not None:
            message["vehicle_id"] = command.vehicle_id
        if command.train_index is not None:
            message["train_index"] = command.train_index
        return message

    if command.type == "remove_train":
        message = {"type": command.type}
        if command.vehicle_id is not None:
            message["vehicle_id"] = command.vehicle_id
        if command.train_index is not None:
            message["train_index"] = command.train_index
        return message

    if command.type == "reset_trains":
        return {
            "type": command.type,
            "count": 10 if command.count is None else command.count,
        }

    return {"type": command.type}


def _sync_vehicle_processes(command: VehicleManagementRequest, result: dict) -> dict | None:
    if not result.get("ok"):
        return None

    if command.type == "add_train":
        vehicle_id = result.get("vehicle_id") or command.vehicle_id
        train_index = result.get("train_index") or command.train_index
        if not vehicle_id or not train_index:
            return {"started": False, "reason": "missing_vehicle_id_or_train_index"}
        return vehicle_process_manager.start_train(
            vehicle_id=str(vehicle_id),
            train_index=int(train_index),
            initial_position=float(result.get("position", command.position)),
        )

    if command.type == "remove_train":
        vehicle_id = result.get("vehicle_id") or command.vehicle_id
        if vehicle_id:
            return vehicle_process_manager.stop_train(str(vehicle_id))
        return {"stopped": False, "reason": "missing_vehicle_id"}

    if command.type == "clear_trains":
        return vehicle_process_manager.stop_all()

    if command.type == "reset_trains":
        stop_result = vehicle_process_manager.stop_all()
        start_results = []
        for train in vehicle_manager.list_trains():
            start_results.append(
                vehicle_process_manager.start_train(
                    vehicle_id=str(train["vehicle_id"]),
                    train_index=int(train["train_index"]),
                    initial_position=float(train.get("position", 0.0)),
                )
            )
        return {"reset": True, "stop": stop_result, "start": start_results}

    return None
