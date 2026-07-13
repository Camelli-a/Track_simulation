"""
视景系统驱动桥接模块（ZMQ → ScenerySource UDP）

职责：
    订阅 ZMQ bus 上的 train_state 消息，通过 visual_mapping 把内部里程坐标
    转换成视景协议的 edge_id + section_distance(mm)，再交给 ScenerySource
    每 100ms 发一帧 UDP 给视景控制机。

    数据流：
        ATO 进程
            └─ publish("train_state", {...position_m, speed_mps, ...})
                        ↓ ZMQ bus
        SceneryDriver.on_train_state()
            └─ scenery_source.update_own_train_from_state(data)
                        ↓ visual_mapping: position_m → edge_id + offset_mm
        ScenerySource._send_loop()
            └─ UDP 帧 → 视景控制机 18.32.115.28:8303

使用方式（在 main.py lifespan 里）：
    from app.communication.scenery_driver import SceneryDriver
    scenery_driver = SceneryDriver(bus=bus)
    scenery_driver.start()
    ...
    scenery_driver.stop()
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from app.communication.scenery_source import ScenerySource

if TYPE_CHECKING:
    from app.communication.message_bus import MessageBus

logger = logging.getLogger(__name__)

# 多车时：本车 vehicle_id，其余进 other_trains
OWN_VEHICLE_ID = "TRAIN-001"

# 超过此秒数没有收到 train_state，记一条警告
STALE_WARN_SEC = 3.0


class SceneryDriver:
    """
    桥接 ZMQ bus 与 ScenerySource。

    - 订阅 "train_state" 主题
    - 本车（OWN_VEHICLE_ID）→ update_own_train_from_state()
    - 他车（其他 vehicle_id） → update_other_trains()（按需启用）
    """

    def __init__(
        self,
        bus: "MessageBus",
        own_vehicle_id: str = OWN_VEHICLE_ID,
        scenery_host: str | None = None,
        scenery_port: int | None = None,
        local_port: int | None = None,
    ):
        self._bus = bus
        self._own_vehicle_id = own_vehicle_id

        self._source = ScenerySource(
            scenery_host=scenery_host,
            scenery_port=scenery_port,
            local_port=local_port,
        )

        self._last_received: float = 0.0
        self._msg_count: int = 0

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self) -> None:
        """启动 ScenerySource UDP 发送线程，并订阅 ZMQ train_state。"""
        self._source.start()
        self._bus.subscribe("train_state", self._on_train_state)
        logger.info(
            "SceneryDriver started — own_vehicle=%s → %s:%s",
            self._own_vehicle_id,
            self._source.scenery_host,
            self._source.scenery_port,
        )

    def stop(self) -> None:
        """停止 UDP 发送，取消 ZMQ 订阅。"""
        self._bus.unsubscribe("train_state", self._on_train_state)
        self._source.stop()
        logger.info(
            "SceneryDriver stopped (messages_processed=%d)", self._msg_count
        )

    # ------------------------------------------------------------------
    # 内部：直接暴露 ScenerySource，供信号组调用 update_signal / update_switch
    # ------------------------------------------------------------------

    @property
    def source(self) -> ScenerySource:
        """返回底层 ScenerySource，信号模块可直接调用 update_signal()。"""
        return self._source

    # ------------------------------------------------------------------
    # ZMQ 回调
    # ------------------------------------------------------------------

    def _on_train_state(self, topic: str, data: dict) -> None:
        """bus.subscribe 回调，从任意线程调用，内部全部是线程安全操作。"""
        vehicle_id = (
            data.get("vehicle_id")
            or data.get("train_id")
            or data.get("id")
        )

        if str(vehicle_id) == self._own_vehicle_id:
            ok = self._source.update_own_train_from_state(data)
            if ok:
                self._last_received = time.monotonic()
                self._msg_count += 1
                if self._msg_count % 100 == 1:
                    # 每 100 条打一次摘要日志（100ms 周期 ≈ 每 10s 一次）
                    st = self._source.get_state()
                    logger.debug(
                        "SceneryDriver [#%d] edge=%s dist=%dmm speed=%dmm/s dir=%s",
                        self._msg_count,
                        st["edge_id"],
                        st["section_dist"],
                        st["speed_mmps"],
                        st["direction"],
                    )
            else:
                logger.warning(
                    "SceneryDriver: visual mapping failed for vehicle=%s position_m=%s",
                    vehicle_id,
                    data.get("position_m", data.get("position")),
                )
        else:
            # 他车暂时忽略（如需多车联调，在此扩展）
            pass

    def check_stale(self) -> bool:
        """
        返回 True 表示已超时未收到数据。
        可在健康检查或告警逻辑里调用。
        """
        if self._last_received == 0.0:
            return True
        return (time.monotonic() - self._last_received) > STALE_WARN_SEC

    def status(self) -> dict:
        """返回当前运行状态摘要。"""
        return {
            "own_vehicle_id": self._own_vehicle_id,
            "messages_processed": self._msg_count,
            "stale": self.check_stale(),
            "source": self._source.status(),
        }
