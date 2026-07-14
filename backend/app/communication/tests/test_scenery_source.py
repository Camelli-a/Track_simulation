from app.communication.scenery_source import ScenerySource


def test_scenery_source_initializes_with_first_visual_edge():
    source = ScenerySource()

    state = source.get_state()

    assert state["edge_id"] == 3
    assert state["section_dist"] == 0


def test_scenery_source_position_zero_uses_first_visual_edge():
    source = ScenerySource()

    updated = source.update_own_train_from_state(
        {
            "vehicle_id": "TRAIN-001",
            "line_id": "LINE-1",
            "position_m": 0.0,
            "speed_mps": 0.0,
            "direction": 1,
        }
    )

    state = source.get_state()
    assert updated is True
    assert state["edge_id"] == 3
    assert state["section_dist"] == 0
