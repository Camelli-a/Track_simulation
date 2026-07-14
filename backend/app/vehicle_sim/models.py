from dataclasses import dataclass
import logging
from typing import Literal, Optional
import time

from .vehicle_parameters import TRAIN_LENGTH_M


Mode = Literal["manual", "ato", "atp", "emergency"]
logger = logging.getLogger(__name__)


@dataclass
class TrainState:
    """Internal train state.

    Protocol units:
    - position: m
    - speed: km/h, derived from internal speed_ms
    - acceleration: m/s^2
    """

    vehicle_id: str
    line_id: str
    position: float
    speed_ms: float
    acceleration: float
    mode: Mode
    is_running: bool
    emergency_brake: bool
    route_id: str = "R_MAIN"
    train_index: int = 0
    edge_id: Optional[int] = None
    section_id: Optional[str] = None
    station_id: Optional[str] = None
    station_name: Optional[str] = None
    station_yard_section_id: Optional[str] = None
    station_yard_track_id: Optional[str] = None
    station_yard_route_section_ids: Optional[list[str]] = None
    edge_offset_m: Optional[float] = None
    direction_code: int = 1
    door_state: str = "closed"
    left_door_open: bool = False
    right_door_open: bool = False
    doors_all_closed: bool = True
    door_mode: str = "auto"
    door_closed_light: bool = True
    high_voltage_light: bool = True
    brake_bad_light: bool = False
    traction_level: int = 0
    brake_level: int = 0
    traction_percent: float = 0.0
    brake_percent: float = 0.0
    actual_traction_force_n: float = 0.0
    actual_brake_force_n: float = 0.0
    atp_intervention: bool = False
    driving_mode: str = "SM"
    control_source: str = "none"
    ato_active: bool = False
    ato_capable: bool = False
    ato_start_requested: bool = False
    ato_start_accepted: bool = False
    ato_start_reject_reason: Optional[str] = None
    auto_reverse_cap: bool = False
    auto_reverse_active: bool = False
    recommended_speed_kmh: Optional[float] = None
    recommended_speed: float = 0.0
    ato_state: Optional[str] = None
    ato_target_speed_kmh: float = 0.0
    ato_traction_level: int = 0
    ato_brake_level: int = 0
    commanded_traction_level: int = 0
    commanded_brake_level: int = 0
    applied_traction_level: int = 0
    applied_brake_level: int = 0
    atp_intervened: bool = False
    stop_target: Optional[float] = None
    distance_to_stop: Optional[float] = None
    stop_result: Optional[dict] = None
    parking_brake: bool = False
    external_speed_limit_kmh: Optional[float] = None
    active_faults: tuple[str, ...] = ()
    atp_supervision_state: str = "unknown"
    atp_reason: str = "not_evaluated"
    atp_allowed_speed_kmh: Optional[float] = None
    atp_speed_limit_source: Optional[str] = None
    atp_track_speed_limit_kmh: Optional[float] = None
    atp_ma_allowed_speed_kmh: Optional[float] = None
    atp_external_speed_limit_kmh: Optional[float] = None
    atp_eb_trigger_speed_kmh: Optional[float] = None
    atp_distance_to_authority_m: Optional[float] = None
    atp_service_stop_distance_m: Optional[float] = None
    atp_emergency_stop_distance_m: Optional[float] = None
    atp_debug: Optional[dict] = None
    ato_brake_bias: float = 1.0
    ato_brake_bias_enabled: bool = False
    ato_brake_bias_adaptation_enabled: bool = False
    last_brake_bias_adjustment: Optional[dict] = None
    brake_bias_history_size: int = 0
    curve_output_enabled: bool = True
    curve_history_size: int = 300
    curve_point: Optional[dict] = None

    @property
    def speed_kmh(self) -> float:
        return self.speed_ms * 3.6

    @property
    def protocol_direction(self) -> int:
        if self.direction_code in (-1, 2, 0xAA):
            return -1
        return 1

    @property
    def front_position_m(self) -> float:
        """Absolute mileage of the train front reference point in metres.

        ``position``/``position_m`` is the canonical visualisation and signalling
        reference point.  It represents the leading/front cab position on the
        one-dimensional line model.
        """
        return self.position

    @property
    def rear_position_m(self) -> float:
        """Absolute mileage of the rear end in metres.

        Direction is normalised to the visualisation contract: ``1`` means
        increasing mileage, ``-1`` means decreasing mileage.
        """
        return self.front_position_m - self.protocol_direction * TRAIN_LENGTH_M

    def to_protocol(self) -> dict:
        """Convert internal state to the train_state protocol message."""
        protocol = {
            "type": "train_state",
            "timestamp": time.time(),
            "vehicle_id": self.vehicle_id,
            "train_index": self.train_index,
            "line_id": self.line_id,
            "route_id": self.route_id,
            "train_length": TRAIN_LENGTH_M,
            "position": round(self.position, 3),
            "speed": round(self.speed_kmh, 3),
            "speed_ms": round(self.speed_ms, 3),
            "acceleration": round(self.acceleration, 3),
            "position_m": round(self.position, 3),
            "position_reference": "front_cab",
            "front_position_m": round(self.front_position_m, 3),
            "rear_position_m": round(self.rear_position_m, 3),
            "speed_mps": round(self.speed_ms, 3),
            "speed_kmh": round(self.speed_kmh, 3),
            "vehicle_speed_kmh": round(self.speed_kmh, 3),
            "acceleration_mps2": round(self.acceleration, 3),
            "mode": self.mode,
            "control_mode": self.mode,
            "is_running": self.is_running,
            "emergency_brake": self.emergency_brake,
            "edge_id": self.edge_id,
            "section_id": self.section_id,
            "station_id": self.station_id,
            "station_name": self.station_name,
            "station_yard_section_id": self.station_yard_section_id,
            "station_yard_track_id": self.station_yard_track_id,
            "station_yard_route_section_ids": self.station_yard_route_section_ids,
            "edge_offset_m": (
                None if self.edge_offset_m is None else round(self.edge_offset_m, 3)
            ),
            "direction_code": self.direction_code,
            "direction": self.protocol_direction,
            "direction_text": (
                "reverse"
                if self.direction_code < 0
                else "neutral"
                if self.direction_code == 0
                else "forward"
            ),
            "direction_sign": self.protocol_direction,
            "traction_level": self.traction_level,
            "brake_level": self.brake_level,
            "traction_percent": round(self.traction_percent, 3),
            "brake_percent": round(self.brake_percent, 3),
            "actual_traction_force_n": round(self.actual_traction_force_n, 3),
            "actual_brake_force_n": round(self.actual_brake_force_n, 3),
            "atp_intervention": self.atp_intervention,
            "driving_mode": self.driving_mode,
            "control_source": self.control_source,
            "ato_active": self.ato_active,
            "ato_capable": self.ato_capable,
            "ato_start_requested": self.ato_start_requested,
            "ato_start_accepted": self.ato_start_accepted,
            "ato_start_reject_reason": self.ato_start_reject_reason,
            "auto_reverse_cap": self.auto_reverse_cap,
            "auto_reverse_active": self.auto_reverse_active,
            "recommended_speed_kmh": self.recommended_speed_kmh,
            "recommended_speed": (
                None
                if self.recommended_speed_kmh is None
                else round(self.recommended_speed_kmh, 3)
            ),
            "recommended_speed_mps": round(
                (0.0 if self.recommended_speed_kmh is None else self.recommended_speed_kmh)
                / 3.6,
                3,
            ),
            "ato_state": self.ato_state,
            "ato_target_speed_kmh": round(self.ato_target_speed_kmh, 3),
            "ato_target_speed": round(self.ato_target_speed_kmh, 3),
            "ato_target_speed_mps": round(self.ato_target_speed_kmh / 3.6, 3),
            "ato_traction_level": self.ato_traction_level,
            "ato_brake_level": self.ato_brake_level,
            "commanded_traction_level": self.commanded_traction_level,
            "commanded_brake_level": self.commanded_brake_level,
            "applied_traction_level": self.applied_traction_level,
            "applied_brake_level": self.applied_brake_level,
            "atp_intervened": self.atp_intervened,
            "stop_target": (
                None if self.stop_target is None else round(self.stop_target, 3)
            ),
            "distance_to_stop": (
                None if self.distance_to_stop is None else round(self.distance_to_stop, 3)
            ),
            "stop_result": self.stop_result,
            "door_state": self.door_state,
            "left_door_open": self.left_door_open,
            "right_door_open": self.right_door_open,
            "doors_all_closed": self.doors_all_closed,
            "door_open_light": not self.doors_all_closed,
            "door_mode": self.door_mode,
            "door_closed_light": self.door_closed_light,
            "high_voltage_light": self.high_voltage_light,
            "high_voltage_on": self.high_voltage_light,
            "brake_bad_light": self.brake_bad_light,
            "parking_brake": self.parking_brake,
            "external_speed_limit_kmh": self.external_speed_limit_kmh,
            "active_faults": list(self.active_faults),
            "atp_supervision_state": self.atp_supervision_state,
            "atp_reason": self.atp_reason,
            "atp_allowed_speed_kmh": (
                None
                if self.atp_allowed_speed_kmh is None
                else round(self.atp_allowed_speed_kmh, 3)
            ),
            "atp_speed_limit_source": self.atp_speed_limit_source,
            "atp_track_speed_limit_kmh": (
                None
                if self.atp_track_speed_limit_kmh is None
                else round(self.atp_track_speed_limit_kmh, 3)
            ),
            "atp_ma_allowed_speed_kmh": (
                None
                if self.atp_ma_allowed_speed_kmh is None
                else round(self.atp_ma_allowed_speed_kmh, 3)
            ),
            "atp_external_speed_limit_kmh": (
                None
                if self.atp_external_speed_limit_kmh is None
                else round(self.atp_external_speed_limit_kmh, 3)
            ),
            "atp_eb_trigger_speed_kmh": (
                None
                if self.atp_eb_trigger_speed_kmh is None
                else round(self.atp_eb_trigger_speed_kmh, 3)
            ),
            "atp_distance_to_authority_m": (
                None
                if self.atp_distance_to_authority_m is None
                else round(self.atp_distance_to_authority_m, 3)
            ),
            "atp_service_stop_distance_m": (
                None
                if self.atp_service_stop_distance_m is None
                else round(self.atp_service_stop_distance_m, 3)
            ),
            "atp_emergency_stop_distance_m": (
                None
                if self.atp_emergency_stop_distance_m is None
                else round(self.atp_emergency_stop_distance_m, 3)
            ),
            "atp_debug": self.atp_debug,
            "ato_brake_bias": round(self.ato_brake_bias, 3),
            "ato_brake_bias_enabled": self.ato_brake_bias_enabled,
            "ato_brake_bias_adaptation_enabled": (
                self.ato_brake_bias_adaptation_enabled
            ),
            "last_brake_bias_adjustment": self.last_brake_bias_adjustment,
            "brake_bias_history_size": self.brake_bias_history_size,
            "curve_output_enabled": self.curve_output_enabled,
            "curve_history_size": self.curve_history_size,
            "curve_point": self.curve_point,
        }
        try:
            from app.data_flow.visual_mapping import build_visual_payload

            protocol.update(build_visual_payload(protocol))
        except Exception:
            logger.exception("Failed to enrich train_state with visual mapping")
        return protocol


@dataclass
class DriverInput:
    vehicle_id: str
    line_id: str
    source: str
    control_mode: str
    traction_level: int
    brake_level: int
    direction: str
    emergency_button: bool
    main_handle_raw: Optional[int] = None
    command: Optional[int] = None
    percent: Optional[float] = None
    main_handle_state: Optional[int] = None
    traction_percent: Optional[float] = None
    brake_percent: Optional[float] = None
    direction_code: Optional[int] = None
    emergency_cmd: Optional[bool] = None
    key_switch: Optional[bool] = None
    ato_start_btn: bool = False
    ato_capable: Optional[bool] = None
    ato_active: Optional[bool] = None
    auto_reverse_cap: Optional[bool] = None
    auto_reverse_active: Optional[bool] = None
    auto_rev_flag: bool = False
    mode_up_confirm: bool = False
    mode_dn_confirm: bool = False
    vigilance: bool = False
    vigilance_allow: bool = False
    forced_release: bool = False
    parking_apply: bool = False
    parking_release: bool = False
    brake_bad_light: Optional[bool] = None
    network_fault_light: Optional[bool] = None
    open_left_door: bool = False
    open_right_door: bool = False
    close_left_door: bool = False
    close_right_door: bool = False
    door_mode: Optional[str] = None
    door_closed_light: Optional[bool] = None
    high_voltage_light: Optional[bool] = None
    forced_pump: bool = False
    horn: bool = False
    confirm_flag: bool = False
    trac_aux_reset: bool = False
    wash_mode_switch: bool = False
    frame_seq: Optional[int] = None
    message_id: Optional[str] = None
    raw_brake_level: Optional[int] = None
    fast_brake: bool = False


@dataclass
class AtoCommand:
    vehicle_id: str
    line_id: str
    control_mode: str
    target_speed: float
    target_position: Optional[float]
    traction_level: int
    brake_level: int
    reason: str
    command: Optional[int] = None
    percent: Optional[float] = None


@dataclass
class MaLimit:
    vehicle_id: str
    ma_limit: Optional[float]
    target_speed: Optional[float]
    reason: str
    allowed_speed_kmh: Optional[float] = None
    eb_trigger_speed_kmh: Optional[float] = None
    target_distance_m: Optional[float] = None
    permission: Optional[str] = None
    signal_state: Optional[str] = None
    speed_limit_reason: Optional[str] = None
    speed_limit_warning: bool = False
    upcoming_speed_limit_kmh: Optional[float] = None
    speed_limit_warning_distance_m: Optional[float] = None
    updated_at: Optional[float] = None


@dataclass
class PowerState:
    substation_id: str
    voltage: float
    current: float
    power: float
    is_fault: bool


@dataclass
class CommState:
    source: str
    driver_console_connected: bool
    zmq_connected: bool
    last_message_at: float


@dataclass
class TrackSection:
    section_id: str
    start: float
    end: float
    gradient: float
    speed_limit: float
    station_id: Optional[str]
    stop_position: Optional[float]
    edge_id: Optional[int] = None
    begin_km: Optional[float] = None
    end_km: Optional[float] = None
    begin_switch: Optional[str] = None
    end_switch: Optional[str] = None
    direction_code: int = 1
