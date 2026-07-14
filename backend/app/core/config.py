from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Legacy display/source hint. The dashboard data path is the ZMQ/state_store
    # pipeline by default; do not use this as an exclusive runtime mode switch.
    DATA_SOURCE: str = "zmq"

    # Generate local dashboard demo data only when explicitly enabled.
    ENABLE_DASHBOARD_MOCK: bool = False

    # Keep the backend subscribed to the internal module bus in normal runs.
    ENABLE_ZMQ_DASHBOARD_LISTENER: bool = True
    ENABLE_ZMQ_BROKER_MANAGER: bool = True
    ENABLE_SIGNAL_ZMQ_ADAPTER: bool = True

    # Local development/demo helper: when a train is added through
    # /api/v1/vehicle/manage, start one vehicle_sim.main_integrated process for
    # that train. This is not intended to replace production service
    # orchestration.
    ENABLE_VEHICLE_PROCESS_MANAGER: bool = True
    VEHICLE_PROCESS_DT: float = 0.1

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

    # 视景系统 UDP 目标地址（视景控制机）.
    SCENERY_HOST: str = "192.168.100.124"
    SCENERY_PORT: int = 8303
    SCENERY_LOCAL_PORT: int = 8302
    # Direction code used only in the 3D viewer UDP SectionDirection field.
    # The internal train direction_code remains 1 for down-line, increasing
    # position_m. Some viewer edge models face the opposite way, so the UDP
    # visual direction is configurable without changing ATO/signalling logic.
    SCENERY_SECTION_DIRECTION: int = -1

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
