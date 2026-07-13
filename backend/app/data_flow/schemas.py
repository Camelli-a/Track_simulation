from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


DataSource = Literal[
    "mock",
    "udp",
    "zmq",
    "frontend",
    "vehicle_udp",
    "vehicle_api",
    "driver_tcp",
    "signal_zmq",
    "power_adapter",
    "track_adapter",
    "unknown",
]
SystemState = Literal["running", "degraded", "emergency", "offline"]
TrainMode = Literal["manual", "ato", "atp", "emergency", "unknown"]
SignalLightState = Literal["red", "yellow", "green", "unknown"]
MovementPermission = Literal["allow", "restricted", "stop", "unknown"]
ParkingPhase = Literal["cruising", "approaching", "braking", "docking", "stopped"]
SectionCondition = Literal["normal", "warning", "fault"]
SectionAspect = Literal["green", "yellow", "red", "unknown"]
SwitchPosition = Literal["normal", "reverse", "unknown"]
AlarmLevel = Literal["info", "warning", "critical"]
RouteRequestStatus = Literal["pending", "accepted", "rejected", "unknown"]
PrimaryChart = Literal[
    "speed_distance",
    "speed_time",
    "line_overview",
    "ma_distance",
    "atp_margin_chart",
    "stop_result_chart",
    "event_timeline",
    "driver_input_timeline",
]
PanelId = Literal[
    "target_vehicle_summary",
    "network_impact_summary",
    "stop_target",
    "signal_status",
    "ma_status",
    "atp_status",
    "control_output",
    "driver_input",
    "affected_vehicles",
    "blocked_section",
    "event_timeline",
    "driver_input_timeline",
    "stop_result",
    "external_system_status",
    "recommended_speed",
]
IntegrationMode = Literal["simulation", "realtime", "hybrid", "degraded"]
RealtimeChannel = Literal["websocket", "rest_polling", "zmq", "none"]
TrackType = Literal["main", "arrival_departure", "siding", "turnback", "platform", "depot", "unknown"]
GeometryType = Literal["point", "polyline"]


class IncomingMessage(BaseModel):
    """Loose input envelope for ZMQ/Mock messages from other modules."""

    type: str
    timestamp: float
    source: str = "unknown"
    data: Dict[str, Any] = Field(default_factory=dict)


class SystemStatus(BaseModel):
    status: SystemState = "running"
    system_mode: str = "normal"
    data_source: DataSource = "mock"
    zmq_connected: bool = False
    websocket_clients: int = 0
    degraded_reasons: List[str] = Field(default_factory=list)


class ExternalConnections(BaseModel):
    power: bool = False
    signal_screen: bool = False
    cab_screen: bool = False
    viewer_3d: bool = False
    driver_desk: bool = False


class IntegrationStatus(BaseModel):
    integration_mode: IntegrationMode = "simulation"
    realtime_channel: RealtimeChannel = "websocket"
    driver_desk_connected: bool = False
    active_driver_vehicle_id: Optional[str] = None
    external_connections: ExternalConnections = Field(default_factory=ExternalConnections)
    degraded: bool = False
    last_realtime_message_at: Optional[float] = None


class CommunicationStatus(BaseModel):
    source: DataSource = "mock"
    driver_console_connected: bool = False
    udp_connected: bool = False
    zmq_connected: bool = False
    latency_ms: Optional[float] = None
    packet_loss_count: int = 0
    last_message_at: Optional[float] = None
    last_real_message_at: Optional[float] = None
    no_message_seconds: Optional[float] = None


class DriverInput(BaseModel):
    vehicle_id: str
    line_id: str = "LINE-1"
    source: DataSource = "mock"
    traction_level: int = Field(default=0, ge=0, le=4)
    brake_level: int = Field(default=0, ge=0, le=7)
    traction_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    brake_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    main_handle_raw: Optional[int] = None
    key_switch: Optional[bool] = None
    direction: Literal["forward", "reverse", "backward", "neutral"] = "forward"
    direction_code: Optional[int] = Field(default=None, ge=0, le=2)
    control_mode: Literal["manual", "ato"] = "manual"
    emergency_button: bool = False
    emergency_cmd: bool = False
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
    wash_mode_status: Optional[bool] = None
    frame_seq: Optional[int] = None
    message_id: Optional[str] = None
    updated_at: float
    received_at: Optional[float] = None
    protocol: Optional[str] = None
    adapter: Optional[str] = None
    is_stale: bool = False
    stale_after_seconds: Optional[float] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class TrainSnapshot(BaseModel):
    vehicle_id: str
    line_id: str = "LINE-1"
    route_id: str = "R_MAIN"
    position: float = 0.0
    speed: float = 0.0
    acceleration: float = 0.0
    position_m: Optional[float] = None
    speed_ms: Optional[float] = None
    speed_mps: Optional[float] = None
    speed_kmh: Optional[float] = None
    vehicle_speed_kmh: Optional[float] = None
    acceleration_mps2: Optional[float] = None
    direction: Optional[int] = None
    train_length: Optional[float] = None
    train_index: Optional[int] = None
    mileage: Optional[float] = None
    direction_code: Optional[int] = None
    active_cab: Optional[int] = None
    edge_id: Optional[int] = None
    section_id: Optional[str] = None
    station_id: Optional[str] = None
    track_id: Optional[str] = None
    station_yard_section_id: Optional[str] = None
    station_yard_track_id: Optional[str] = None
    station_yard_route_section_ids: Optional[List[str]] = None
    edge_offset_m: Optional[float] = None
    mode: TrainMode = "unknown"
    is_running: bool = True
    emergency_brake: bool = False
    fault_speed_limit: Optional[float] = None
    traction_level: Optional[int] = None
    brake_level: Optional[int] = None
    traction_percent: Optional[float] = None
    brake_percent: Optional[float] = None
    actual_traction_force_n: Optional[float] = None
    actual_brake_force_n: Optional[float] = None
    atp_intervention: Optional[bool] = None
    driving_mode: Optional[str] = None
    control_source: Optional[str] = None
    ato_capable: Optional[bool] = None
    auto_reverse_cap: Optional[bool] = None
    auto_reverse_active: Optional[bool] = None
    wash_mode_status: Optional[bool] = None
    recommended_speed_kmh: Optional[float] = None
    recommended_speed_mps: Optional[float] = None
    ato_target_speed_kmh: Optional[float] = None
    ato_target_speed_mps: Optional[float] = None
    ato_state: Optional[str] = None
    ato_traction_level: Optional[int] = None
    ato_brake_level: Optional[int] = None
    commanded_traction_level: Optional[int] = None
    commanded_brake_level: Optional[int] = None
    applied_traction_level: Optional[int] = None
    applied_brake_level: Optional[int] = None
    atp_intervened: Optional[bool] = None
    stop_target: Optional[float] = None
    distance_to_stop: Optional[float] = None
    stop_result: Optional[Dict[str, Any]] = None
    parking_brake: Optional[bool] = None
    high_voltage_on: Optional[bool] = None
    door_open_light: Optional[bool] = None
    external_speed_limit_kmh: Optional[float] = None
    active_faults: List[str] = Field(default_factory=list)
    door_mode: Optional[str] = None
    door_state: Optional[str] = None
    doors_all_closed: Optional[bool] = None
    door_closed_light: Optional[bool] = None
    high_voltage_light: Optional[bool] = None
    brake_bad_light: Optional[bool] = None
    ato_active: Optional[bool] = None
    parking_apply: Optional[bool] = None
    parking_release: Optional[bool] = None
    ma_limit: Optional[float] = None
    distance_to_ma: Optional[float] = None
    permission: MovementPermission = "unknown"
    signal_state: SignalLightState = "unknown"
    speed_limit: Optional[float] = None
    target_speed: Optional[float] = None
    route_speed_limit: Optional[float] = None
    required_stop_distance: Optional[float] = None
    emergency_stop_distance: Optional[float] = None
    warning_distance: Optional[float] = None
    braking_curve_speed_limit: Optional[float] = None
    braking_model: Optional[str] = None
    front_vehicle_id: Optional[str] = None
    front_protection_point: Optional[float] = None
    energy_kwh: Optional[float] = None
    stop_distance: Optional[float] = None
    station_name: Optional[str] = None
    parking_phase: ParkingPhase = "cruising"
    stop_error_cm: Optional[float] = None
    platform_id: Optional[str] = None
    updated_at: float
    received_at: Optional[float] = None
    source: DataSource = "unknown"
    protocol: Optional[str] = None
    adapter: Optional[str] = None
    is_stale: bool = False
    stale_after_seconds: Optional[float] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    ato_brake_bias: Optional[float] = None
    ato_brake_bias_enabled: Optional[bool] = None
    ato_brake_bias_adaptation_enabled: Optional[bool] = None
    last_brake_bias_adjustment: Optional[Dict[str, Any]] = None
    brake_bias_history_size: Optional[int] = None
    curve_output_enabled: Optional[bool] = None
    curve_history_size: Optional[int] = None
    curve_point: Optional[Dict[str, Any]] = None
    input_lights: Dict[str, Any] = Field(default_factory=dict)
    output_lights: Dict[str, Any] = Field(default_factory=dict)
    plc_feedback: Dict[str, Any] = Field(default_factory=dict)
    ato_guidance: Dict[str, Any] = Field(default_factory=dict)


class TrackSectionSnapshot(BaseModel):
    section_id: str
    line_id: str = "LINE-1"
    track_seg_id: Optional[str] = None
    track_id: Optional[str] = None
    start: float
    end: float
    gradient: Optional[float] = None
    speed_limit: Optional[float] = None
    station_id: Optional[str] = None
    stop_position: Optional[float] = None
    occupied: bool = False
    vehicle_id: Optional[str] = None
    occupied_by: Optional[str] = None
    aspect: SectionAspect = "green"
    locked: bool = False
    locked_by_route_id: Optional[str] = None
    condition: SectionCondition = "normal"
    received_at: Optional[float] = None
    source: DataSource = "unknown"
    protocol: Optional[str] = None
    adapter: Optional[str] = None
    is_stale: bool = False
    stale_after_seconds: Optional[float] = None


class SignalSnapshot(BaseModel):
    signal_id: str
    position: float = 0.0
    state: SignalLightState = "unknown"
    color_code: Optional[int] = None
    station_id: Optional[str] = None
    track_id: Optional[str] = None
    section_id: Optional[str] = None
    direction: Optional[str] = None
    signal_type: Optional[str] = None
    route_id: Optional[str] = None
    protects_switch_id: Optional[str] = None
    protects_section_id: Optional[str] = None
    signal_state: SignalLightState = "unknown"
    permission: MovementPermission = "unknown"
    received_at: Optional[float] = None
    source: DataSource = "unknown"
    protocol: Optional[str] = None
    adapter: Optional[str] = None
    is_stale: bool = False
    stale_after_seconds: Optional[float] = None


class SwitchSnapshot(BaseModel):
    switch_id: str
    position: SwitchPosition = "unknown"
    turnout_id: Optional[str] = None
    station_id: Optional[str] = None
    switch_type: Optional[str] = None
    connects: List[str] = Field(default_factory=list)
    normal_to: Optional[str] = None
    reverse_to: Optional[str] = None
    routing: SwitchPosition = "unknown"
    state: SwitchPosition = "unknown"
    locked: bool = False
    locked_by_route_id: Optional[str] = None
    related_section: Optional[str] = None
    reason: Optional[str] = None
    received_at: Optional[float] = None
    source: DataSource = "unknown"
    protocol: Optional[str] = None
    adapter: Optional[str] = None
    is_stale: bool = False
    stale_after_seconds: Optional[float] = None


class RouteResult(BaseModel):
    vehicle_id: Optional[str] = None
    route_id: Optional[str] = None
    allowed: bool = False
    reason: Optional[str] = None
    required_switch_id: Optional[str] = None
    required_position: Optional[SwitchPosition] = None
    current_position: Optional[SwitchPosition] = None
    locked_by_route_id: Optional[str] = None


class RouteRequestSnapshot(BaseModel):
    request_id: Optional[str] = None
    vehicle_id: str
    route_id: str = "R_MAIN"
    origin_section_id: Optional[str] = None
    destination_section_id: Optional[str] = None
    start_position: Optional[float] = None
    end_position: Optional[float] = None
    priority: int = 0
    status: RouteRequestStatus = "pending"
    reason: Optional[str] = None
    updated_at: float
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class MovementAuthoritySnapshot(BaseModel):
    vehicle_id: str
    position: Optional[float] = None
    route_id: str = "R_MAIN"
    station_id: Optional[str] = None
    station_name: Optional[str] = None
    station_yard_section_id: Optional[str] = None
    station_yard_track_id: Optional[str] = None
    station_yard_route_section_ids: Optional[List[str]] = None
    ma_limit: float
    distance_to_ma: Optional[float] = None
    permission: MovementPermission = "unknown"
    signal_state: SignalLightState = "unknown"
    speed_limit: Optional[float] = None
    target_speed: Optional[float] = None
    reason: Optional[str] = None
    front_vehicle_id: Optional[str] = None
    front_train_length: Optional[float] = None
    location_uncertainty: Optional[float] = None
    communication_margin: Optional[float] = None
    safety_margin: Optional[float] = None
    front_protection_point: Optional[float] = None
    safe_distance: Optional[float] = None
    current_speed: Optional[float] = None
    route_speed_limit: Optional[float] = None
    required_stop_distance: Optional[float] = None
    emergency_stop_distance: Optional[float] = None
    warning_distance: Optional[float] = None
    braking_curve_speed_limit: Optional[float] = None
    braking_model: Optional[str] = None
    updated_at: float
    received_at: Optional[float] = None
    source: DataSource = "unknown"
    protocol: Optional[str] = None
    adapter: Optional[str] = None
    is_stale: bool = False
    stale_after_seconds: Optional[float] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class AtoCommandSnapshot(BaseModel):
    vehicle_id: str
    line_id: str = "LINE-1"
    control_mode: Literal["ato"] = "ato"
    target_speed: float = 0.0
    target_position: Optional[float] = None
    traction_level: int = 0
    brake_level: int = 0
    reason: str = "test"
    updated_at: float
    received_at: Optional[float] = None
    source: DataSource = "unknown"
    protocol: Optional[str] = None
    adapter: Optional[str] = None
    is_stale: bool = False
    stale_after_seconds: Optional[float] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class PowerSnapshot(BaseModel):
    substation_id: str = "SS-01"
    voltage: float = 0.0
    current: float = 0.0
    power: float = 0.0
    is_fault: bool = False
    updated_at: Optional[float] = None
    received_at: Optional[float] = None
    source: DataSource = "unknown"
    protocol: Optional[str] = None
    adapter: Optional[str] = None
    is_stale: bool = False
    stale_after_seconds: Optional[float] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class AlarmEvent(BaseModel):
    alarm_id: str
    level: AlarmLevel = "info"
    level_label: Optional[str] = None
    source: str = "BACKEND"
    source_label: Optional[str] = None
    vehicle_id: Optional[str] = None
    message: str
    timestamp: float
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class CommandAckSnapshot(BaseModel):
    command_id: Optional[str] = None
    topic: str = "unknown"
    vehicle_id: Optional[str] = None
    accepted: bool = False
    status: str = "unknown"
    reason: Optional[str] = None
    updated_at: float
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class ScenarioPageConfig(BaseModel):
    hero_panel: PanelId = "target_vehicle_summary"
    primary_chart: PrimaryChart = "speed_distance"
    secondary_chart: Optional[PrimaryChart] = None
    panels: List[PanelId] = Field(default_factory=list)
    key_metrics: List[str] = Field(default_factory=list)
    highlight_events: List[str] = Field(default_factory=list)


class ScenarioConfig(BaseModel):
    scenario_id: str
    name: str
    description: Optional[str] = None
    page_config: ScenarioPageConfig


class LayoutGeometry(BaseModel):
    type: GeometryType = "point"
    x: Optional[float] = None
    y: Optional[float] = None
    points: List[List[float]] = Field(default_factory=list)


class YardTrack(BaseModel):
    track_id: str
    track_name: str
    station_id: str
    track_type: TrackType = "unknown"
    direction: Optional[str] = None
    section_ids: List[str] = Field(default_factory=list)
    geometry: Optional[LayoutGeometry] = None


class YardSwitch(BaseModel):
    switch_id: str
    station_id: str
    switch_type: str = "single"
    connects: List[str] = Field(default_factory=list)
    normal_to: Optional[str] = None
    reverse_to: Optional[str] = None
    geometry: Optional[LayoutGeometry] = None


class YardSignal(BaseModel):
    signal_id: str
    station_id: str
    track_id: Optional[str] = None
    direction: Optional[str] = None
    protects_switch_id: Optional[str] = None
    protects_section_id: Optional[str] = None
    geometry: Optional[LayoutGeometry] = None


class YardSection(BaseModel):
    section_id: str
    station_id: str
    track_id: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    geometry: Optional[LayoutGeometry] = None


class YardStation(BaseModel):
    station_id: str
    station_name: str
    track_ids: List[str] = Field(default_factory=list)
    switch_ids: List[str] = Field(default_factory=list)
    signal_ids: List[str] = Field(default_factory=list)
    section_ids: List[str] = Field(default_factory=list)
    tracks: List[YardTrack] = Field(default_factory=list)
    switches: List[YardSwitch] = Field(default_factory=list)
    signals: List[YardSignal] = Field(default_factory=list)
    sections: List[YardSection] = Field(default_factory=list)


class YardLayoutSnapshot(BaseModel):
    line_id: str = "LINE-1"
    stations: List[YardStation] = Field(default_factory=list)
    yard_tracks: List[YardTrack] = Field(default_factory=list)
    yard_switches: List[YardSwitch] = Field(default_factory=list)
    yard_signals: List[YardSignal] = Field(default_factory=list)
    yard_sections: List[YardSection] = Field(default_factory=list)
    updated_at: Optional[float] = None


class DashboardSnapshot(BaseModel):
    type: Literal["dashboard_snapshot"] = "dashboard_snapshot"
    protocol_version: str = "1.0"
    timestamp: float
    system: SystemStatus
    communication: CommunicationStatus
    integration: IntegrationStatus = Field(default_factory=IntegrationStatus)
    scenarios: List[ScenarioConfig] = Field(default_factory=list)
    driver_inputs: List[DriverInput] = Field(default_factory=list)
    ato_commands: List[AtoCommandSnapshot] = Field(default_factory=list)
    trains: List[TrainSnapshot] = Field(default_factory=list)
    ma_limits: List[MovementAuthoritySnapshot] = Field(default_factory=list)
    sections: List[TrackSectionSnapshot] = Field(default_factory=list)
    signals: List[SignalSnapshot] = Field(default_factory=list)
    switches: List[SwitchSnapshot] = Field(default_factory=list)
    route_requests: List[RouteRequestSnapshot] = Field(default_factory=list)
    route_results: List[RouteResult] = Field(default_factory=list)
    command_acks: List[CommandAckSnapshot] = Field(default_factory=list)
    power: PowerSnapshot = Field(default_factory=PowerSnapshot)
    alarms: List[AlarmEvent] = Field(default_factory=list)


class VehicleRegistrationCommand(BaseModel):
    vehicle_id: str
    line_id: str = "LINE-1"
    route_id: str = "R_MAIN"
    position: float = 0.0
    speed: float = 0.0
    acceleration: float = 0.0
    train_length: Optional[float] = None
    mode: TrainMode = "manual"
    is_running: bool = False
    emergency_brake: bool = False


class RouteRequestCommand(BaseModel):
    vehicle_id: str
    route_id: str = "R_MAIN"
    request_id: Optional[str] = None
    origin_section_id: Optional[str] = None
    destination_section_id: Optional[str] = None
    start_position: Optional[float] = None
    end_position: Optional[float] = None
    priority: int = 0
