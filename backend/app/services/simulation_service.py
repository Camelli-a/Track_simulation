"""集中式仿真状态聚合：基于老师提供的线路布局 JSON 推送 Mock 数据。"""
import json
import math
import random
import time
from pathlib import Path
from typing import List, Optional

from app.core.config import settings
from app.schemas.dashboard import (
    DashboardAlarm,
    DashboardSection,
    DashboardSignal,
    DashboardSnapshot,
    DashboardSwitch,
    DashboardSystem,
    DashboardTrain,
)
from app.schemas.power import PowerStatus
from app.schemas.simulation import SimulationTick, StationTick, TrackSegmentTick, TurnoutTick, VehicleTick

LAYOUT_PATH = Path(__file__).resolve().parents[3] / "frontend" / "public" / "data" / "line-layout.json"


def _load_layout() -> dict:
    if LAYOUT_PATH.exists():
        return json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    return {}


class SimulationService:
    def __init__(self) -> None:
        self._layout = _load_layout()
        self._total = float(self._layout.get("total_length_m", 5000.0))
        self._stations: List[dict] = self._layout.get("stations", [])
        self._blocks: List[dict] = self._layout.get("blocks", [])
        self._signals_static: List[dict] = self._layout.get("signals", [])
        self._turnouts_static: List[dict] = self._layout.get("turnouts", [])

        # 在真实线路上分散部署 3 列车（间隔若干站，避免示意图顶部堆叠）
        positions = [800.0, 5200.0, 9800.0]
        if len(self._stations) >= 3:
            indices = [0, len(self._stations) // 3, (len(self._stations) * 2) // 3]
            positions = [self._stations[i]["position"] + 200 for i in indices[:3]]

        self._vehicles: List[dict] = [
            {"vehicle_id": "T01", "line_id": "LINE-1", "position": positions[0], "speed": 65.0, "energy_kwh": 12.4, "drive_mode": "ato"},
            {"vehicle_id": "T02", "line_id": "LINE-1", "position": positions[1], "speed": 48.0, "energy_kwh": 9.8, "drive_mode": "manual"},
            {"vehicle_id": "T03", "line_id": "LINE-1", "position": positions[2], "speed": 42.0, "energy_kwh": 7.2, "drive_mode": "atp"},
        ]
        self._elapsed = 0.0
        self._alarms: List[dict] = []
        self._last_control: Optional[dict] = None

    _SIGNAL_PRIORITY = {"red": 3, "yellow": 2, "green": 1}

    def _signal_state_for_demo(self, position: float, index: int) -> str:
        """Mock 信号机：列车前方红/黄闪 + 沿线演示性闪灯。"""
        t = self._elapsed
        phase = (index * 0.71 + position * 0.00008) % (2 * math.pi)

        min_ahead = self._total
        for v in self._vehicles:
            if v["position"] < position:
                ahead = position - v["position"]
                if ahead < min_ahead:
                    min_ahead = ahead

        # 列车前方防护：红 ↔ 黄 快闪（约 2 Hz）
        if min_ahead < 380:
            return "red" if math.sin(t * 4.2 + phase) > 0.15 else "yellow"

        # 预告区：黄 ↔ 绿 慢闪
        if min_ahead < 1000:
            return "yellow" if math.sin(t * 2.4 + phase) > -0.1 else "green"

        # MA 边界附近：偶发黄灯
        for v in self._vehicles:
            ma = v.get("ma_end")
            if ma and abs(position - ma) < 120 and math.sin(t * 3.1 + phase) > 0.4:
                return "yellow"

        # 远离列车：抽样演示闪灯，便于电子地图验收
        bucket = index % 11
        if bucket == 0 and math.sin(t * 1.4 + phase) > 0.55:
            return "yellow"
        if bucket == 1 and math.sin(t * 1.9 + phase) > 0.6:
            return "red" if math.sin(t * 5.5 + phase) > 0 else "yellow"
        if bucket == 2 and math.sin(t * 0.9 + phase) > 0.72:
            return "yellow"

        return "green"

    def _build_mock_signals(self) -> List["SignalLight"]:
        from app.schemas.signal import SignalLight

        state_by_id: dict[str, str] = {}
        pos_by_id: dict[str, float] = {}

        for i, s in enumerate(self._signals_static):
            sid = s["signal_id"]
            state = self._signal_state_for_demo(float(s["position"]), i)
            prev = state_by_id.get(sid)
            if prev is None or self._SIGNAL_PRIORITY[state] > self._SIGNAL_PRIORITY[prev]:
                state_by_id[sid] = state
                pos_by_id[sid] = float(s["position"])

        return [
            SignalLight(signal_id=sid, position=pos_by_id[sid], state=state)
            for sid, state in state_by_id.items()
        ]

    def next_tick(self, dt: float = 0.2) -> SimulationTick:
        self._elapsed += dt
        now = time.time()

        for vehicle in self._vehicles:
            speed = vehicle["speed"] + math.sin(
                self._elapsed + sum(ord(c) for c in vehicle["vehicle_id"]) % 7
            ) * 2.0
            speed = max(15.0, min(speed, 80.0))
            vehicle["speed"] = round(speed, 1)

            prev = vehicle["position"]
            vehicle["position"] = (vehicle["position"] + speed / 3.6 * dt) % self._total

            vehicle["acceleration"] = round((vehicle["position"] - prev) / dt / 3.6 if dt else 0, 2)
            vehicle["energy_kwh"] = round(vehicle["energy_kwh"] + max(speed, 0) * dt / 3600 * 0.12, 2)

            eb_until = vehicle.pop("_eb_until", None)
            vehicle["emergency_brake"] = bool(eb_until and now < eb_until)

            # ATO 接近站台时 Mock 自动减速
            if vehicle["drive_mode"] == "ato" and vehicle.get("stop_distance", 999) < 400:
                vehicle["speed"] = max(8.0, vehicle["speed"] - 4.0 * dt * 5)

            ma_span = 1200 + (sum(ord(c) for c in vehicle["vehicle_id"]) % 5) * 200
            vehicle["ma_end"] = round(min(vehicle["position"] + ma_span, self._total), 1)

            next_st = self._next_station(vehicle["position"])
            stop_target = next_st["position"] if next_st else vehicle["ma_end"]
            if stop_target >= vehicle["position"]:
                vehicle["stop_distance"] = round(stop_target - vehicle["position"], 1)
                vehicle["station_name"] = next_st["name"] if next_st else None
            else:
                vehicle["stop_distance"] = round(vehicle["ma_end"] - vehicle["position"], 1)
                vehicle["station_name"] = next_st["name"] if next_st else "运行区间"

            vehicle["target_speed_limit"] = (
                round(max(25.0, vehicle["stop_distance"] * 0.15), 1)
                if vehicle["stop_distance"] < 500 else 80.0
            )

            vehicle["parking_phase"] = self._derive_parking_phase(vehicle)
            if vehicle["parking_phase"] in ("stopped", "docking") and vehicle["speed"] < 5:
                vehicle["stop_error_cm"] = round(abs(random.gauss(10, 7)), 1)
            else:
                vehicle["stop_error_cm"] = None

        self._trim_alarms(now)

        segments = self._build_segments()
        stations = [
            StationTick(station_id=s["station_id"], name=s["name"], position=s["position"])
            for s in self._stations
        ] or None

        power = PowerStatus(
            timestamp=now,
            voltage=round(1500 + math.sin(self._elapsed * 0.8) * 30 + random.uniform(-6, 6), 2),
            current=round(260 + sum(v["speed"] for v in self._vehicles) * 0.55, 2),
            power=round(400 + sum(v["speed"] for v in self._vehicles) * 1.1, 2),
            substation_id="SS-01",
            is_fault=False,
        )

        # 信号机：静态位置 + 列车相关红/黄闪（联调后由信号组覆盖）
        signals = self._build_mock_signals()

        turnouts = [
            TurnoutTick(
                turnout_id=t["turnout_id"],
                position=t["position"],
                state="normal",
                locked=i % 3 != 2,
            )
            for i, t in enumerate(self._turnouts_static[:20])
        ]

        return SimulationTick(
            timestamp=now,
            vehicles=[
                VehicleTick(
                    vehicle_id=v["vehicle_id"],
                    position=round(v["position"], 1),
                    speed=v["speed"],
                    acceleration=v["acceleration"],
                    emergency_brake=v["emergency_brake"],
                    energy_kwh=v["energy_kwh"],
                    ma_end=v["ma_end"],
                    drive_mode=v["drive_mode"],
                    target_speed_limit=v["target_speed_limit"],
                    station_name=v.get("station_name"),
                    stop_distance=v.get("stop_distance"),
                    parking_phase=v.get("parking_phase"),
                    stop_error_cm=v.get("stop_error_cm"),
                )
                for v in self._vehicles
            ],
            track_segments=segments,
            stations=stations or [],
            total_length=self._total,
            power=power,
            signals=signals,
            turnouts=turnouts,
            system_mode="normal",
        )

    def next_dashboard_snapshot(self, dt: float = 0.2, websocket_clients: int = 1) -> DashboardSnapshot:
        tick = self.next_tick(dt)
        now = tick.timestamp

        trains = [
            DashboardTrain(
                vehicle_id=v.vehicle_id,
                line_id="LINE-1",
                position=v.position,
                speed=v.speed,
                acceleration=v.acceleration,
                mode=v.drive_mode,
                is_running=True,
                emergency_brake=v.emergency_brake,
                ma_limit=v.ma_end,
                target_speed=v.target_speed_limit,
                energy_kwh=v.energy_kwh,
                stop_distance=v.stop_distance,
                station_name=v.station_name,
                parking_phase=v.parking_phase,
                stop_error_cm=v.stop_error_cm,
                updated_at=now,
            )
            for v in tick.vehicles
        ]

        sections = [
            DashboardSection(
                section_id=s.segment_id,
                start=s.start,
                end=s.end,
                occupied=s.occupied,
                vehicle_id=s.occupied_by,
                condition=s.condition,
                aspect=s.aspect,
            )
            for s in tick.track_segments
        ]

        signals = [
            DashboardSignal(signal_id=s.signal_id, position=s.position, state=s.state)
            for s in tick.signals
        ]

        switches = [
            DashboardSwitch(
                switch_id=t.turnout_id,
                routing=t.state,
                locked=t.locked,
            )
            for t in tick.turnouts
        ]

        alarms = [
            DashboardAlarm(
                alarm_id=a["alarm_id"],
                level=a["level"],
                source=a["source"],
                vehicle_id=a.get("vehicle_id"),
                message=a["message"],
                timestamp=a["timestamp"],
            )
            for a in self._alarms
        ]

        return DashboardSnapshot(
            timestamp=now,
            system=DashboardSystem(
                status="emergency" if tick.system_mode == "emergency" else "running",
                data_source=settings.DATA_SOURCE,
                zmq_connected=settings.DATA_SOURCE == "zmq",
                websocket_clients=websocket_clients,
            ),
            trains=trains,
            sections=sections,
            signals=signals,
            switches=switches,
            power=tick.power,
            alarms=alarms,
        )

    def apply_control(
        self,
        vehicle_id: str,
        command: str,
        level: float = 1.0,
        source: str = "hmi",
    ) -> tuple[bool, str]:
        """接收 HMI 控车指令；联调后 C 转发至 ZMQ / A 组。"""
        for v in self._vehicles:
            if v["vehicle_id"] != vehicle_id:
                continue

            mode = v.get("drive_mode", "manual")
            if mode != "manual" and command != "emergency_brake":
                msg = f"{vehicle_id} 处于 {mode} 模式，已记录 {command} 但不执行"
                self._last_control = {"vehicle_id": vehicle_id, "command": command, "source": source, "accepted": False}
                return True, msg

            if command == "traction":
                v["speed"] = min(80.0, v["speed"] + 3.0 * level)
                msg = f"牵引 +{3.0 * level:.0f} km/h"
            elif command == "brake":
                v["speed"] = max(0.0, v["speed"] - 4.0 * level)
                msg = f"制动 -{4.0 * level:.0f} km/h"
            elif command == "emergency_brake":
                v["speed"] = 0.0
                v["emergency_brake"] = True
                v["_eb_until"] = time.time() + 2.5
                msg = "紧急制动已触发"
            else:
                return False, f"未知指令: {command}"

            self._last_control = {"vehicle_id": vehicle_id, "command": command, "source": source, "accepted": True}
            return True, msg

        return False, f"未找到车辆 {vehicle_id}"

    @staticmethod
    def _derive_parking_phase(vehicle: dict) -> str:
        sd = vehicle.get("stop_distance")
        speed = vehicle.get("speed", 0)
        if sd is None:
            return "cruising"
        if speed < 1 and sd < 5:
            return "stopped"
        if sd < 20 and speed < 8:
            return "docking"
        if sd < 200 and speed < 45:
            return "braking"
        if sd < 800:
            return "approaching"
        return "cruising"

    def _push_alarm(
        self,
        now: float,
        alarm_id: str,
        level: str,
        source: str,
        vehicle_id: Optional[str],
        message: str,
    ) -> None:
        existing = {a["alarm_id"] for a in self._alarms}
        if alarm_id in existing:
            return
        self._alarms.append(
            {
                "alarm_id": alarm_id,
                "level": level,
                "source": source,
                "vehicle_id": vehicle_id,
                "message": message,
                "timestamp": now,
            }
        )

    def _trim_alarms(self, now: float) -> None:
        self._alarms = [a for a in self._alarms if now - a["timestamp"] < 30][-100:]

    def _next_station(self, position: float) -> Optional[dict]:
        for st in self._stations:
            if st["position"] > position + 80:
                return st
        return self._stations[0] if self._stations else None

    def _build_segments(self) -> List[TrackSegmentTick]:
        if not self._blocks:
            return self._fallback_segments()

        segments: List[TrackSegmentTick] = []
        for block in self._blocks:
            start, end = block["start"], block["end"]
            occupant = None
            for v in self._vehicles:
                if start <= v["position"] < end:
                    occupant = v["vehicle_id"]
                    break

            if occupant:
                aspect = "red"
            elif any(start - 300 <= v["position"] < end for v in self._vehicles):
                aspect = "yellow"
            else:
                aspect = "green"

            segments.append(
                TrackSegmentTick(
                    segment_id=block["segment_id"],
                    start=start,
                    end=end,
                    occupied=occupant is not None,
                    aspect=aspect,
                    occupied_by=occupant,
                    condition="normal",
                )
            )
        return segments

    def _fallback_segments(self) -> List[TrackSegmentTick]:
        n = 10
        size = self._total / n
        segments = []
        for i in range(n):
            start = i * size
            end = (i + 1) * size
            occupied = any(start <= v["position"] < end for v in self._vehicles)
            segments.append(
                TrackSegmentTick(
                    segment_id=f"SEG-{i:02d}",
                    start=round(start, 1),
                    end=round(end, 1),
                    occupied=occupied,
                    aspect="red" if occupied else "green",
                    condition="normal",
                )
            )
        return segments


simulation_service = SimulationService()
