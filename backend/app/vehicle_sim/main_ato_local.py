import json
import time

from .mock_data import DEFAULT_TRACK
from .models import AtoCommand
from .track_map import TrackMap
from .train import Train


def main():
    track = TrackMap(DEFAULT_TRACK)
    train = Train("TRAIN-001", "LINE-1", track)

    dt = 0.1

    for i in range(100):
        ato_command = AtoCommand(
            vehicle_id="TRAIN-001",
            line_id="LINE-1",
            control_mode="ato",
            target_speed=30.0 if i < 50 else 0.0,
            target_position=1500.0,
            traction_level=3 if i < 50 else 0,
            brake_level=0 if i < 50 else 2,
            reason="local_ato_demo",
        )

        train.step_ato(ato_command, dt)
        print(json.dumps(train.state.to_protocol(), ensure_ascii=False))

        time.sleep(dt)


if __name__ == "__main__":
    main()
