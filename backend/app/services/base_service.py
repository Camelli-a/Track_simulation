"""
Service 基类：定义统一接口，子类根据 DATA_SOURCE 选择数据来源。
切换数据源只需修改 .env 中的 DATA_SOURCE 字段，无需改动接口层。
"""
from abc import ABC, abstractmethod
from app.core.config import settings


class BaseService(ABC):

    def __init__(self):
        self.source = settings.DATA_SOURCE  # mock | udp | zmq

    @abstractmethod
    def get_status(self):
        """获取当前状态快照"""
        ...

    def get_history(self, limit: int = 100):
        """获取历史数据（默认返回空，子类按需覆写）"""
        return []
