from pydantic import BaseModel


class PowerStatus(BaseModel):
    timestamp: float
    voltage: float       # 电压 (V)
    current: float       # 电流 (A)
    power: float         # 功率 (kW)
    substation_id: str   # 变电站编号
    is_fault: bool = False
