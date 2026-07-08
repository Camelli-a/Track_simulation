from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # 数据源模式：mock | udp | zmq
    DATA_SOURCE: str = "mock"

    # UDP
    UDP_HOST: str = "0.0.0.0"
    UDP_PORT: int = 9000

    # ZMQ
    ZMQ_BROKER_FRONTEND: str = "tcp://127.0.0.1:5555"
    ZMQ_BROKER_BACKEND: str = "tcp://127.0.0.1:5556"
    ZMQ_ADDRESS: str = "tcp://127.0.0.1:5555"

    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"


settings = Settings()
