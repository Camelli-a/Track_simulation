import json
import time
from pathlib import Path


class RunRecorder:
    def __init__(self, output_dir: str = "logs/vehicle_runs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        filename = time.strftime("run_%Y%m%d_%H%M%S.jsonl")
        self.path = self.output_dir / filename

    def record_train_state(self, state: dict):
        self._record(state)

    def record_alarm(self, alarm: dict):
        self._record(alarm)

    def _record(self, message: dict):
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(message, ensure_ascii=False) + "\n")
