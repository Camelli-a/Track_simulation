from typing import List, Optional

from .models import TrackSection


class TrackMap:
    """Query track section data by train position."""

    def __init__(self, sections: List[TrackSection]):
        if not sections:
            raise ValueError("Track sections cannot be empty")
        self.sections = sections

    def get_section(self, position: float) -> TrackSection:
        for section in self.sections:
            if section.start <= position < section.end:
                return section

        # Clamp beyond the known map to the last section for local simulation.
        return self.sections[-1]

    def get_gradient(self, position: float) -> float:
        return self.get_section(position).gradient

    def get_speed_limit(self, position: float) -> float:
        return self.get_section(position).speed_limit

    def get_stop_position(self, position: float) -> Optional[float]:
        return self.get_section(position).stop_position
