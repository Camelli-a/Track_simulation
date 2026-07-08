from dataclasses import dataclass
from typing import Any


@dataclass
class ScenarioEvent:
    time_sec: float
    message: dict[str, Any]


@dataclass
class Scenario:
    name: str
    description: str
    duration_sec: float
    events: list[ScenarioEvent]
