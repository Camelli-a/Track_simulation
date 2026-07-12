import json
import time

from .mock_data import DEFAULT_TRACK
from .models import DriverInput
from .track_map import TrackMap
from .train import Train


def main():
    track = TrackMap(DEFAULT_TRACK)
    train = Train("TRAIN-001", "LINE-1", track)

    dt = 0.1

    for i in range(100):
        driver_input = DriverInput(
            vehicle_id="TRAIN-001",
            line_id="LINE-1",
            source="mock",
            control_mode="manual",
            traction_level=3 if i < 50 else 0,
            brake_level=0 if i < 50 else 2,
            direction="forward",
            emergency_button=False,
        )

        train.step_manual(driver_input, dt)
        train.step_tick(dt)
        print(json.dumps(train.state.to_protocol(), ensure_ascii=False))

        time.sleep(dt)


if __name__ == "__main__":
    main()
