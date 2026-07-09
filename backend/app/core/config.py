from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # 数据源模式：mock | udp | zmq
    DATA_SOURCE: str = "mock"

    # UDP（保留兼容）
    UDP_HOST: str = "0.0.0.0"
    UDP_PORT: int = 9000

    # PLC 司机台（TCP）
    PLC_HOST: str = "192.168.100.123"  # PLC 默认 IP
    PLC_PORT: int = 8001               # PLC 端口（8001/8002/8003 按需改）

    # ZMQ Broker 地址
    zmq_address: str = "tcp://localhost:5555"
    ZMQ_BROKER_FRONTEND: str = "tcp://127.0.0.1:5555"  # 订阅者连接
    ZMQ_BROKER_BACKEND: str = "tcp://127.0.0.1:5556"   # 发布者连接

    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"


settings = Settings()
