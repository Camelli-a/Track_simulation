from app.vehicle_sim.atp import check_atp
from app.vehicle_sim.models import TrainState


def test_overspeed_triggers_atp():
    state = TrainState(
        vehicle_id="TRAIN-001",
        line_id="LINE-1",
        position=100.0,
        speed_ms=20.0,
        acceleration=0.0,
        mode="manual",
        is_running=True,
        emergency_brake=False,
    )

    should_brake, alarm = check_atp(
        state=state,
        speed_limit=30.0,
        ma_limit=1000.0,
        power_fault=False,
        comm_ok=True,
    )

    assert should_brake is True
    assert alarm is not None
    assert alarm["source"] == "ATP"
