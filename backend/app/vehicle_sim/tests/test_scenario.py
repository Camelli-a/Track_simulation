from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.scenario.scenario_runner import ScenarioRunner
from app.vehicle_sim.scenario.scenarios import power_fault_brake
from app.vehicle_sim.train_manager import TrainManager


def test_power_fault_scenario_triggers_emergency():
    manager = TrainManager()
    router = MessageRouter(manager)
    scenario = power_fault_brake()
    runner = ScenarioRunner(scenario, router, realtime=False)
    runner.start()

    for _ in range(80):
        runner.tick()
        manager.step_all(0.1)
        runner.advance(0.1)

    train = manager.get_train("TRAIN-001")
    assert train.state.emergency_brake is True
    assert train.state.mode == "emergency"
