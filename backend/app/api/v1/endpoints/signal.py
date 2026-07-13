"""信号系统接口"""
import time
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.signal_service import SignalService
from app.schemas.signal import SignalEvaluateRequest, SignalStatus

router = APIRouter()
service = SignalService()


# 无 pytest 配置时，可启动后端后在 /docs 中执行 GET /api/v1/signal/status 验证。
@router.get("/status", response_model=SignalStatus, summary="获取信号系统当前状态")
def get_signal_status():
    return service.get_status()


@router.post("/evaluate", response_model=SignalStatus, summary="调试计算信号控制快照")
def evaluate_signal_status(request: SignalEvaluateRequest):
    return service.evaluate(request)


@router.get("/lights", summary="获取所有信号灯状态列表")
def get_all_lights():
    return service.get_all_lights()


# ---------------------------------------------------------------------------
# Debug / test helper — inject MA without a real signal module
# ---------------------------------------------------------------------------

class InjectMaRequest(BaseModel):
    vehicle_id: str = Field(
        default="TRAIN-001",
        description="目标列车 ID",
    )
    ma_limit_m: float = Field(
        default=5000.0,
        description="MA 终点位置（米），列车允许行驶到此处",
    )
    allowed_speed_kmh: float = Field(
        default=80.0,
        description="允许速度上限（km/h）",
    )
    permission: str = Field(
        default="allow",
        description="行车许可：allow | restricted | stop",
    )
    signal_state: str = Field(
        default="green",
        description="信号显示：green | yellow | red",
    )
    stop_target_m: Optional[float] = Field(
        default=None,
        description="停车目标位置（米）。不填则 ATO 使用线路静态站台配置",
    )


@router.post(
    "/inject-ma",
    summary="[调试] 注入 MA，无需信号模块即可测试 ATO",
    description=(
        "直接向 TRAIN-001（或指定列车）注入移动授权（MA），使 ATO 脱离 degraded 状态。\n\n"
        "**仅用于联调测试，无信号模块时使用。**\n\n"
        "注入后 ATO 会立即计算制动曲线，如果 `driving_mode=AM` 则自动控车。"
    ),
)
def inject_ma(req: InjectMaRequest) -> dict:
    from app.api.v1.endpoints.vehicle import vehicle_message_router

    ma_message = {
        "type": "ma_state",
        "timestamp": time.time(),
        "source": "debug_inject",
        "ma_limits": [
            {
                "vehicle_id": req.vehicle_id,
                "ma_limit": req.ma_limit_m,
                "ma_limit_m": req.ma_limit_m,
                "allowed_speed_kmh": req.allowed_speed_kmh,
                "permission": req.permission,
                "signal_state": req.signal_state,
                "target_speed": req.allowed_speed_kmh,
                "reason": "debug_inject",
                "updated_at": time.time(),
                **(
                    {"stop_target_m": req.stop_target_m}
                    if req.stop_target_m is not None
                    else {}
                ),
            }
        ],
    }

    vehicle_message_router.handle(ma_message)

    # Also push into state_store so the dashboard snapshot reflects it
    from app.data_flow.state_store import state_store
    state_store.update_ma_limits(ma_message["ma_limits"])

    return {
        "ok": True,
        "injected": {
            "vehicle_id": req.vehicle_id,
            "ma_limit_m": req.ma_limit_m,
            "allowed_speed_kmh": req.allowed_speed_kmh,
            "permission": req.permission,
            "signal_state": req.signal_state,
            "stop_target_m": req.stop_target_m,
        },
        "note": (
            "MA injected. ATO should leave 'degraded' state within one tick (~100ms). "
            "Set driving_mode=AM (push ato_start_btn on the cab) to activate auto control."
        ),
    }
