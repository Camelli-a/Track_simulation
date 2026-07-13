from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Data source: mock | udp | zmq
    DATA_SOURCE: str = "mock"

    # UDP compatibility settings.
    UDP_HOST: str = "0.0.0.0"
    UDP_PORT: int = 9000

    # Driver desk PLC over TCP.
    # DriverDeskSource always starts in zmq mode and retries until connected.
    # Set PLC_HOST/PLC_PORT to match the real hardware; if the PLC is not
    # reachable the source will keep retrying silently in the background.
    PLC_HOST: str = "192.168.100.123"
    PLC_PORT: int = 8001

    # Signal screen MMI over TCP (信号屏).
    SIGNAL_MMI_HOST: str = "192.168.100.121"
    SIGNAL_MMI_PORT: int = 9999

    # ZMQ broker addresses.
    ZMQ_BROKER_FRONTEND: str = "tcp://127.0.0.1:5555"
    ZMQ_BROKER_BACKEND: str = "tcp://127.0.0.1:5556"

    # Compatibility aliases for older modules.
    ZMQ_ADDRESS: str = "tcp://127.0.0.1:5555"
    zmq_address: str = "tcp://127.0.0.1:5555"

    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # 3D viewer mapping for the current TRAIN-001 acceptance run.
    # Internal position_m is still the vehicle/ATO coordinate.  The viewer
    # coordinate is only used in the visualization payload.
    VISUAL_TRACK: int = 0
    VISUAL_DIRECTION_NAME: str = "down"
    SIGNAL_COORD_OFFSET_M: float = 216.46
    VIEWER_ABS_OFFSET_M: float = 4028.28

    class Config:
        env_file = ".env"


settings = Settings()
