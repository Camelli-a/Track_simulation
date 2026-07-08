class FallbackAtoController:
    """Local fallback ATO for station-stop demos without external ATO."""

    def __init__(self, target_position: float, target_speed_kmh: float = 30.0):
        self.target_position = target_position
        self.target_speed_kmh = target_speed_kmh

    def compute(self, position: float, speed_kmh: float) -> tuple[int, int, str]:
        distance = self.target_position - position

        if distance <= 0:
            return 0, 4, "passed_stop_position"

        if distance > 5 and speed_kmh < 1.0:
            return 1, 0, "fallback_creep"

        speed_ms = speed_kmh / 3.6
        comfortable_deceleration = 0.8
        brake_distance = (speed_ms * speed_ms) / (2 * comfortable_deceleration)

        if distance > brake_distance + 30:
            if speed_kmh < self.target_speed_kmh:
                return 2, 0, "fallback_cruise_traction"
            return 0, 0, "fallback_cruise_coast"

        if distance > brake_distance + 10:
            return 0, 1, "fallback_light_brake"

        if distance > brake_distance:
            return 0, 2, "fallback_medium_brake"

        return 0, 3, "fallback_strong_brake"
