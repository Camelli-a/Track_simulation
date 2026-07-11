import time


class ScenarioRunner:
    def __init__(self, scenario, router, realtime: bool = True):
        self.scenario = scenario
        self.router = router
        self.realtime = realtime
        self.start_time = None
        self.sim_time = 0.0
        self.sent_indices = set()

    def start(self):
        self.start_time = time.time()
        self.sim_time = 0.0
        self.sent_indices.clear()

    def elapsed(self) -> float:
        if self.realtime:
            if self.start_time is None:
                return 0.0
            return time.time() - self.start_time
        return self.sim_time

    def advance(self, dt: float):
        if not self.realtime:
            self.sim_time += dt

    def tick(self):
        now = self.elapsed()
        for index, event in enumerate(self.scenario.events):
            if index in self.sent_indices:
                continue
            if now >= event.time_sec:
                msg = dict(event.message)
                msg.setdefault("timestamp", time.time())
                self.router.handle(msg)
                self.sent_indices.add(index)

    def is_finished(self) -> bool:
        return self.elapsed() >= self.scenario.duration_sec
