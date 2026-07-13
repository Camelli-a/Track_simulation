import json
import time

from .line_data_loader import build_track_map_from_line_layout
from .models import AtoCommand
from .models import MaLimit
from .train import Train


def main():
    track = build_track_map_from_line_layout()
    train = Train("TRAIN-001", "LINE-1", track)

    dt = 0.1
    train.apply_ma_state(
        MaLimit(
            vehicle_id="TRAIN-001",
            ma_limit=1800.0,
            target_speed=60.0,
            reason="local_demo",
            allowed_speed_kmh=60.0,
            target_distance_m=1800.0,
            permission="allow",
            signal_state="green",
            updated_at=time.time(),
        )
    )

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
        train.ma_updated_at = time.time()
        train.step_tick(dt)
        print(json.dumps(train.state.to_protocol(), ensure_ascii=False))

        time.sleep(dt)


if __name__ == "__main__":
    main()
