"""信号系统接口"""
from fastapi import APIRouter
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
