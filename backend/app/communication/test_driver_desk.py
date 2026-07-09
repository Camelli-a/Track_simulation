"""
司机台 TCP 接入测试脚本
验证：PLC 模拟器 → DriverDeskSource → ZMQ 总线 → 订阅者 全流程

使用方式（需要 3 个终端）：
    终端1: python -m app.communication.broker
    终端2: python -m app.communication.test_driver_desk
    终端3: python -m app.communication.plc_simulator
"""
import logging
import time
from app.communication.driver_desk_source import DriverDeskSource
from app.communication.message_bus import MessageBus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    bus = MessageBus()
    bus.start()

    received = {"count": 0}

    def on_train_state(topic: str, data: dict):
        received["count"] += 1
        eb = "🚨 EMERGENCY BRAKE" if data.get("emergency_brake") else ""
        logger.info(
            f"[#{received['count']}] "
            f"vehicle={data.get('vehicle_id')} "
            f"speed={data.get('speed'):.1f} km/h "
            f"mode={data.get('mode')} "
            f"door_mode={data.get('door_mode')} "
            f"{eb}"
        )

    bus.subscribe("train_state", on_train_state)

    # 连接到本地模拟器（127.0.0.1:8001）
    source = DriverDeskSource(
        vehicle_id="TRAIN-001",
        plc_host="127.0.0.1",
        plc_port=8001,
        bus=bus,
    )
    source.start()

    logger.info("=" * 55)
    logger.info("DriverDeskSource is running.")
    logger.info("Now start the PLC simulator in another terminal:")
    logger.info("  python -m app.communication.plc_simulator")
    logger.info("=" * 55)
    logger.info("Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(5)
            logger.info(f"Status → {source.status()}")
    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        source.stop()
        bus.stop()


if __name__ == "__main__":
    main()
