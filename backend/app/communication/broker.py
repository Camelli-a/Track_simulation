"""
ZMQ 消息总线 Broker
使用 XPUB/XSUB 模式，支持多发布者、多订阅者
"""
import zmq
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class MessageBroker:
    """
    ZMQ 消息代理，负责转发所有消息
    
    架构：
    发布者 ---> XSUB (backend) ---> XPUB (frontend) ---> 订阅者
    """

    def __init__(
        self,
        frontend_address: str = None,
        backend_address: str = None,
    ):
        self.frontend_address = frontend_address or settings.ZMQ_BROKER_FRONTEND
        self.backend_address = backend_address or settings.ZMQ_BROKER_BACKEND
        self.context = None
        self.frontend = None
        self.backend = None

    def start(self):
        """启动 Broker，阻塞运行"""
        logger.info(f"Starting ZMQ Broker...")
        logger.info(f"  Frontend (XPUB): {self.frontend_address}")
        logger.info(f"  Backend  (XSUB): {self.backend_address}")

        self.context = zmq.Context()

        # XPUB: 订阅者连接这里
        self.frontend = self.context.socket(zmq.XPUB)
        self.frontend.bind(self.frontend_address)

        # XSUB: 发布者连接这里
        self.backend = self.context.socket(zmq.XSUB)
        self.backend.bind(self.backend_address)

        logger.info("Broker is running...")

        try:
            # 使用 ZMQ 内置的代理功能，自动转发消息
            zmq.proxy(self.frontend, self.backend)
        except KeyboardInterrupt:
            logger.info("Broker shutting down...")
        finally:
            self.stop()

    def stop(self):
        """停止 Broker"""
        if self.frontend:
            self.frontend.close()
        if self.backend:
            self.backend.close()
        if self.context:
            self.context.term()
        logger.info("Broker stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    broker = MessageBroker()
    broker.start()
