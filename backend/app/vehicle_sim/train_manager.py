from .mock_data import DEFAULT_TRACK
from .track_map import TrackMap
from .train import Train


class TrainManager:
    def __init__(self):
        track = TrackMap(DEFAULT_TRACK)
        self.trains = {
            "TRAIN-001": Train("TRAIN-001", "LINE-1", track),
            "TRAIN-002": Train("TRAIN-002", "LINE-1", track),
            "TRAIN-003": Train("TRAIN-003", "LINE-1", track),
        }

        self.trains["TRAIN-001"].state.position = 0.0
        self.trains["TRAIN-002"].state.position = 300.0
        self.trains["TRAIN-003"].state.position = 700.0

    def get_train(self, vehicle_id: str):
        return self.trains.get(vehicle_id)

    def step_all(self, dt: float):
        outputs = []
        for train in self.trains.values():
            train.step_tick(dt)
            outputs.append(train.state.to_protocol())
        return outputs
