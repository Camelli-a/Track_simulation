from pydantic import BaseModel
from typing import List


class SignalLight(BaseModel):
    signal_id: str
    position: float   # 里程位置 (m)
    state: str        # red | yellow | green


class SignalStatus(BaseModel):
    timestamp: float
    lights: List[SignalLight]
    system_mode: str = "normal"   # normal | degraded | emergency
