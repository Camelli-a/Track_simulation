"""
UDP 接入测试脚本
验证：司机台模拟器 → UDPSource → ZMQ 总线 → 订阅者 全流程

使用方式（需要 3 个终端）：
    终端1: python -m app.communication.broker
    终端2: python -m app.communication.test_udp
    终端3: python -m app.communication.udp_simulator
"""
import logging
import time
from app.communication.udp_source import UDPSource
from app.communication.message_bus import MessageBus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    # 共用一个 MessageBus（也可以让 UDPSource 自己创建）
    bus = MessageBus()
    bus.start()

    # 订阅 train_state，验证消息是否流通
    received = {"count": 0}

    def on_train_state(topic: str, data: dict):
        received["count"] += 1
        source_tag = " [占位数据]" if data.get("_source") == "udp_placeholder" else ""
        logger.info(
            f"[#{received['count']}] train_state{source_tag} → "
            f"vehicle={data.get('vehicle_id')} "
            f"speed={data.get('speed')} km/h "
            f"position={data.get('position')} m"
        )

    bus.subscribe("train_state", on_train_state)

    # 启动 UDPSource（注入共用 bus）
    source = UDPSource(
        vehicle_id="TRAIN-001",
        bus=bus,
    )
    source.start()

    logger.info("=" * 50)
    logger.info("UDP Source is running.")
    logger.info("Now start the simulator in another terminal:")
    logger.info("  python -m app.communication.udp_simulator")
    logger.info("=" * 50)
    logger.info("Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(5)
            logger.info(f"Status: {source.status()}")
    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        source.stop()
        bus.stop()


if __name__ == "__main__":
    main()
