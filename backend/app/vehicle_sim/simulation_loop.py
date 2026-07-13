"""
Simulation loop — drives all Train objects at a fixed tick rate and
bridges the results to the rest of the system.

Responsibilities per tick (every 100 ms):
  1. Call TrainManager.step_all() → physics + ATO recommendation
  2. Publish each train's train_state to the shared MessageBus (ZMQ)
     so the ZmqDashboardListener / SpeedCurveRecorder pick it up.
  3. Push each train's state into state_store directly (avoids a ZMQ
     round-trip when the broker is not running).
  4. If a PlcFeedbackAggregator is attached, feed it the latest
     train_state so it can call send_to_plc() with real values.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.communication.plc_feedback_aggregator import PlcFeedbackAggregator
    from app.communication.message_bus import MessageBus
    from app.vehicle_sim.train_manager import TrainManager

logger = logging.getLogger(__name__)

DT = 0.1  # simulation time step, seconds
PUBLISH_INTERVAL = 0.1  # how often to publish to ZMQ / state_store


class SimulationLoop:
    """Async background task that ticks the vehicle simulation."""

    def __init__(
        self,
        train_manager: "TrainManager",
        *,
        dt: float = DT,
        plc_aggregator: "PlcFeedbackAggregator | None" = None,
        zmq_bus: "MessageBus | None" = None,
    ) -> None:
        self._manager = train_manager
        self._dt = float(dt)
        self._plc_aggregator = plc_aggregator
        self._zmq_bus = zmq_bus
        self._task: asyncio.Task | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="simulation-loop")
        logger.info("SimulationLoop started (dt=%.0f ms)", self._dt * 1000)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SimulationLoop stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        from app.data_flow.state_store import state_store

        next_tick = asyncio.get_event_loop().time()
        while self._running:
            now_loop = asyncio.get_event_loop().time()
            if now_loop < next_tick:
                await asyncio.sleep(next_tick - now_loop)

            next_tick += self._dt

            try:
                protocol_states = await asyncio.to_thread(
                    self._manager.step_all, self._dt
                )
            except Exception:
                logger.exception("SimulationLoop: step_all failed")
                continue

            now_wall = time.time()

            for proto in protocol_states:
                vehicle_id = proto.get("vehicle_id")
                if not vehicle_id:
                    continue

                # 1. Push into state_store (direct, no ZMQ round-trip needed)
                state_store.update_train(vehicle_id, proto)

                # 2. Feed SpeedCurveRecorder directly so the speed curve is
                #    always populated regardless of DATA_SOURCE mode.
                #    In zmq mode we also publish to ZMQ (step 3) which would
                #    reach the recorder via ZmqDashboardListener.dispatch, but
                #    calling on_train_state directly here is safe (idempotent).
                try:
                    from app.speed_curve.recorder import speed_curve_recorder
                    speed_curve_recorder.on_train_state(vehicle_id, proto)
                except Exception:
                    logger.debug(
                        "SimulationLoop: failed to feed speed_curve_recorder for %s",
                        vehicle_id,
                    )

                # 3. Publish to ZMQ bus so ZmqDashboardListener and any
                #    external subscribers (signal worker etc.) get the data.
                if self._zmq_bus is not None:
                    try:
                        self._zmq_bus.publish("train_state", proto)
                    except Exception:
                        logger.debug(
                            "SimulationLoop: failed to publish train_state for %s",
                            vehicle_id,
                        )

                # 4. Feed PlcFeedbackAggregator so it can call send_to_plc()
                #    with real speed / door / ATO state from the simulation.
                if self._plc_aggregator is not None:
                    self._plc_aggregator.on_message("train_state", proto)
