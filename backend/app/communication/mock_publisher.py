"""
Mock 数据发布器
当其他模块还未就绪时，定时发送假数据到 ZMQ 总线，用于验证通信流程
"""
import time
import random
import logging
import threading
from app.communication.message_bus import MessageBus

logger = logging.getLogger(__name__)


class MockPublisher:
    """Mock 数据发布器"""

    def __init__(self, interval: float = 1.0):
        """
        Args:
            interval: 发布间隔（秒）
        """
        self.interval = interval
        self.bus = MessageBus()
        self._running = False
        self._thread: threading.Thread = None

    def start(self):
        """启动 Mock 发布器"""
        self.bus.start()
        self._running = True
        self._thread = threading.Thread(
            target=self._publish_loop,
            daemon=True,
            name="MockPublisher"
        )
        self._thread.start()
        logger.info(f"MockPublisher started (interval={self.interval}s)")

    def stop(self):
        """停止发布"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self.bus.stop()
        logger.info("MockPublisher stopped")

    def _publish_loop(self):
        """后台线程：定时发布 Mock 数据"""
        while self._running:
            try:
                self._publish_train_state()
                self._publish_signal_state()
                self._publish_ma_state()
                self._publish_power_state()
                self._publish_comm_state()

                # 随机发送告警
                if random.random() < 0.1:  # 10% 概率
                    self._publish_alarm()

                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error in mock publish loop: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # 各消息类型的 Mock 数据生成
    # ------------------------------------------------------------------

    def _publish_train_state(self):
        """车辆状态"""
        data = {
            "vehicle_id": "TRAIN-001",
            "line_id": "LINE-1",
            "position": round(random.uniform(0, 5000), 1),
            "speed": round(random.uniform(0, 120), 1),
            "acceleration": round(random.uniform(-1.5, 1.5), 2),
            "mode": random.choice(["manual", "ato", "atp"]),
            "is_running": True,
            "emergency_brake": False,
        }
        self.bus.publish("train_state", data)

    def _publish_signal_state(self):
        """信号状态"""
        states = ["red", "yellow", "green"]
        data = {
            "system_mode": "normal",
            "signals": [
                {
                    "signal_id": f"SIG-{i:02d}",
                    "position": i * 500.0,
                    "state": random.choice(states),
                }
                for i in range(1, 11)
            ],
            "sections": [
                {
                    "section_id": f"SEG-{i:02d}",
                    "start": i * 500.0,
                    "end": (i + 1) * 500.0,
                    "occupied": random.choice([True, False]),
                    "vehicle_id": "TRAIN-001" if random.random() < 0.3 else None,
                    "condition": "normal",
                }
                for i in range(10)
            ],
            "switches": [
                {
                    "switch_id": f"SW-{i:02d}",
                    "position": random.choice(["normal", "reverse"]),
                    "locked": random.choice([True, False]),
                    "related_section": f"SEG-{i:02d}",
                }
                for i in range(1, 4)
            ],
        }
        self.bus.publish("signal_state", data)

    def _publish_ma_state(self):
        """移动授权"""
        data = {
            "ma_limits": [
                {
                    "vehicle_id": "TRAIN-001",
                    "ma_limit": round(random.uniform(1000, 3000), 1),
                    "target_speed": round(random.uniform(40, 80), 1),
                    "reason": random.choice(["front_train", "switch_locked", "station_stop"]),
                }
            ]
        }
        self.bus.publish("ma_state", data)

    def _publish_power_state(self):
        """供电状态"""
        data = {
            "substation_id": "SS-01",
            "voltage": round(random.uniform(1450, 1550), 2),
            "current": round(random.uniform(200, 400), 2),
            "power": round(random.uniform(300, 600), 2),
            "is_fault": False,
        }
        self.bus.publish("power_state", data)

    def _publish_comm_state(self):
        """通信状态"""
        data = {
            "source": "mock",
            "driver_console_connected": True,
            "zmq_connected": True,
            "last_message_at": time.time(),
        }
        self.bus.publish("comm_state", data)

    def _publish_alarm(self):
        """告警事件"""
        data = {
            "alarm_id": f"ALM-{random.randint(1, 999):03d}",
            "level": random.choice(["info", "warning", "critical"]),
            "source": random.choice(["ATP", "ATO", "SIGNAL", "POWER", "COMM"]),
            "vehicle_id": "TRAIN-001" if random.random() < 0.5 else None,
            "message": random.choice([
                "Train is close to MA limit",
                "Signal timeout detected",
                "Power voltage drop",
                "Communication latency high",
            ]),
        }
        self.bus.publish("alarm_event", data)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    publisher = MockPublisher(interval=2.0)
    publisher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        publisher.stop()
