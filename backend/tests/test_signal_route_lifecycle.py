import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.signal_route_lifecycle import RouteLifecycleManager  # noqa: E402


class FakeClock:
    def __init__(self, now):
        self.now = now

    def time(self):
        return self.now


def _open_request(vehicle_id="TRAIN-001", route_id="R_MAIN"):
    return {
        "request_id": f"REQ-{vehicle_id}-{route_id}",
        "vehicle_id": vehicle_id,
        "route_id": route_id,
        "request_type": "open",
        "priority": 0,
    }


def _cancel_request(vehicle_id="TRAIN-001", route_id="R_MAIN"):
    return {
        "request_id": f"REQ-CANCEL-{vehicle_id}-{route_id}",
        "vehicle_id": vehicle_id,
        "route_id": route_id,
        "request_type": "cancel",
    }


def _custom_manager(clock):
    routes = {
        "R_TEST": {
            "route_id": "R_TEST",
            "section_ids": ["S1"],
            "required_switches": [
                {"switch_id": "SW-TEST", "required_position": "reverse"}
            ],
            "start": 0.0,
            "end": 100.0,
            "speed_limit": 40.0,
        },
        "R_TEST_NORMAL": {
            "route_id": "R_TEST_NORMAL",
            "section_ids": ["S1"],
            "required_switches": [
                {"switch_id": "SW-TEST", "required_position": "normal"}
            ],
            "start": 0.0,
            "end": 100.0,
            "speed_limit": 40.0,
        },
    }
    sections = [
        {
            "section_id": "S1",
            "start": 0.0,
            "end": 100.0,
            "condition": "normal",
        }
    ]
    switches = [
        {
            "switch_id": "SW-TEST",
            "position": "normal",
            "default_position": "normal",
            "locked": False,
            "initial_locked": False,
            "locked_by_route_id": None,
            "initial_locked_by_route_id": None,
        }
    ]
    return RouteLifecycleManager(
        routes=routes,
        sections=sections,
        switches=switches,
        time_func=clock.time,
    )


def test_switch_runtime_states_initialized_from_config():
    manager = RouteLifecycleManager(time_func=FakeClock(100.0).time)

    switch_state = manager.switch_runtime_states["SW-01"]

    assert switch_state["state"] in {"locked_normal", "locked_reverse"}
    assert switch_state["locked"] is True
    assert switch_state["locked_by_route_id"] == "R_MAIN"
    assert switch_state["moving"] is False


def test_open_known_route_creates_locked_route_state():
    manager = RouteLifecycleManager(time_func=FakeClock(100.0).time)

    results = manager.handle_route_request(_open_request())

    route_state = manager.get_route_states()[0]
    assert results[0]["allowed"] is True
    assert results[0]["reason"] == "route_locked"
    assert route_state["state"] == "locked"
    assert route_state["route_id"] == "R_MAIN"
    assert manager.section_locks
    assert "SW-01" in manager.switch_locks


def test_open_route_locks_switch_as_locked_normal():
    manager = RouteLifecycleManager(time_func=FakeClock(100.0).time)

    manager.handle_route_request(_open_request(route_id="R_MAIN"))

    switch_state = manager.switch_runtime_states["SW-01"]
    assert switch_state["state"] == "locked_normal"
    assert switch_state["position"] == "normal"
    assert switch_state["locked"] is True


def test_open_route_requiring_reverse_changes_switch_to_locked_reverse():
    clock = FakeClock(100.0)
    manager = _custom_manager(clock)

    manager.handle_route_request(_open_request(route_id="R_TEST"))

    switch_state = manager.switch_runtime_states["SW-TEST"]
    assert switch_state["position"] == "reverse"
    assert switch_state["state"] == "locked_reverse"
    assert switch_state["locked"] is True


def test_open_unknown_route_rejected():
    manager = RouteLifecycleManager(time_func=FakeClock(100.0).time)

    results = manager.handle_route_request(_open_request(route_id="NO_SUCH_ROUTE"))

    route_state = manager.get_route_states()[0]
    assert results[0]["allowed"] is False
    assert route_state["state"] == "rejected"
    assert route_state["reason"] == "unknown_route"
    assert manager.build_route_results()[0]["allowed"] is False


def test_switch_fault_rejects_route():
    manager = RouteLifecycleManager(time_func=FakeClock(100.0).time)
    assert manager.set_switch_fault("SW-01") is True

    results = manager.handle_route_request(_open_request(route_id="R_MAIN"))

    route_state = manager.get_route_states()[0]
    assert results[0]["allowed"] is False
    assert route_state["state"] == "rejected"
    assert route_state["reason"] == "switch_fault"


def test_switch_four_open_rejects_route():
    manager = RouteLifecycleManager(time_func=FakeClock(100.0).time)
    assert manager.set_switch_four_open("SW-01") is True

    results = manager.handle_route_request(_open_request(route_id="R_MAIN"))

    route_state = manager.get_route_states()[0]
    assert results[0]["allowed"] is False
    assert route_state["state"] == "rejected"
    assert route_state["reason"] == "switch_four_open"


def test_clear_switch_fault_restores_normal_state():
    manager = RouteLifecycleManager(time_func=FakeClock(100.0).time)

    manager.set_switch_fault("SW-01")
    assert manager.clear_switch_fault("SW-01") is True

    switch_state = manager.switch_runtime_states["SW-01"]
    assert switch_state["fault"] is False
    assert switch_state["state"] in {"normal", "reverse"}


def test_second_route_conflicts_with_locked_switch():
    manager = RouteLifecycleManager(time_func=FakeClock(100.0).time)

    manager.handle_route_request(_open_request(route_id="R_MAIN"))
    results = manager.handle_route_request(
        _open_request(vehicle_id="TRAIN-003", route_id="R_BRANCH")
    )

    route_state = next(
        item for item in manager.get_route_states() if item["route_id"] == "R_BRANCH"
    )
    assert results[0]["allowed"] is False
    assert route_state["state"] == "rejected"
    assert route_state["reason"] == "switch_locked_conflict"
    assert route_state["conflict_switch_id"] == "SW-01"


def test_section_occupied_by_another_vehicle_rejected():
    manager = RouteLifecycleManager(time_func=FakeClock(100.0).time)

    results = manager.handle_route_request(
        _open_request(vehicle_id="TRAIN-001", route_id="R_MAIN"),
        train_states=[
            {
                "vehicle_id": "TRAIN-OTHER",
                "position": 300.0,
                "speed": 0.0,
                "route_id": "R_MAIN",
            }
        ],
    )

    route_state = manager.get_route_states()[0]
    assert results[0]["allowed"] is False
    assert route_state["reason"] == "occupied_section"
    assert route_state["conflict_section_id"] == "JZ1"
    assert route_state["occupied_by_vehicle_id"] == "TRAIN-OTHER"


def test_train_enters_locked_route_becomes_active():
    clock = FakeClock(100.0)
    manager = RouteLifecycleManager(time_func=clock.time)
    manager.handle_route_request(_open_request())

    clock.now = 101.0
    manager.update_by_train_states(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 300.0,
                "speed": 0.0,
                "route_id": "R_MAIN",
            }
        ]
    )

    route_state = manager.get_route_states()[0]
    assert route_state["state"] == "active"
    assert route_state["activated_at"] == 101.0


def test_train_leaves_route_released_and_locks_cleared():
    clock = FakeClock(100.0)
    manager = RouteLifecycleManager(time_func=clock.time)
    manager.handle_route_request(_open_request())
    manager.update_by_train_states(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 300.0,
                "speed": 0.0,
                "route_id": "R_MAIN",
            }
        ]
    )

    clock.now = 102.0
    manager.update_by_train_states(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 3000.0,
                "speed": 0.0,
                "route_id": "R_MAIN",
            }
        ]
    )

    route_state = manager.get_route_states()[0]
    assert route_state["state"] == "released"
    assert route_state["released_at"] == 102.0
    assert not [
        lock for lock in manager.section_locks.values() if lock["route_id"] == "R_MAIN"
    ]
    assert not [
        lock for lock in manager.switch_locks.values() if lock["route_id"] == "R_MAIN"
    ]


def test_releasing_route_unlocks_switch_runtime_state():
    clock = FakeClock(100.0)
    manager = _custom_manager(clock)
    manager.handle_route_request(_open_request(route_id="R_TEST_NORMAL"))
    manager.update_by_train_states(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 10.0,
                "speed": 0.0,
                "route_id": "R_TEST_NORMAL",
            }
        ]
    )

    clock.now = 102.0
    manager.update_by_train_states(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 200.0,
                "speed": 0.0,
                "route_id": "R_TEST_NORMAL",
            }
        ]
    )

    route_state = manager.get_route_states()[0]
    switch_state = manager.switch_runtime_states["SW-TEST"]
    assert route_state["state"] == "released"
    assert switch_state["locked"] is False
    assert switch_state["locked_by_route_id"] is None
    assert switch_state["state"] == "normal"


def test_cancel_locked_route_before_active():
    manager = RouteLifecycleManager(time_func=FakeClock(100.0).time)
    manager.handle_route_request(_open_request())

    results = manager.handle_route_request(_cancel_request())

    route_state = manager.get_route_states()[0]
    assert results[0]["allowed"] is True
    assert results[0]["reason"] == "route_cancelled"
    assert route_state["state"] == "cancelled"
    assert route_state["reason"] == "cancelled_before_active"
    assert not manager.section_locks
    assert not [lock for lock in manager.switch_locks.values() if lock["route_id"] == "R_MAIN"]


def test_cancel_active_route_rejected():
    manager = RouteLifecycleManager(time_func=FakeClock(100.0).time)
    manager.handle_route_request(_open_request())
    manager.update_by_train_states(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 300.0,
                "speed": 0.0,
                "route_id": "R_MAIN",
            }
        ]
    )

    results = manager.handle_route_request(_cancel_request())

    route_state = manager.get_route_states()[0]
    assert results[0]["allowed"] is False
    assert results[0]["reason"] == "route_active_cannot_cancel"
    assert route_state["state"] == "active"


def test_apply_locks_to_snapshot_adds_locked_fields():
    manager = RouteLifecycleManager(time_func=FakeClock(100.0).time)
    manager.handle_route_request(_open_request())
    snapshot = {
        "sections": [
            {
                "section_id": "JZ1",
                "occupied": False,
                "vehicle_id": None,
                "locked": False,
                "locked_by_route_id": None,
            }
        ],
        "switches": [
            {
                "switch_id": "SW-01",
                "position": "normal",
                "locked": False,
                "locked_by_route_id": None,
                "reason": "initial_state",
            }
        ],
        "route_results": [],
    }

    updated_snapshot = manager.apply_locks_to_snapshot(snapshot)

    assert snapshot["sections"][0]["locked"] is False
    assert updated_snapshot["sections"][0]["locked"] is True
    assert updated_snapshot["sections"][0]["locked_by_route_id"] == "R_MAIN"
    assert updated_snapshot["switches"][0]["locked"] is True
    assert updated_snapshot["switches"][0]["locked_by_route_id"] == "R_MAIN"
    assert updated_snapshot["route_states"][0]["state"] == "locked"


def test_apply_locks_to_snapshot_adds_switch_state_fields():
    manager = RouteLifecycleManager(time_func=FakeClock(100.0).time)
    manager.handle_route_request(_open_request())
    snapshot = {
        "sections": [],
        "switches": [
            {
                "switch_id": "SW-01",
                "position": "normal",
                "locked": False,
                "locked_by_route_id": None,
                "reason": "initial_state",
            }
        ],
        "route_results": [],
    }

    updated_snapshot = manager.apply_locks_to_snapshot(snapshot)
    switch = updated_snapshot["switches"][0]

    for field_name in (
        "state",
        "target_position",
        "moving",
        "fault",
        "four_open",
    ):
        assert field_name in switch
    assert switch["state"] == "locked_normal"
