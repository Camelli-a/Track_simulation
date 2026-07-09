from app.vehicle_sim.evaluation.metrics import evaluate_run
from app.vehicle_sim.evaluation.recorder import RunRecorder
from app.vehicle_sim.adapters.command_mapping import command_percent_to_levels
from app.vehicle_sim.adapters.id_mapping import vehicle_id_to_index
from app.vehicle_sim.adapters.units import m_to_cm, ms_to_cms
from app.vehicle_sim.adapters.vehicle_udp_codec import (
    INPUT_PACKET_SIZE,
    OUTPUT_PACKET_SIZE,
    pack_vehicle_input,
    pack_vehicle_output,
    unpack_vehicle_input,
)
from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.scenario.scenario_runner import ScenarioRunner
from app.vehicle_sim.scenario.scenarios import (
    comm_lost_brake,
    normal_station_stop,
    power_fault_brake,
)
from app.vehicle_sim.train_manager import TrainManager


def run_adapter_checks():
    assert vehicle_id_to_index("TRAIN-001") == 1
    assert ms_to_cms(10.0) == 1000
    assert m_to_cm(12.34) == 1234

    output = pack_vehicle_output(
        {1: {"acceleration": 0.3, "speed": 12.5, "mileage": 123.4}}
    )
    assert len(output) == OUTPUT_PACKET_SIZE

    input_packet = pack_vehicle_input(
        {
            1: {"command": 1, "percent": 50.0},
            2: {"command": 2, "percent": 75.0},
        }
    )
    assert len(input_packet) == INPUT_PACKET_SIZE
    commands = unpack_vehicle_input(input_packet)
    assert commands[1]["traction_level"] == 2
    assert commands[2]["brake_level"] == 3
    assert command_percent_to_levels(1, 50.0) == (2, 0)
    assert command_percent_to_levels(2, 75.0) == (0, 3)


def test_dynamic_train_manager_initial_count():
    manager = TrainManager()
    assert len(manager.trains) == 10
    for slot in range(1, 11):
        assert manager.get_train_by_slot(slot) is not None


def test_add_train_auto_slot():
    manager = TrainManager()
    manager.remove_train(vehicle_id="TRAIN-003")
    result = manager.add_train(vehicle_id="TRAIN-099")
    assert result["ok"] is True
    assert result["train_index"] == 3
    assert manager.get_slot("TRAIN-099") == 3


def test_add_train_beyond_udp_slots():
    manager = TrainManager()
    for _ in range(15):
        result = manager.add_train()
        assert result["ok"] is True
    assert len(manager.trains) == 25
    assert manager.get_train_by_slot(21) is not None
    assert manager.get_train_by_slot(25) is not None


def test_remove_train():
    manager = TrainManager()
    result = manager.remove_train(vehicle_id="TRAIN-003")
    assert result["ok"] is True
    assert manager.get_train("TRAIN-003") is None
    assert manager.get_train_by_slot(3) is None
    assert manager.get_slot("TRAIN-003") is None


def test_clear_and_reset():
    manager = TrainManager()
    manager.clear_trains()
    assert len(manager.trains) == 0
    assert manager.step_all(0.1) == []
    manager.reset_trains(5)
    assert len(manager.trains) == 5
    assert manager.get_train_by_slot(5) is not None
    assert manager.get_train_by_slot(6) is None


def test_vehicle_udp_output_packet_size():
    manager = TrainManager()
    manager.reset_trains(5)
    packet = pack_vehicle_output(manager)
    assert len(packet) == OUTPUT_PACKET_SIZE


def test_vehicle_udp_input_unpack():
    packet = pack_vehicle_input(
        {
            1: {"command": 1, "percent": 50.0},
            2: {"command": 2, "percent": 75.0},
        }
    )
    commands = unpack_vehicle_input(packet)
    assert commands[1]["command"] == 1
    assert commands[1]["percent"] == 50.0
    assert commands[2]["command"] == 2
    assert commands[2]["percent"] == 75.0
    assert command_percent_to_levels(commands[1]["command"], commands[1]["percent"]) == (2, 0)
    assert command_percent_to_levels(commands[2]["command"], commands[2]["percent"]) == (0, 3)


def test_apply_udp_commands_only_active_trains():
    manager = TrainManager()
    manager.reset_trains(2)
    commands = {
        1: {"command": 1, "percent": 50.0},
        2: {"command": 2, "percent": 75.0},
        20: {"command": 1, "percent": 100.0},
    }
    outputs = manager.apply_udp_commands(commands, dt=0.1)
    assert len(outputs) == 2
    assert manager.get_train_by_slot(1).current_traction_level == 2
    assert manager.get_train_by_slot(1).current_brake_level == 0
    assert manager.get_train_by_slot(2).current_traction_level == 0
    assert manager.get_train_by_slot(2).current_brake_level == 3
    assert manager.get_train_by_slot(20) is None


def run_dynamic_manager_checks():
    test_dynamic_train_manager_initial_count()
    test_add_train_auto_slot()
    test_add_train_beyond_udp_slots()
    test_remove_train()
    test_clear_and_reset()
    test_vehicle_udp_output_packet_size()
    test_vehicle_udp_input_unpack()
    test_apply_udp_commands_only_active_trains()


def run_dynamic_scenario_check():
    manager = TrainManager()
    router = MessageRouter(manager)
    from app.vehicle_sim.scenario.scenarios import dynamic_train_management

    scenario = dynamic_train_management()
    runner = ScenarioRunner(scenario, router, realtime=False)
    runner.start()
    while not runner.is_finished():
        runner.tick()
        manager.step_all(0.5)
        runner.advance(0.5)

    assert len(manager.trains) == 5
    assert manager.get_train_by_slot(5) is not None
    assert manager.get_train_by_slot(6) is None


def run_scenario(factory, target_stop_position=None):
    manager = TrainManager()
    router = MessageRouter(manager)
    scenario = factory()
    runner = ScenarioRunner(scenario, router, realtime=False)
    recorder = RunRecorder("logs/vehicle_runs_regression")
    runner.start()

    while not runner.is_finished():
        runner.tick()
        for state in manager.step_all(0.2):
            recorder.record_train_state(state)
        for train in manager.trains.values():
            if train.last_alarm is not None:
                recorder.record_alarm(train.last_alarm)
                train.last_alarm = None
        runner.advance(0.2)

    return evaluate_run(str(recorder.path), target_stop_position)


def main():
    run_adapter_checks()
    run_dynamic_manager_checks()
    run_dynamic_scenario_check()

    normal = run_scenario(normal_station_stop, 1500.0)
    assert normal["ok"]
    assert normal["emergency_count"] == 0
    assert normal["final_stop_error_m"] < 15.0

    power = run_scenario(power_fault_brake)
    assert power["ok"]
    assert power["emergency_count"] > 0
    assert power["alarm_count"] > 0

    comm = run_scenario(comm_lost_brake)
    assert comm["ok"]
    assert comm["emergency_count"] > 0
    assert comm["alarm_count"] > 0

    print("vehicle_sim regression passed")
    print("adapter checks passed")
    print("dynamic train manager checks passed")
    print("normal_station_stop:", normal)
    print("power_fault_brake:", power)
    print("comm_lost_brake:", comm)


if __name__ == "__main__":
    main()
