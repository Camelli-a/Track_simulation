from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1"


class VehicleDemoClient:
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} failed: HTTP {exc.code} {raw}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Cannot connect to backend at {self.base_url}. Start FastAPI first."
            ) from exc


def log_step(title: str) -> None:
    print(f"\n=== {title} ===", flush=True)


def print_json(data: dict[str, Any] | list[Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2), flush=True)


def summarize_trains(data: dict[str, Any]) -> None:
    trains = data.get("trains", [])
    print(f"active train count: {data.get('count', len(trains))}", flush=True)
    for train in trains[:5]:
        print(
            "  {vehicle_id} | slot={train_index} | pos={position:.1f}m | "
            "speed={speed:.2f}km/h | mode={mode} | EB={emergency_brake}".format(
                **train
            ),
            flush=True,
        )
    if len(trains) > 5:
        print(f"  ... {len(trains) - 5} more", flush=True)


def run_demo(client: VehicleDemoClient, pause: float) -> None:
    log_step("1. Reset vehicle manager to 3 demo trains")
    reset = client.post("/vehicle/manage", {"type": "reset_trains", "count": 3})
    print_json(
        {
            "ok": reset["ok"],
            "published": reset["published"],
            "result": reset["result"],
            "train_count": len(reset["trains"]),
        }
    )

    log_step("2. List managed trains")
    summarize_trains(client.get("/vehicle/trains"))

    log_step("3. Add one extra train")
    added = client.post(
        "/vehicle/manage",
        {
            "type": "add_train",
            "vehicle_id": "TRAIN-099",
            "train_index": 99,
            "line_id": "LINE-1",
            "position": 1500.0,
        },
    )
    print_json(
        {
            "ok": added["ok"],
            "published": added["published"],
            "result": added["result"],
            "train_count": len(added["trains"]),
        }
    )
    time.sleep(pause)

    control_cases = [
        (
            "4. Manual traction command",
            {
                "vehicle_id": "TRAIN-001",
                "command": "traction",
                "level": 3,
                "direction": "forward",
            },
        ),
        (
            "5. Manual brake command",
            {
                "vehicle_id": "TRAIN-001",
                "command": "brake",
                "level": 2,
                "direction": "forward",
            },
        ),
        (
            "6. ATO target-speed command",
            {
                "vehicle_id": "TRAIN-002",
                "command": "ato",
                "target_speed": 45.0,
                "target_position": 900.0,
                "reason": "midterm_demo",
            },
        ),
        (
            "7. Emergency brake command",
            {
                "vehicle_id": "TRAIN-003",
                "command": "emergency_brake",
                "level": 4,
            },
        ),
    ]

    for title, payload in control_cases:
        log_step(title)
        response = client.post("/vehicle/control", payload)
        print_json(response)
        time.sleep(pause)

    log_step("8. Read mock vehicle status")
    print_json(client.get("/vehicle/status"))

    log_step("9. Read short vehicle history")
    history = client.get("/vehicle/history?limit=3")
    print_json({"returned": len(history), "items": history})

    log_step("10. Final managed train list")
    summarize_trains(client.get("/vehicle/trains"))

    print(
        "\nDemo finished. Check the FastAPI backend terminal for Vehicle control/management logs.",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vehicle module HTTP demo test")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--pause", type=float, default=0.4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = VehicleDemoClient(args.base_url)
    try:
        run_demo(client, args.pause)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
