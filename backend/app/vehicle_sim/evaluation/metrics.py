import json
from pathlib import Path


def load_jsonl(path: str):
    records = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                records.append(json.loads(line))
    return records


def evaluate_run(
    path: str,
    target_stop_position: float | None = None,
    vehicle_id: str | None = "TRAIN-001",
) -> dict:
    records = load_jsonl(path)

    train_states = [r for r in records if r.get("type") == "train_state"]
    if vehicle_id is not None:
        train_states = [
            state for state in train_states if state.get("vehicle_id") == vehicle_id
        ]
    alarms = [r for r in records if r.get("type") == "alarm_event"]

    if not train_states:
        return {
            "ok": False,
            "message": "No train_state records found",
        }

    speeds = [float(s.get("speed", 0.0)) for s in train_states]
    accelerations = [float(s.get("acceleration", 0.0)) for s in train_states]
    positions = [float(s.get("position", 0.0)) for s in train_states]
    final_position = positions[-1]

    result = {
        "ok": True,
        "vehicle_id": vehicle_id,
        "records": len(train_states),
        "max_speed_kmh": round(max(speeds), 3),
        "max_acceleration_ms2": round(max(accelerations), 3),
        "max_deceleration_ms2": round(min(accelerations), 3),
        "emergency_count": sum(
            1 for state in train_states if state.get("emergency_brake")
        ),
        "alarm_count": len(alarms),
        "final_position_m": round(final_position, 3),
    }

    if target_stop_position is not None:
        result["target_stop_position_m"] = target_stop_position
        result["final_stop_error_m"] = round(
            abs(final_position - target_stop_position),
            3,
        )

    return result
