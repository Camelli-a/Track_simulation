from .adapters.command_mapping import command_percent_to_levels
from .adapters.id_mapping import MAX_TRAINS, index_to_vehicle_id, vehicle_id_to_index
from .mock_data import DEFAULT_TRACK
from .models import DriverInput
from .track_map import TrackMap
from .train import Train

DEFAULT_INITIAL_TRAINS = 10


class TrainManager:
    def __init__(self, initial_count: int = DEFAULT_INITIAL_TRAINS):
        self.track = TrackMap(DEFAULT_TRACK)
        self.trains: dict[str, Train] = {}
        self.slot_to_vehicle_id: dict[int, str] = {}
        self.vehicle_id_to_slot: dict[str, int] = {}
        self.reset_trains(initial_count)

    def add_train(
        self,
        vehicle_id: str | None = None,
        slot: int | None = None,
        position: float = 0.0,
        line_id: str = "LINE-1",
    ) -> dict:
        if len(self.trains) >= MAX_TRAINS:
            return {"ok": False, "reason": "max_trains_reached"}

        if slot is None:
            slot = self._first_free_slot()
        if slot is None:
            return {"ok": False, "reason": "no_free_slot"}
        if not 1 <= slot <= MAX_TRAINS:
            return {"ok": False, "reason": "slot_out_of_range", "slot": slot}
        if slot in self.slot_to_vehicle_id:
            return {"ok": False, "reason": "slot_occupied", "slot": slot}

        if vehicle_id is None:
            vehicle_id = index_to_vehicle_id(slot)
        if vehicle_id in self.trains:
            return {
                "ok": False,
                "reason": "vehicle_id_exists",
                "vehicle_id": vehicle_id,
            }

        train = Train(vehicle_id, line_id, self.track, train_index=slot)
        train.state.position = float(position)
        train.state.is_running = train.state.speed_ms > 0.0
        self.trains[vehicle_id] = train
        self.slot_to_vehicle_id[slot] = vehicle_id
        self.vehicle_id_to_slot[vehicle_id] = slot
        return {
            "ok": True,
            "vehicle_id": vehicle_id,
            "train_index": slot,
            "position": train.state.position,
            "line_id": line_id,
        }

    def remove_train(
        self,
        vehicle_id: str | None = None,
        slot: int | None = None,
    ) -> dict:
        if vehicle_id is None and slot is not None:
            vehicle_id = self.slot_to_vehicle_id.get(slot)
        if vehicle_id is None:
            return {"ok": False, "reason": "missing_vehicle_id_or_slot"}

        slot = self.vehicle_id_to_slot.get(vehicle_id)
        if slot is None or vehicle_id not in self.trains:
            return {
                "ok": False,
                "reason": "train_not_found",
                "vehicle_id": vehicle_id,
            }

        del self.trains[vehicle_id]
        self.vehicle_id_to_slot.pop(vehicle_id, None)
        self.slot_to_vehicle_id.pop(slot, None)
        return {"ok": True, "vehicle_id": vehicle_id, "train_index": slot}

    def clear_trains(self) -> dict:
        removed = len(self.trains)
        self.trains.clear()
        self.slot_to_vehicle_id.clear()
        self.vehicle_id_to_slot.clear()
        return {"ok": True, "removed": removed}

    def reset_trains(self, count: int = DEFAULT_INITIAL_TRAINS) -> dict:
        count = max(0, min(int(count), MAX_TRAINS))
        self.clear_trains()
        for slot in range(1, count + 1):
            self.add_train(
                slot=slot,
                position=self._default_position_for_slot(slot),
            )
        return {"ok": True, "count": count}

    def list_trains(self) -> list[dict]:
        return [
            {
                "vehicle_id": vehicle_id,
                "train_index": slot,
                "line_id": self.trains[vehicle_id].state.line_id,
                "position": self.trains[vehicle_id].state.position,
                "speed": self.trains[vehicle_id].state.speed_kmh,
                "mode": self.trains[vehicle_id].state.mode,
                "emergency_brake": self.trains[vehicle_id].state.emergency_brake,
            }
            for slot, vehicle_id in sorted(self.slot_to_vehicle_id.items())
        ]

    def get_train(self, vehicle_id: str):
        return self.trains.get(vehicle_id)

    def get_train_by_slot(self, slot: int):
        vehicle_id = self.slot_to_vehicle_id.get(slot)
        if vehicle_id is None:
            return None
        return self.get_train(vehicle_id)

    def get_slot(self, vehicle_id: str) -> int | None:
        return self.vehicle_id_to_slot.get(vehicle_id)

    def apply_udp_commands(
        self,
        commands: dict[int, dict],
        dt: float = 0.1,
    ) -> list[dict]:
        outputs = []
        for slot in range(1, MAX_TRAINS + 1):
            train = self.get_train_by_slot(slot)
            if train is None:
                continue

            command = commands.get(slot, {})
            traction_level, brake_level = command_percent_to_levels(
                int(command.get("command", 0)),
                float(command.get("percent", 0.0)),
            )
            driver_input = DriverInput(
                vehicle_id=train.state.vehicle_id,
                line_id=train.state.line_id,
                source="vehicle_udp",
                control_mode="manual",
                traction_level=traction_level,
                brake_level=brake_level,
                direction="forward",
                emergency_button=False,
                command=command.get("command", 0),
                percent=command.get("percent", 0.0),
            )
            train.step_manual(driver_input, dt)
            outputs.append(train.state.to_protocol())
        return outputs

    def step_all(self, dt: float):
        outputs = []
        for slot in sorted(self.slot_to_vehicle_id):
            train = self.get_train_by_slot(slot)
            if train is None:
                continue
            train.step_tick(dt)
            outputs.append(train.state.to_protocol())
        return outputs

    def _first_free_slot(self) -> int | None:
        for slot in range(1, MAX_TRAINS + 1):
            if slot not in self.slot_to_vehicle_id:
                return slot
        return None

    def _default_position_for_slot(self, slot: int) -> float:
        if slot == 1:
            return 0.0
        if slot == 2:
            return 300.0
        if slot == 3:
            return 700.0
        return float((slot - 1) * 300.0)
