from copy import deepcopy
import threading
import time

from app.services.signal_track_config import ROUTES, SECTIONS, SWITCHES


TERMINAL_ROUTE_STATES = {"released", "rejected", "cancelled"}


class RouteLifecycleManager:
    def __init__(
        self,
        routes=None,
        sections=None,
        switches=None,
        time_func=time.time,
    ):
        self.routes = routes or ROUTES
        self.sections = sections or SECTIONS
        self.switches = switches or SWITCHES
        self.time_func = time_func
        self.route_states = {}
        self.section_locks = {}
        self.switch_locks = {}
        self.switch_runtime_states = {}
        self.last_route_results = []
        self.lock = threading.RLock()
        self._initialize_switch_runtime_states()
        self._initialize_switch_locks()

    def handle_route_request(self, request: dict, train_states: list[dict] | None = None) -> list[dict]:
        request_type = str(request.get("request_type", "open")).strip().lower()
        train_states = train_states or []

        with self.lock:
            if request_type == "open":
                result = self._handle_open_request(request, train_states)
                self.last_route_results = [result]
                return [result]
            if request_type == "cancel":
                results = self._handle_cancel_request(request)
                self.last_route_results = results
                return results
            if request_type == "clear":
                results = self._handle_clear_request()
                self.last_route_results = results
                return results

            result = {
                "vehicle_id": request.get("vehicle_id"),
                "route_id": request.get("route_id"),
                "allowed": False,
                "reason": "unsupported_request_type",
                "state": "rejected",
                "request_id": request.get("request_id"),
            }
            self.last_route_results = [result]
            return [result]

    def update_by_train_states(self, train_states: list[dict]) -> None:
        vehicle_current_section = {}
        for train_state in train_states:
            vehicle_id = train_state.get("vehicle_id")
            if not vehicle_id:
                continue
            vehicle_current_section[vehicle_id] = self._find_section_id_by_position(
                float(train_state.get("position", 0.0))
            )

        now = self.time_func()
        with self.lock:
            for route_state in list(self.route_states.values()):
                state = route_state.get("state")
                vehicle_id = route_state.get("vehicle_id")
                if vehicle_id not in vehicle_current_section:
                    continue

                current_section_id = vehicle_current_section[vehicle_id]
                section_ids = route_state.get("section_ids", [])
                if state == "locked" and current_section_id in section_ids:
                    route_state["state"] = "active"
                    route_state["activated_at"] = now
                elif state == "active" and current_section_id not in section_ids:
                    route_state["state"] = "released"
                    route_state["released_at"] = now
                    route_state["reason"] = "vehicle_left_route"
                    self._release_locks_for_route(route_state["route_id"])

    def apply_locks_to_snapshot(self, snapshot: dict) -> dict:
        updated_snapshot = deepcopy(snapshot)
        with self.lock:
            for section in updated_snapshot.get("sections", []):
                section_id = section.get("section_id")
                section_lock = self.section_locks.get(section_id)
                if section_lock:
                    section["locked"] = True
                    section["locked_by_route_id"] = section_lock["route_id"]
                    section["lock_reason"] = "route_lifecycle_locked"

            for switch in updated_snapshot.get("switches", []):
                switch_id = switch.get("switch_id")
                runtime_state = self._get_switch_runtime_state(switch_id)
                if runtime_state:
                    switch.update(
                        {
                            "position": runtime_state.get("position"),
                            "state": runtime_state.get("state"),
                            "target_position": runtime_state.get("target_position"),
                            "locked": runtime_state.get("locked", False),
                            "locked_by_route_id": runtime_state.get("locked_by_route_id"),
                            "moving": runtime_state.get("moving", False),
                            "fault": runtime_state.get("fault", False),
                            "four_open": runtime_state.get("four_open", False),
                            "moving_started_at": runtime_state.get("moving_started_at"),
                            "last_update_at": runtime_state.get("last_update_at"),
                            "reason": runtime_state.get("reason"),
                        }
                    )

            updated_snapshot["route_states"] = self.get_route_states()
            updated_snapshot["route_results"] = self._merge_route_results(
                updated_snapshot.get("route_results", []),
                self.build_route_results(),
            )

        return updated_snapshot

    def build_route_results(self) -> list[dict]:
        results = []
        with self.lock:
            for route_state in self.get_route_states():
                state = route_state.get("state")
                allowed = state != "rejected"
                result = {
                    "vehicle_id": route_state.get("vehicle_id"),
                    "route_id": route_state.get("route_id"),
                    "allowed": allowed,
                    "reason": route_state.get("reason") if state == "rejected" else state,
                    "state": state,
                    "request_id": route_state.get("request_id"),
                }
                for optional_key in (
                    "conflict_section_id",
                    "conflict_switch_id",
                    "occupied_by_vehicle_id",
                    "locked_by_route_id",
                ):
                    if route_state.get(optional_key) is not None:
                        result[optional_key] = route_state[optional_key]
                results.append(result)
        return results

    def remove_vehicle(self, vehicle_id: str | None) -> None:
        if not vehicle_id:
            return
        with self.lock:
            route_ids_to_release = []
            keys_to_remove = []
            for key, route_state in self.route_states.items():
                if route_state.get("vehicle_id") != vehicle_id:
                    continue
                route_id = route_state.get("route_id")
                if route_id:
                    route_ids_to_release.append(route_id)
                keys_to_remove.append(key)

            for route_id in route_ids_to_release:
                self._release_locks_for_route(route_id)
            for key in keys_to_remove:
                self.route_states.pop(key, None)

            self.last_route_results = [
                result
                for result in self.last_route_results
                if result.get("vehicle_id") != vehicle_id
            ]

    def clear_runtime_state(self) -> None:
        with self.lock:
            self.route_states.clear()
            self.section_locks.clear()
            self.switch_locks.clear()
            self.switch_runtime_states.clear()
            self.last_route_results = []
            self._initialize_switch_runtime_states()
            self._initialize_switch_locks()

    def get_route_states(self) -> list[dict]:
        with self.lock:
            return sorted(
                [deepcopy(route_state) for route_state in self.route_states.values()],
                key=lambda item: (
                    item.get("locked_at") is None,
                    item.get("locked_at") or 0.0,
                    item.get("request_id") or "",
                ),
            )

    def _handle_open_request(self, request: dict, train_states: list[dict]) -> dict:
        now = self.time_func()
        vehicle_id = request.get("vehicle_id")
        route_id = request.get("route_id")
        request_id = request.get("request_id") or f"REQ-{vehicle_id}-{route_id}"
        route = self._route_by_id(route_id)

        if route is None:
            route_state = self._build_route_state(
                request_id=request_id,
                vehicle_id=vehicle_id,
                route_id=route_id,
                state="rejected",
                reason="unknown_route",
                now=now,
            )
            self.route_states[self._route_state_key(vehicle_id, route_id)] = route_state
            return self._route_result(route_state, allowed=False, reason="unknown_route")

        switch_conflict = self._find_switch_request_failure(route, route_id)
        if switch_conflict:
            reason = switch_conflict.get("reason", "switch_locked_conflict")
            route_state = self._build_rejected_route_state(
                request,
                route,
                reason,
                now,
                conflict_switch_id=switch_conflict.get("switch_id"),
                locked_by_route_id=switch_conflict.get("locked_by_route_id"),
            )
            self.route_states[self._route_state_key(vehicle_id, route_id)] = route_state
            return self._route_result(route_state, allowed=False, reason=reason)

        occupied_conflict = self._find_occupied_section_conflict(route, vehicle_id, train_states)
        if occupied_conflict:
            route_state = self._build_rejected_route_state(
                request,
                route,
                "occupied_section",
                now,
                conflict_section_id=occupied_conflict["section_id"],
                occupied_by_vehicle_id=occupied_conflict["vehicle_id"],
            )
            self.route_states[self._route_state_key(vehicle_id, route_id)] = route_state
            return self._route_result(route_state, allowed=False, reason="occupied_section")

        section_lock_conflict = self._find_section_lock_conflict(route, route_id)
        if section_lock_conflict:
            route_state = self._build_rejected_route_state(
                request,
                route,
                "section_locked_conflict",
                now,
                conflict_section_id=section_lock_conflict,
            )
            self.route_states[self._route_state_key(vehicle_id, route_id)] = route_state
            return self._route_result(route_state, allowed=False, reason="section_locked_conflict")

        for required_switch in route.get("required_switches", []):
            switch_result = self._request_switch_for_route(
                route_id=route_id,
                vehicle_id=vehicle_id,
                switch_id=required_switch.get("switch_id"),
                required_position=required_switch.get("required_position"),
            )
            if not switch_result.get("ok"):
                reason = switch_result.get("reason", "switch_locked_conflict")
                route_state = self._build_rejected_route_state(
                    request,
                    route,
                    reason,
                    now,
                    conflict_switch_id=switch_result.get("switch_id"),
                    locked_by_route_id=switch_result.get("locked_by_route_id"),
                )
                self.route_states[self._route_state_key(vehicle_id, route_id)] = route_state
                return self._route_result(route_state, allowed=False, reason=reason)

        route_state = self._build_route_state(
            request_id=request_id,
            vehicle_id=vehicle_id,
            route_id=route_id,
            state="locked",
            route=route,
            now=now,
        )
        self.route_states[self._route_state_key(vehicle_id, route_id)] = route_state

        for section_id in route.get("section_ids", []):
            self.section_locks[section_id] = {
                "route_id": route_id,
                "vehicle_id": vehicle_id,
                "locked_at": now,
            }

        return self._route_result(route_state, allowed=True, reason="route_locked")

    def _handle_cancel_request(self, request: dict) -> list[dict]:
        vehicle_id = request.get("vehicle_id")
        route_id = request.get("route_id")
        now = self.time_func()

        if route_id:
            keys = [self._route_state_key(vehicle_id, route_id)]
        else:
            keys = [
                key
                for key, route_state in self.route_states.items()
                if route_state.get("vehicle_id") == vehicle_id
            ]

        if not keys or all(key not in self.route_states for key in keys):
            return [
                {
                    "vehicle_id": vehicle_id,
                    "route_id": route_id,
                    "allowed": False,
                    "reason": "route_not_found",
                    "state": None,
                    "request_id": request.get("request_id"),
                }
            ]

        results = []
        for key in keys:
            route_state = self.route_states.get(key)
            if not route_state:
                continue

            state = route_state.get("state")
            if state == "locked":
                route_state["state"] = "cancelled"
                route_state["cancelled_at"] = now
                route_state["reason"] = "cancelled_before_active"
                self._release_locks_for_route(route_state["route_id"])
                results.append(self._route_result(route_state, allowed=True, reason="route_cancelled"))
            elif state == "active":
                results.append(
                    self._route_result(
                        route_state,
                        allowed=False,
                        reason="route_active_cannot_cancel",
                    )
                )
            elif state in TERMINAL_ROUTE_STATES:
                results.append(
                    self._route_result(
                        route_state,
                        allowed=True,
                        reason="route_already_terminal",
                    )
                )
            else:
                results.append(
                    self._route_result(
                        route_state,
                        allowed=False,
                        reason="route_not_found",
                    )
                )

        return results

    def _handle_clear_request(self) -> list[dict]:
        return [
            {
                "vehicle_id": None,
                "route_id": None,
                "allowed": True,
                "reason": "route_requests_cleared",
                "state": None,
                "request_id": None,
            }
        ]

    def _initialize_switch_locks(self) -> None:
        now = self.time_func()
        for switch in self.switches:
            locked_by_route_id = switch.get("initial_locked_by_route_id") or switch.get("locked_by_route_id")
            if (switch.get("initial_locked") or switch.get("locked")) and locked_by_route_id:
                self.switch_locks[switch["switch_id"]] = {
                    "route_id": locked_by_route_id,
                    "vehicle_id": None,
                    "position": switch.get("position") or switch.get("default_position") or "normal",
                    "locked_at": now,
                    "source": "initial_config",
                }

    def _initialize_switch_runtime_states(self) -> None:
        now = self.time_func()
        for switch in self.switches:
            switch_id = switch.get("switch_id")
            position = switch.get("position") or switch.get("default_position") or "normal"
            position = self._normalize_switch_position(position)
            locked_by_route_id = switch.get("initial_locked_by_route_id") or switch.get("locked_by_route_id")
            locked = bool((switch.get("initial_locked") or switch.get("locked")) and locked_by_route_id)

            fault = position == "fault"
            four_open = position == "four_open"
            if fault or four_open:
                locked = False
                locked_by_route_id = None

            self.switch_runtime_states[switch_id] = {
                "switch_id": switch_id,
                "position": position,
                "state": self._state_for_position(position, locked=locked),
                "target_position": position,
                "locked": locked,
                "locked_by_route_id": locked_by_route_id if locked else None,
                "moving": False,
                "moving_started_at": None,
                "last_update_at": now,
                "fault": fault,
                "four_open": four_open,
                "reason": "initial_config" if locked else "initial_state",
            }

    def _route_by_id(self, route_id: str) -> dict | None:
        return self.routes.get(route_id)

    def _section_by_id(self, section_id: str) -> dict | None:
        for section in self.sections:
            if section.get("section_id") == section_id:
                return section
        return None

    def _switch_by_id(self, switch_id: str) -> dict | None:
        for switch in self.switches:
            if switch.get("switch_id") == switch_id:
                return switch
        return None

    def _state_for_position(self, position: str, locked: bool = False) -> str:
        position = self._normalize_switch_position(position)
        if position == "fault":
            return "fault"
        if position == "four_open":
            return "four_open"
        if position == "normal":
            return "locked_normal" if locked else "normal"
        if position == "reverse":
            return "locked_reverse" if locked else "reverse"
        return "unknown"

    def _normalize_switch_position(self, position) -> str:
        normalized = str(position or "unknown").strip().lower()
        if normalized in {"normal", "reverse", "fault", "four_open"}:
            return normalized
        return "unknown"

    def _get_switch_runtime_state(self, switch_id: str) -> dict | None:
        if not switch_id:
            return None
        runtime_state = self.switch_runtime_states.get(switch_id)
        if runtime_state:
            return runtime_state

        switch = self._switch_by_id(switch_id)
        if not switch:
            return None

        now = self.time_func()
        position = self._normalize_switch_position(
            switch.get("position") or switch.get("default_position") or "normal"
        )
        runtime_state = {
            "switch_id": switch_id,
            "position": position,
            "state": self._state_for_position(position, locked=False),
            "target_position": position,
            "locked": False,
            "locked_by_route_id": None,
            "moving": False,
            "moving_started_at": None,
            "last_update_at": now,
            "fault": position == "fault",
            "four_open": position == "four_open",
            "reason": "initial_state",
        }
        self.switch_runtime_states[switch_id] = runtime_state
        return runtime_state

    def _route_state_key(self, vehicle_id, route_id) -> str:
        return f"{vehicle_id}:{route_id}"

    def _find_section_id_by_position(self, position: float) -> str | None:
        for section in self.sections:
            if section["start"] <= position < section["end"]:
                return section["section_id"]
        return None

    def _build_route_state(
        self,
        request_id,
        vehicle_id,
        route_id,
        state,
        route=None,
        reason=None,
        now=None,
        **extra_fields,
    ) -> dict:
        now = self.time_func() if now is None else now
        route = route or {}
        return {
            "request_id": request_id,
            "route_id": route_id,
            "vehicle_id": vehicle_id,
            "state": state,
            "section_ids": list(route.get("section_ids", [])),
            "required_switches": list(route.get("required_switches", [])),
            "locked_at": now if state == "locked" else None,
            "activated_at": None,
            "released_at": None,
            "reason": reason,
            **extra_fields,
        }

    def _build_rejected_route_state(self, request, route, reason, now, **extra_fields) -> dict:
        return self._build_route_state(
            request_id=request.get("request_id") or f"REQ-{request.get('vehicle_id')}-{request.get('route_id')}",
            vehicle_id=request.get("vehicle_id"),
            route_id=request.get("route_id"),
            state="rejected",
            route=route,
            reason=reason,
            now=now,
            **extra_fields,
        )

    def _release_locks_for_route(self, route_id: str) -> None:
        now = self.time_func()
        self.section_locks = {
            section_id: section_lock
            for section_id, section_lock in self.section_locks.items()
            if section_lock.get("route_id") != route_id
        }
        self.switch_locks = {
            switch_id: switch_lock
            for switch_id, switch_lock in self.switch_locks.items()
            if switch_lock.get("route_id") != route_id
        }
        for runtime_state in self.switch_runtime_states.values():
            if runtime_state.get("locked_by_route_id") != route_id:
                continue
            position = self._normalize_switch_position(runtime_state.get("position"))
            runtime_state.update(
                {
                    "locked": False,
                    "locked_by_route_id": None,
                    "target_position": position,
                    "state": self._state_for_position(position, locked=False),
                    "moving": False,
                    "reason": "route_released",
                    "last_update_at": now,
                }
            )

    def _find_switch_request_failure(self, route: dict, route_id: str) -> dict | None:
        for required_switch in route.get("required_switches", []):
            switch_id = required_switch.get("switch_id")
            required_position = required_switch.get("required_position")
            runtime_state = self._get_switch_runtime_state(switch_id)
            if not runtime_state:
                return {"switch_id": switch_id, "reason": "unknown_switch"}
            if runtime_state.get("fault") or runtime_state.get("state") == "fault":
                return {"switch_id": switch_id, "reason": "switch_fault"}
            if runtime_state.get("four_open") or runtime_state.get("state") == "four_open":
                return {"switch_id": switch_id, "reason": "switch_four_open"}
            if runtime_state.get("state") == "unknown":
                return {"switch_id": switch_id, "reason": "switch_unknown"}
            if runtime_state.get("moving") or str(runtime_state.get("state", "")).startswith("moving_to_"):
                return {"switch_id": switch_id, "reason": "switch_moving"}

            locked_by_route_id = runtime_state.get("locked_by_route_id")
            if not runtime_state.get("locked"):
                continue
            if locked_by_route_id == route_id and runtime_state.get("position") == required_position:
                continue
            return {
                "switch_id": switch_id,
                "reason": "switch_locked_conflict",
                "locked_by_route_id": locked_by_route_id,
            }

        return None

    def _request_switch_for_route(
        self,
        route_id: str,
        vehicle_id: str,
        switch_id: str,
        required_position: str,
    ) -> dict:
        runtime_state = self._get_switch_runtime_state(switch_id)
        if not runtime_state:
            return {"ok": False, "switch_id": switch_id, "reason": "unknown_switch"}

        required_position = self._normalize_switch_position(required_position)
        if required_position not in {"normal", "reverse"}:
            return {"ok": False, "switch_id": switch_id, "reason": "switch_unknown"}

        if runtime_state.get("fault") or runtime_state.get("state") == "fault":
            return {"ok": False, "switch_id": switch_id, "reason": "switch_fault"}
        if runtime_state.get("four_open") or runtime_state.get("state") == "four_open":
            return {"ok": False, "switch_id": switch_id, "reason": "switch_four_open"}
        if runtime_state.get("state") == "unknown":
            return {"ok": False, "switch_id": switch_id, "reason": "switch_unknown"}
        if runtime_state.get("moving") or str(runtime_state.get("state", "")).startswith("moving_to_"):
            return {"ok": False, "switch_id": switch_id, "reason": "switch_moving"}

        locked_by_route_id = runtime_state.get("locked_by_route_id")
        if runtime_state.get("locked") and locked_by_route_id != route_id:
            return {
                "ok": False,
                "switch_id": switch_id,
                "reason": "switch_locked_conflict",
                "locked_by_route_id": locked_by_route_id,
            }
        if runtime_state.get("locked") and runtime_state.get("position") != required_position:
            return {
                "ok": False,
                "switch_id": switch_id,
                "reason": "switch_locked_conflict",
                "locked_by_route_id": locked_by_route_id,
            }

        now = self.time_func()
        runtime_state.update(
            {
                "position": required_position,
                "state": self._state_for_position(required_position, locked=True),
                "target_position": required_position,
                "locked": True,
                "locked_by_route_id": route_id,
                "moving": False,
                "moving_started_at": None,
                "fault": False,
                "four_open": False,
                "reason": "route_lifecycle_locked",
                "last_update_at": now,
            }
        )
        self.switch_locks[switch_id] = {
            "route_id": route_id,
            "vehicle_id": vehicle_id,
            "position": required_position,
            "locked_at": now,
        }
        return {
            "ok": True,
            "switch_id": switch_id,
            "position": required_position,
            "state": runtime_state["state"],
        }

    def _find_section_lock_conflict(self, route: dict, route_id: str) -> str | None:
        for section_id in route.get("section_ids", []):
            section_lock = self.section_locks.get(section_id)
            if section_lock and section_lock.get("route_id") != route_id:
                return section_id
        return None

    def _find_occupied_section_conflict(
        self,
        route: dict,
        vehicle_id: str,
        train_states: list[dict],
    ) -> dict | None:
        route_section_ids = set(route.get("section_ids", []))
        for train_state in train_states:
            other_vehicle_id = train_state.get("vehicle_id")
            if other_vehicle_id == vehicle_id:
                continue
            section_id = self._find_section_id_by_position(float(train_state.get("position", 0.0)))
            if section_id in route_section_ids:
                return {
                    "section_id": section_id,
                    "vehicle_id": other_vehicle_id,
                }
        return None

    def _route_result(self, route_state: dict, allowed: bool, reason: str) -> dict:
        result = {
            "vehicle_id": route_state.get("vehicle_id"),
            "route_id": route_state.get("route_id"),
            "allowed": allowed,
            "reason": reason,
            "state": route_state.get("state"),
            "request_id": route_state.get("request_id"),
        }
        for optional_key in (
            "conflict_section_id",
            "conflict_switch_id",
            "occupied_by_vehicle_id",
            "locked_by_route_id",
        ):
            if route_state.get(optional_key) is not None:
                result[optional_key] = route_state[optional_key]
        return result

    def set_switch_fault(self, switch_id: str, reason: str | None = None) -> bool:
        with self.lock:
            runtime_state = self._get_switch_runtime_state(switch_id)
            if not runtime_state:
                return False
            runtime_state.update(
                {
                    "state": "fault",
                    "fault": True,
                    "four_open": False,
                    "locked": False,
                    "locked_by_route_id": None,
                    "moving": False,
                    "reason": reason or "switch_fault",
                    "last_update_at": self.time_func(),
                }
            )
            self.switch_locks.pop(switch_id, None)
            return True

    def clear_switch_fault(self, switch_id: str) -> bool:
        with self.lock:
            runtime_state = self._get_switch_runtime_state(switch_id)
            if not runtime_state:
                return False
            runtime_state["fault"] = False
            if not runtime_state.get("four_open"):
                position = self._normal_or_reverse_position(runtime_state, switch_id)
                runtime_state.update(
                    {
                        "position": position,
                        "state": self._state_for_position(position, locked=False),
                        "target_position": position,
                        "locked": False,
                        "locked_by_route_id": None,
                        "moving": False,
                        "reason": "switch_fault_cleared",
                        "last_update_at": self.time_func(),
                    }
                )
            return True

    def set_switch_four_open(self, switch_id: str, reason: str | None = None) -> bool:
        with self.lock:
            runtime_state = self._get_switch_runtime_state(switch_id)
            if not runtime_state:
                return False
            runtime_state.update(
                {
                    "state": "four_open",
                    "four_open": True,
                    "fault": False,
                    "locked": False,
                    "locked_by_route_id": None,
                    "moving": False,
                    "reason": reason or "switch_four_open",
                    "last_update_at": self.time_func(),
                }
            )
            self.switch_locks.pop(switch_id, None)
            return True

    def clear_switch_four_open(self, switch_id: str) -> bool:
        with self.lock:
            runtime_state = self._get_switch_runtime_state(switch_id)
            if not runtime_state:
                return False
            runtime_state["four_open"] = False
            if not runtime_state.get("fault"):
                position = self._normal_or_reverse_position(runtime_state, switch_id)
                runtime_state.update(
                    {
                        "position": position,
                        "state": self._state_for_position(position, locked=False),
                        "target_position": position,
                        "locked": False,
                        "locked_by_route_id": None,
                        "moving": False,
                        "reason": "switch_four_open_cleared",
                        "last_update_at": self.time_func(),
                    }
                )
            return True

    def _normal_or_reverse_position(self, runtime_state: dict, switch_id: str) -> str:
        position = self._normalize_switch_position(runtime_state.get("position"))
        if position in {"normal", "reverse"}:
            return position
        switch = self._switch_by_id(switch_id) or {}
        position = self._normalize_switch_position(switch.get("default_position") or switch.get("position"))
        if position in {"normal", "reverse"}:
            return position
        return "normal"

    def _merge_route_results(self, existing_results: list[dict], lifecycle_results: list[dict]) -> list[dict]:
        merged = []
        seen = set()
        for result in [*existing_results, *lifecycle_results]:
            key = (
                result.get("vehicle_id"),
                result.get("route_id"),
                result.get("allowed"),
                result.get("reason"),
                result.get("state"),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(result)
        return merged
