"""
测试订阅脚本
订阅所有消息，用于调试和验证 ZMQ 总线是否正常工作
"""
import logging
from app.communication.message_bus import MessageBus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)


def on_message(topic: str, data: dict):
    """通用消息处理器"""
    logger.info(f"[{topic}] {data}")


def main():
    bus = MessageBus()
    bus.start()

    # 订阅所有定义的消息类型
    topics = [
        "train_state",
        "signal_state",
        "ma_state",
        "power_state",
        "comm_state",
        "alarm_event",
    ]

    for topic in topics:
        bus.subscribe(topic, on_message)

    logger.info("Test subscriber started, press Ctrl+C to stop")

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping...")
        bus.stop()


if __name__ == "__main__":
    main()
