from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.core.config import settings
from app.data_flow.message_publisher import publish_module_message
from app.data_flow.mock_service import mock_dashboard_service
from app.data_flow.schemas import (
    DashboardSnapshot,
    RouteRequestCommand,
    ScenarioConfig,
    VehicleRegistrationCommand,
    YardLayoutSnapshot,
)
from app.data_flow.state_store import state_store

router = APIRouter()
logger = logging.getLogger(__name__)


def _vehicle_scene_item(train: Any, snapshot: DashboardSnapshot) -> dict[str, Any]:
    """Derive the current overview scene for one train from real snapshot fields."""

    scenario_id = "line_run"
    reason = "normal"
    summary = "正常巡航"

    if getattr(train, "emergency_brake", False) or getattr(train, "atp_intervention", False):
        scenario_id = "manual_overspeed_atp"
        reason = "atp_or_emergency_brake"
        summary = "ATP/紧急制动介入"
    elif getattr(train, "permission", None) == "stop":
        scenario_id = "ma_shrink"
        reason = "permission_stop"
        summary = "MA 停车约束"
    elif getattr(train, "permission", None) == "restricted":
        scenario_id = "ma_shrink"
        reason = "permission_restricted"
        summary = "MA 受限运行"
    elif getattr(train, "signal_state", None) in {"red", "yellow"}:
        scenario_id = "signal_restriction"
        reason = f"signal_{getattr(train, 'signal_state', 'restricted')}"
        summary = "信号受限"
    elif getattr(train, "parking_phase", None) in {"approaching", "braking", "docking", "stopped"}:
        scenario_id = "station_stop"
        reason = f"parking_phase_{getattr(train, 'parking_phase', 'unknown')}"
        summary = "进站停车过程"
    elif getattr(train, "distance_to_ma", None) is not None and train.distance_to_ma < 120:
        scenario_id = "ma_shrink"
        reason = "near_ma_boundary"
        summary = "接近 MA 边界"

    return {
        "scenario_id": scenario_id,
        "scope": "vehicle",
        "vehicle_id": train.vehicle_id,
        "target_vehicle_id": train.vehicle_id,
        "summary": summary,
        "reason": reason,
        "key_metrics": _scene_metric_keys(scenario_id),
        "highlight_events": _scene_event_keys(scenario_id),
        "updated_at": getattr(train, "updated_at", None) or snapshot.timestamp,
    }


def _scene_metric_keys(scenario_id: str) -> list[str]:
    if scenario_id == "manual_overspeed_atp":
        return ["current_speed", "target_speed", "atp_status", "brake_level"]
    if scenario_id == "ma_shrink":
        return ["distance_to_ma", "ma_limit", "permission", "signal_state"]
    if scenario_id == "station_stop":
        return ["current_speed", "recommended_speed", "stop_distance", "stop_error_cm"]
    return ["current_speed", "mode", "driving_mode", "current_section_id"]


def _scene_event_keys(scenario_id: str) -> list[str]:
    if scenario_id == "manual_overspeed_atp":
        return ["atp_triggered", "realtime_snapshot", "ma_updated"]
    if scenario_id == "ma_shrink":
        return ["ma_updated", "signal_state", "realtime_snapshot"]
    if scenario_id == "station_stop":
        return ["ato_command", "door_state", "stop_completed"]
    return ["realtime_snapshot", "ma_updated", "signal_state"]


def _load_real_yard_layout() -> YardLayoutSnapshot | None:
    """Load the converted workbook yard layout for dashboard rendering.

    This is static infrastructure data, not generated demo runtime data. Prefer
    the frontend public artifact because it is the canonical output consumed by
    Page 1; fall back to backend/data for deployment layouts that copy assets
    there.
    """

    backend_root = Path(__file__).resolve().parents[2]
    project_root = backend_root.parent
    candidates = [
        project_root / "frontend" / "public" / "data" / "line-layout.json",
        project_root / "backend" / "data" / "line-layout.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            yard_layout = payload.get("yard_layout")
            if isinstance(yard_layout, dict) and yard_layout.get("stations"):
                return YardLayoutSnapshot(**yard_layout)
        except Exception:
            logger.exception("Failed to load yard layout from %s", path)
    return None


@router.get("/snapshot", response_model=DashboardSnapshot, summary="Get dashboard snapshot")
def get_dashboard_snapshot() -> DashboardSnapshot:
    if settings.ENABLE_DASHBOARD_MOCK:
        mock_dashboard_service.tick()
    return state_store.get_snapshot()


@router.get("/scenarios", response_model=list[ScenarioConfig], summary="Get frontend scenario page configs")
def get_scenarios() -> list[ScenarioConfig]:
    return state_store.get_scenarios()


@router.get("/scenarios/{scenario_id}", response_model=ScenarioConfig, summary="Get one scenario page config")
def get_scenario(scenario_id: str) -> ScenarioConfig:
    scenario = state_store.get_scenario(scenario_id)
    if scenario is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="scenario_not_found")
    return scenario


@router.get("/scene-state", summary="Get current dashboard scene state")
def get_scene_state() -> dict[str, Any]:
    """Return scene selection derived from the current real dashboard snapshot.

    This endpoint is intentionally a lightweight compatibility view for the
    frontend. It does not generate mock runtime data; it classifies the current
    train/MA/ATO/ATP state already cached in state_store.
    """

    snapshot = state_store.get_snapshot()
    vehicle_scene_map = [_vehicle_scene_item(train, snapshot) for train in snapshot.trains]

    active_scene = None
    if vehicle_scene_map:
        priority = {
            "manual_overspeed_atp": 0,
            "ma_shrink": 1,
            "signal_restriction": 2,
            "station_stop": 3,
            "line_run": 4,
        }
        active_scene = min(
            vehicle_scene_map,
            key=lambda item: priority.get(item["scenario_id"], 99),
        )
    else:
        active_scene = {
            "scenario_id": "line_run",
            "scope": "network",
            "vehicle_id": None,
            "target_vehicle_id": None,
            "summary": "等待车辆状态",
            "reason": "no_train_state",
            "key_metrics": ["affected_vehicle_count", "system_mode", "signal_count", "section_count"],
            "highlight_events": ["realtime_snapshot", "signal_state"],
            "updated_at": snapshot.timestamp,
        }

    return {
        "type": "dashboard_scene_state",
        "timestamp": snapshot.timestamp,
        "active_scene": active_scene,
        "vehicle_scene_map": vehicle_scene_map,
    }


@router.get("/stations/yards", response_model=YardLayoutSnapshot, summary="Get static station yard layout")
def get_station_yards() -> YardLayoutSnapshot:
    if not state_store.get_yard_layout().stations:
        real_layout = _load_real_yard_layout()
        if real_layout is not None:
            state_store.update_yard_layout(real_layout)
        elif settings.ENABLE_DASHBOARD_MOCK:
            state_store.update_yard_layout(mock_dashboard_service.build_yard_layout_seed())
    return state_store.get_yard_layout()


@router.post("/publish-track-info", summary="Publish track_info to module message bus")
def publish_track_info() -> dict:
    if settings.ENABLE_DASHBOARD_MOCK and not state_store.get_track_info_payload()["sections"]:
        mock_dashboard_service.tick()

    payload = state_store.get_track_info_payload()
    published = publish_module_message("track_info", payload)
    return {
        "accepted": True,
        "published": published,
        "topic": "track_info",
        "section_count": len(payload["sections"]),
    }


@router.post("/vehicles/register", summary="Register vehicle and publish initial state")
def register_vehicle(command: VehicleRegistrationCommand) -> dict:
    payload = command.model_dump(exclude_none=True)
    vehicle_id = state_store.register_vehicle(payload)
    published_register = publish_module_message("vehicle_register", payload)
    published_set_state = publish_module_message("set_train_state", payload)
    return {
        "accepted": vehicle_id is not None,
        "vehicle_id": vehicle_id,
        "published": published_register or published_set_state,
        "topics": {
            "vehicle_register": published_register,
            "set_train_state": published_set_state,
        },
    }


@router.post("/route-request", summary="Publish route request to module message bus")
def publish_route_request(command: RouteRequestCommand) -> dict:
    payload = command.model_dump(exclude_none=True)
    request_key = state_store.update_route_request(payload)
    published = publish_module_message("route_request", payload)
    return {
        "accepted": request_key is not None,
        "published": published,
        "topic": "route_request",
        "request_key": request_key,
    }
