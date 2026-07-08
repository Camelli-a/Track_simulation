from app.vehicle_sim.evaluation.metrics import evaluate_run
from app.vehicle_sim.evaluation.recorder import RunRecorder
from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.scenario.scenario_runner import ScenarioRunner
from app.vehicle_sim.scenario.scenarios import (
    comm_lost_brake,
    normal_station_stop,
    power_fault_brake,
)
from app.vehicle_sim.train_manager import TrainManager


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
    print("normal_station_stop:", normal)
    print("power_fault_brake:", power)
    print("comm_lost_brake:", comm)


if __name__ == "__main__":
    main()
