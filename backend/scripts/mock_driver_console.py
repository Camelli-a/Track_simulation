"""External mock driver console entrypoint.

Run from ``backend`` as:
    python scripts\\mock_driver_console.py --vehicle-id TRAIN-001 --mode ato --publish-ma
"""

from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.vehicle_sim.mock_driver_console import main  # noqa: E402


if __name__ == "__main__":
    main()
