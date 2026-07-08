from .metrics import evaluate_run


def print_report(
    log_path: str,
    target_stop_position: float | None = None,
    vehicle_id: str | None = "TRAIN-001",
):
    result = evaluate_run(log_path, target_stop_position, vehicle_id)

    print("\n========== Vehicle Simulation Evaluation ==========")

    if not result["ok"]:
        print(result["message"])
        return

    print(f"vehicle_id: {result['vehicle_id']}")
    print(f"records: {result['records']}")
    print(f"max_speed_kmh: {result['max_speed_kmh']}")
    print(f"max_acceleration_ms2: {result['max_acceleration_ms2']}")
    print(f"max_deceleration_ms2: {result['max_deceleration_ms2']}")
    print(f"emergency_count: {result['emergency_count']}")
    print(f"alarm_count: {result['alarm_count']}")
    print(f"final_position_m: {result['final_position_m']}")

    if "final_stop_error_m" in result:
        print(f"target_stop_position_m: {result['target_stop_position_m']}")
        print(f"final_stop_error_m: {result['final_stop_error_m']}")

    print("===================================================\n")
