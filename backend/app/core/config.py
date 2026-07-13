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

    class Config:
        env_file = ".env"


settings = Settings()
