from .scenario_models import Scenario, ScenarioEvent


def normal_station_stop() -> Scenario:
    return Scenario(
        name="normal_station_stop",
        description="Fallback ATO normal station stopping scenario",
        duration_sec=70.0,
        events=[
            ScenarioEvent(
                0.0,
                {
                    "type": "set_train_state",
                    "vehicle_id": "TRAIN-001",
                    "position": 1300.0,
                    "speed": 30.0,
                    "mode": "ato",
                },
            ),
            ScenarioEvent(
                0.0,
                {
                    "type": "ma_state",
                    "ma_limits": [
                        {
                            "vehicle_id": "TRAIN-001",
                            "ma_limit": 1800.0,
                            "target_speed": 60.0,
                            "reason": "station_stop",
                        }
                    ],
                },
            ),
            ScenarioEvent(
                0.0,
                {
                    "type": "enable_fallback_ato",
                    "vehicle_id": "TRAIN-001",
                    "target_position": 1500.0,
                },
            ),
        ],
    )


def overspeed_atp() -> Scenario:
    return Scenario(
        name="overspeed_atp",
        description="Manual overspeed triggers ATP emergency brake",
        duration_sec=20.0,
        events=[
            ScenarioEvent(
                0.0,
                {
                    "type": "set_train_state",
                    "vehicle_id": "TRAIN-001",
                    "position": 1000.0,
                    "speed": 40.0,
                    "mode": "manual",
                },
            ),
            ScenarioEvent(
                0.0,
                {
                    "type": "driver_input",
                    "vehicle_id": "TRAIN-001",
                    "line_id": "LINE-1",
                    "source": "mock",
                    "control_mode": "manual",
                    "traction_level": 4,
                    "brake_level": 0,
                    "direction": "forward",
                    "emergency_button": False,
                },
            ),
        ],
    )


def ma_limit_brake() -> Scenario:
    return Scenario(
        name="ma_limit_brake",
        description="MA limit shrinks and train triggers ATP brake",
        duration_sec=25.0,
        events=[
            ScenarioEvent(
                0.0,
                {
                    "type": "driver_input",
                    "vehicle_id": "TRAIN-001",
                    "line_id": "LINE-1",
                    "source": "mock",
                    "control_mode": "manual",
                    "traction_level": 3,
                    "brake_level": 0,
                    "direction": "forward",
                    "emergency_button": False,
                },
            ),
            ScenarioEvent(
                8.0,
                {
                    "type": "ma_state",
                    "ma_limits": [
                        {
                            "vehicle_id": "TRAIN-001",
                            "ma_limit": 50.0,
                            "target_speed": 20.0,
                            "reason": "front_train",
                        }
                    ],
                },
            ),
        ],
    )


def power_fault_brake() -> Scenario:
    return Scenario(
        name="power_fault_brake",
        description="Power fault triggers emergency brake",
        duration_sec=15.0,
        events=[
            ScenarioEvent(
                0.0,
                {
                    "type": "driver_input",
                    "vehicle_id": "TRAIN-001",
                    "line_id": "LINE-1",
                    "source": "mock",
                    "control_mode": "manual",
                    "traction_level": 3,
                    "brake_level": 0,
                    "direction": "forward",
                    "emergency_button": False,
                },
            ),
            ScenarioEvent(
                6.0,
                {
                    "type": "power_state",
                    "substation_id": "SS-01",
                    "voltage": 900.0,
                    "current": 0.0,
                    "power": 0.0,
                    "is_fault": True,
                },
            ),
        ],
    )


def comm_lost_brake() -> Scenario:
    return Scenario(
        name="comm_lost_brake",
        description="Communication lost triggers emergency brake",
        duration_sec=15.0,
        events=[
            ScenarioEvent(
                0.0,
                {
                    "type": "driver_input",
                    "vehicle_id": "TRAIN-001",
                    "line_id": "LINE-1",
                    "source": "mock",
                    "control_mode": "manual",
                    "traction_level": 3,
                    "brake_level": 0,
                    "direction": "forward",
                    "emergency_button": False,
                },
            ),
            ScenarioEvent(
                6.0,
                {
                    "type": "comm_state",
                    "source": "mock",
                    "driver_console_connected": False,
                    "zmq_connected": False,
                    "last_message_at": 0.0,
                },
            ),
        ],
    )


SCENARIOS = {
    "normal_station_stop": normal_station_stop,
    "overspeed_atp": overspeed_atp,
    "ma_limit_brake": ma_limit_brake,
    "power_fault_brake": power_fault_brake,
    "comm_lost_brake": comm_lost_brake,
}
