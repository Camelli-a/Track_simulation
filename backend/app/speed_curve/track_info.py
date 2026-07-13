"""Utility helpers to query static track data (gradient, speed limit).

Bridges the speed_curve module to the existing signal_track_config data.
"""
from __future__ import annotations

from typing import Optional

from app.services.signal_gradient import find_gradient_at_position
from app.services.signal_track_config import STATIC_SPEED_LIMITS


def get_gradient_at(position_m: float) -> float:
    """Return the gradient (‰) at *position_m*.  0.0 if not found."""
    info = find_gradient_at_position(position_m)
    if info is None:
        return 0.0
    try:
        return float(info["gradient"])
    except (KeyError, TypeError, ValueError):
        return 0.0


def get_speed_limit_at(position_m: float) -> Optional[float]:
    """Return the static speed limit (km/h) at *position_m*, or None.

    STATIC_SPEED_LIMITS entries have keys: start, end, speed_limit (km/h).
    """
    try:
        limits = STATIC_SPEED_LIMITS
    except Exception:
        return None

    best: Optional[float] = None
    best_len: float = float("inf")

    for row in limits:
        try:
            start = float(row["start"])
            end = float(row["end"])
            # field is named "speed_limit" and is already in km/h (converted from cm/s)
            limit = float(row["speed_limit"])
        except (KeyError, TypeError, ValueError):
            continue
        if start <= position_m < end:
            seg_len = end - start
            if seg_len < best_len:
                best_len = seg_len
                best = limit

    return best
