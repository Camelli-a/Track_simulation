"""Small deterministic train-door state machine for the vehicle simulator."""

from dataclasses import dataclass


DOOR_CLOSED = "closed"
DOOR_OPEN = "open"


@dataclass
class DoorState:
    """Physical door state, independent from driver-desk indicator feedback."""

    left_open: bool = False
    right_open: bool = False
    mode: str = "auto"
    dwell_remaining_s: float = 0.0
    last_auto_target_m: float | None = None

    @property
    def all_closed(self) -> bool:
        return not self.left_open and not self.right_open

    @property
    def state(self) -> str:
        return DOOR_CLOSED if self.all_closed else DOOR_OPEN

    def open(self, *, left: bool, right: bool, dwell_s: float) -> None:
        self.left_open = bool(left)
        self.right_open = bool(right)
        self.dwell_remaining_s = max(0.0, float(dwell_s))

    def close(self) -> None:
        self.left_open = False
        self.right_open = False
        self.dwell_remaining_s = 0.0

    def tick(self, dt: float) -> bool:
        """Advance dwell time and close when it expires; return whether closed."""
        if self.all_closed:
            return False
        self.dwell_remaining_s = max(0.0, self.dwell_remaining_s - max(0.0, dt))
        if self.dwell_remaining_s == 0.0:
            self.close()
            return True
        return False


def normalize_door_mode(mode: str | None) -> str:
    normalized = "auto" if mode is None else str(mode).strip().lower()
    aliases = {
        "l": "left",
        "left": "left",
        "左": "left",
        "r": "right",
        "right": "right",
        "右": "right",
        "both": "both",
        "双侧": "both",
        "auto": "auto",
        "automatic": "auto",
    }
    return aliases.get(normalized, "auto")


def sides_for_mode(mode: str) -> tuple[bool, bool]:
    """Return opening sides; auto defaults to left until platform-side data exists."""
    normalized = normalize_door_mode(mode)
    if normalized == "right":
        return False, True
    if normalized == "both":
        return True, True
    return True, False
