from pydantic import BaseModel


class VehicleStatus(BaseModel):
    timestamp: float
    vehicle_id: str
    position: float      # 当前里程位置 (m)
    speed: float         # 速度 (km/h)
    acceleration: float  # 加速度 (m/s²)
    line_id: str         # 所在线路编号
    is_running: bool = True
