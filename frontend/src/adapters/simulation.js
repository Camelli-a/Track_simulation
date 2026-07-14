/** WebSocket 数据适配层：协议 v1.0 dashboard_snapshot + 旧版 tick 兼容 */

const SUPPORTED_TYPES = new Set(['dashboard_snapshot', 'tick'])

export function normalizeTick(raw) {
  if (!raw || !SUPPORTED_TYPES.has(raw.type)) return null
  if (raw.type === 'dashboard_snapshot') return normalizeDashboardSnapshot(raw)
  return normalizeLegacyTick(raw)
}

export function normalizeSceneState(raw) {
  if (!raw) return null
  return {
    type: raw.type ?? 'dashboard_scene_state',
    timestamp: raw.timestamp ?? Date.now() / 1000,
    active_scene: normalizeSceneStateItem(raw.active_scene),
    vehicle_scene_map: (raw.vehicle_scene_map ?? []).map(normalizeSceneStateItem),
  }
}

function normalizeDashboardSnapshot(raw) {
  return {
    type: 'dashboard_snapshot',
    protocol_version: raw.protocol_version ?? '1.0',
    timestamp: raw.timestamp ?? Date.now() / 1000,
    scenarios: (raw.scenarios ?? []).map(normalizeScenarioConfig),
    communication: normalizeCommunication(raw.communication),
    driver_inputs: (raw.driver_inputs ?? []).map(normalizeDriverInput),
    ato_commands: (raw.ato_commands ?? []).map(normalizeAtoCommand),
    vehicles: (raw.trains ?? []).map(normalizeVehicle),
    ma_limits: (raw.ma_limits ?? []).map(normalizeMaLimit),
    track_segments: (raw.sections ?? []).map(normalizeSection),
    signals: (raw.signals ?? []).map(normalizeSignal),
    turnouts: (raw.switches ?? []).map(normalizeSwitch),
    route_results: (raw.route_results ?? []).map(normalizeRouteResult),
    power: normalizePower(raw.power),
    alarms: (raw.alarms ?? []).map(normalizeAlarm),
    system: raw.system ?? null,
    system_mode: deriveSystemMode(raw),
    stations: raw.stations ?? [],
    total_length: raw.total_length ?? null,
  }
}

function normalizeLegacyTick(raw) {
  return {
    type: 'tick',
    protocol_version: raw.protocol_version ?? null,
    timestamp: raw.timestamp ?? Date.now() / 1000,
    scenarios: (raw.scenarios ?? []).map(normalizeScenarioConfig),
    communication: normalizeCommunication(raw.communication ?? raw.comm_state),
    driver_inputs: (raw.driver_inputs ?? []).map(normalizeDriverInput),
    ato_commands: (raw.ato_commands ?? []).map(normalizeAtoCommand),
    vehicles: (raw.vehicles ?? raw.trains ?? []).map(normalizeVehicle),
    ma_limits: (raw.ma_limits ?? raw.ma_states ?? []).map(normalizeMaLimit),
    track_segments: (raw.track_segments ?? raw.sections ?? []).map(normalizeSection),
    signals: (raw.signals ?? []).map(normalizeSignal),
    turnouts: (raw.turnouts ?? raw.switches ?? []).map(normalizeSwitch),
    route_results: (raw.route_results ?? []).map(normalizeRouteResult),
    power: normalizePower(raw.power),
    alarms: (raw.alarms ?? []).map(normalizeAlarm),
    system: raw.system ?? null,
    system_mode: deriveSystemMode(raw),
    stations: raw.stations ?? [],
    total_length: raw.total_length ?? null,
  }
}

function normalizeVehicle(v) {
  const mode = v.mode ?? v.drive_mode ?? 'manual'
  return {
    vehicle_id: v.vehicle_id,
    train_index: v.train_index ?? v.trainIndex ?? null,
    line_id: v.line_id ?? null,
    route_id: v.route_id ?? v.routeId ?? null,
    position: v.position ?? 0,
    speed: v.speed ?? 0,
    speed_kmh: v.speed_kmh ?? v.vehicle_speed_kmh ?? v.speed ?? 0,
    acceleration: v.acceleration ?? 0,
    mode,
    driving_mode: v.driving_mode ?? v.drivingMode ?? null,
    control_source: v.control_source ?? v.controlSource ?? null,
    is_running: v.is_running ?? true,
    emergency_brake: Boolean(v.emergency_brake),
    atp_intervention: Boolean(v.atp_intervention ?? v.atp_intervened),
    atp_intervened: Boolean(v.atp_intervened ?? v.atp_intervention),
    atp_state: v.atp_state ?? null,
    atp_reason: v.atp_reason ?? v.reason ?? null,
    ma_limit: v.ma_limit ?? v.ma_end ?? null,
    distance_to_ma: v.distance_to_ma ?? v.distanceToMa ?? null,
    permission: v.permission ?? 'unknown',
    signal_state: v.signal_state ?? v.signalState ?? 'unknown',
    speed_limit: v.speed_limit ?? v.limitSpeed ?? null,
    target_speed: v.target_speed ?? v.target_speed_limit ?? null,
    recommended_speed_kmh: v.recommended_speed_kmh ?? v.recommended_speed ?? null,
    ato_target_speed_kmh: v.ato_target_speed_kmh ?? null,
    ato_state: v.ato_state ?? null,
    ato_active: Boolean(v.ato_active),
    ato_capable: Boolean(v.ato_capable),
    commanded_traction_level: v.commanded_traction_level ?? null,
    commanded_brake_level: v.commanded_brake_level ?? null,
    door_closed_light: v.door_closed_light ?? null,
    parking_release: v.parking_release ?? null,
    route_speed_limit: v.route_speed_limit ?? null,
    required_stop_distance: v.required_stop_distance ?? null,
    emergency_stop_distance: v.emergency_stop_distance ?? null,
    warning_distance: v.warning_distance ?? null,
    braking_curve_speed_limit: v.braking_curve_speed_limit ?? v.brakingCurveSpeedLimit ?? null,
    braking_model: v.braking_model ?? v.brakingModel ?? null,
    front_vehicle_id: v.front_vehicle_id ?? v.frontTrainId ?? null,
    front_protection_point: v.front_protection_point ?? null,
    energy_kwh: v.energy_kwh ?? 0,
    stop_distance: v.stop_distance ?? null,
    station_name: v.station_name ?? null,
    parking_phase: v.parking_phase ?? deriveParkingPhase(v),
    stop_error_cm: v.stop_error_cm ?? null,
    platform_id: v.platform_id ?? null,
    station_id: v.station_id ?? v.stationId ?? null,
    track_id: v.track_id ?? v.trackId ?? null,
    section_id: v.section_id ?? v.sectionId ?? null,
    station_yard_section_id: v.station_yard_section_id ?? v.stationYardSectionId ?? null,
    station_yard_track_id: v.station_yard_track_id ?? v.stationYardTrackId ?? null,
    station_yard_route_section_ids: v.station_yard_route_section_ids ?? v.stationYardRouteSectionIds ?? [],
    edge_id: v.edge_id ?? v.edgeId ?? null,
    edge_offset_m: v.edge_offset_m ?? v.edgeOffsetM ?? null,
    direction_code: v.direction_code ?? v.directionCode ?? null,
    updated_at: v.updated_at ?? null,
    raw_data: v.raw_data ?? {},
  }
}

function deriveParkingPhase(v) {
  const sd = v.stop_distance
  const speed = v.speed ?? 0
  if (sd == null) return 'cruising'
  if (speed < 1 && sd < 5) return 'stopped'
  if (sd < 20 && speed < 8) return 'docking'
  if (sd < 200 && speed < 45) return 'braking'
  if (sd < 800) return 'approaching'
  return 'cruising'
}

function normalizeSection(s) {
  const segmentId = s.section_id ?? s.segment_id
  const occupied = Boolean(s.occupied)
  const aspect = s.aspect
    ?? (s.condition === 'warning' ? 'yellow' : null)
    ?? (s.condition === 'fault' ? 'red' : null)
    ?? (occupied ? 'red' : 'green')
  return {
    section_id: segmentId,
    segment_id: segmentId,
    line_id: s.line_id ?? null,
    track_seg_id: s.track_seg_id ?? null,
    track_id: s.track_id ?? s.trackId ?? null,
    start: s.start ?? 0,
    end: s.end ?? 0,
    gradient: s.gradient ?? null,
    speed_limit: s.speed_limit ?? null,
    station_id: s.station_id ?? null,
    stop_position: s.stop_position ?? null,
    occupied,
    aspect,
    condition: s.condition ?? 'normal',
    occupied_by: s.vehicle_id ?? s.occupied_by ?? null,
    locked: Boolean(s.locked),
    locked_by_route_id: s.locked_by_route_id ?? null,
  }
}

function normalizeSignal(s) {
  const state = s.state ?? s.signal_state ?? 'green'
  return {
    signal_id: s.signal_id,
    position: s.position ?? 0,
    state,
    signal_type: s.signal_type ?? null,
    route_id: s.route_id ?? null,
    signal_state: s.signal_state ?? state,
    permission: s.permission ?? 'unknown',
  }
}

/** 协议 switches.position 为 routing；公里标由静态 layout 提供 */
function normalizeSwitch(sw) {
  const id = sw.switch_id ?? sw.turnout_id
  const routing = sw.routing
    ?? (typeof sw.position === 'string' ? sw.position : null)
    ?? sw.state
    ?? 'normal'

  return {
    switch_id: id,
    turnout_id: id,
    position: typeof sw.position === 'string' ? sw.position : 'unknown',
    routing,
    state: routing,
    locked: Boolean(sw.locked),
    related_section: sw.related_section ?? null,
    locked_by_route_id: sw.locked_by_route_id ?? null,
    reason: sw.reason ?? null,
  }
}

function normalizePower(p) {
  if (!p) return null
  return {
    substation_id: p.substation_id ?? null,
    voltage: p.voltage ?? 0,
    current: p.current ?? 0,
    power: p.power ?? 0,
    is_fault: Boolean(p.is_fault),
    updated_at: p.updated_at ?? null,
    raw_data: p.raw_data ?? {},
  }
}

function normalizeAlarm(a) {
  return {
    alarm_id: a.alarm_id ?? `ALM-${a.timestamp ?? Date.now()}`,
    level: a.level ?? 'info',
    level_label: a.level_label ?? levelLabel(a.level),
    source: a.source ?? 'BACKEND',
    source_label: a.source_label ?? sourceLabel(a.source),
    vehicle_id: a.vehicle_id ?? null,
    message: a.message ?? '',
    timestamp: a.timestamp ?? null,
    raw_data: a.raw_data ?? {},
  }
}

function normalizeCommunication(comm) {
  if (!comm) return null
  return {
    source: comm.source ?? 'unknown',
    driver_console_connected: Boolean(comm.driver_console_connected),
    udp_connected: Boolean(comm.udp_connected),
    zmq_connected: Boolean(comm.zmq_connected),
    latency_ms: comm.latency_ms ?? null,
    packet_loss_count: comm.packet_loss_count ?? 0,
    last_message_at: comm.last_message_at ?? null,
  }
}

function normalizeDriverInput(input) {
  return {
    vehicle_id: input.vehicle_id,
    line_id: input.line_id ?? 'LINE-1',
    source: input.source ?? 'unknown',
    main_handle_raw: input.main_handle_raw ?? null,
    traction_level: input.traction_level ?? 0,
    brake_level: input.brake_level ?? 0,
    direction: input.direction ?? 'forward',
    control_mode: input.control_mode ?? 'manual',
    key_switch: Boolean(input.key_switch),
    door_closed_light: Boolean(input.door_closed_light),
    ato_start_btn: Boolean(input.ato_start_btn),
    ato_capable: Boolean(input.ato_capable),
    ato_active: Boolean(input.ato_active),
    emergency_button: Boolean(input.emergency_button),
    emergency_cmd: Boolean(input.emergency_cmd),
    parking_apply: Boolean(input.parking_apply),
    parking_release: Boolean(input.parking_release),
    updated_at: input.updated_at ?? null,
    raw_data: input.raw_data ?? {},
  }
}

function normalizeAtoCommand(command) {
  return {
    vehicle_id: command.vehicle_id,
    line_id: command.line_id ?? 'LINE-1',
    control_mode: command.control_mode ?? 'ato',
    target_speed: command.target_speed ?? 0,
    target_position: command.target_position ?? null,
    traction_level: command.traction_level ?? 0,
    brake_level: command.brake_level ?? 0,
    reason: command.reason ?? null,
    updated_at: command.updated_at ?? null,
    raw_data: command.raw_data ?? {},
  }
}

function normalizeMaLimit(authority) {
  return {
    vehicle_id: authority.vehicle_id,
    position: authority.position ?? 0,
    route_id: authority.route_id ?? null,
    ma_limit: authority.ma_limit ?? authority.ma_end ?? null,
    distance_to_ma: authority.distance_to_ma ?? authority.distanceToMa ?? null,
    permission: authority.permission ?? 'unknown',
    signal_state: authority.signal_state ?? authority.state ?? 'unknown',
    speed_limit: authority.speed_limit ?? null,
    target_speed: authority.target_speed ?? null,
    reason: authority.reason ?? null,
    front_vehicle_id: authority.front_vehicle_id ?? null,
    front_train_length: authority.front_train_length ?? null,
    location_uncertainty: authority.location_uncertainty ?? null,
    communication_margin: authority.communication_margin ?? null,
    safety_margin: authority.safety_margin ?? null,
    front_protection_point: authority.front_protection_point ?? null,
    safe_distance: authority.safe_distance ?? null,
    current_speed: authority.current_speed ?? null,
    route_speed_limit: authority.route_speed_limit ?? null,
    required_stop_distance: authority.required_stop_distance ?? null,
    emergency_stop_distance: authority.emergency_stop_distance ?? null,
    warning_distance: authority.warning_distance ?? null,
    braking_curve_speed_limit: authority.braking_curve_speed_limit ?? null,
    braking_model: authority.braking_model ?? null,
    updated_at: authority.updated_at ?? null,
    raw_data: authority.raw_data ?? {},
  }
}

function normalizeRouteResult(result) {
  return {
    vehicle_id: result.vehicle_id ?? null,
    route_id: result.route_id ?? null,
    allowed: Boolean(result.allowed),
    reason: result.reason ?? null,
    required_switch_id: result.required_switch_id ?? null,
    required_position: result.required_position ?? null,
    current_position: result.current_position ?? null,
    locked_by_route_id: result.locked_by_route_id ?? null,
  }
}

function normalizeScenarioConfig(scenario) {
  const pageConfig = scenario?.page_config ?? {}
  return {
    scenario_id: scenario?.scenario_id ?? 'unknown',
    name: scenario?.name ?? scenario?.scenario_id ?? 'Unknown scenario',
    description: scenario?.description ?? '',
    page_config: {
      hero_panel: pageConfig.hero_panel ?? null,
      primary_chart: pageConfig.primary_chart ?? null,
      secondary_chart: pageConfig.secondary_chart ?? null,
      panels: pageConfig.panels ?? [],
      key_metrics: pageConfig.key_metrics ?? [],
      highlight_events: pageConfig.highlight_events ?? [],
    },
  }
}

function normalizeSceneStateItem(item) {
  if (!item) return null
  return {
    scenario_id: item.scenario_id ?? 'line_run',
    scope: item.scope ?? (item.vehicle_id || item.target_vehicle_id ? 'vehicle' : 'network'),
    vehicle_id: item.vehicle_id ?? item.target_vehicle_id ?? null,
    target_vehicle_id: item.target_vehicle_id ?? item.vehicle_id ?? null,
    summary: item.summary ?? '',
    reason: item.reason ?? null,
    key_metrics: item.key_metrics ?? [],
    highlight_events: item.highlight_events ?? [],
    updated_at: item.updated_at ?? null,
  }
}

function levelLabel(level) {
  if (level === 'critical') return '严重'
  if (level === 'warning') return '警告'
  if (level === 'info') return '信息'
  return level ?? '未知'
}

function sourceLabel(source) {
  const map = {
    ATP: 'ATP 安全防护',
    ATO: 'ATO 自动驾驶',
    SIGNAL: '信号系统',
    POWER: '供电系统',
    COMM: '通信系统',
    BACKEND: '后端服务',
  }
  return map[source] ?? source ?? '未知鏉ユ簮'
}

function deriveSystemMode(raw) {
  const systemMode = raw.system?.system_mode
  if (systemMode) return systemMode
  const status = raw.system?.status
  if (status === 'emergency' || status === 'degraded' || status === 'offline') return status
  return raw.system_mode ?? 'normal'
}

/** 对标误差 (cm)：优先用后端 stop_error_cm，否则前端估算 */
export function resolveStopErrorCm(vehicle) {
  if (!vehicle) return null
  if (vehicle.stop_error_cm != null) return Math.round(vehicle.stop_error_cm)
  if (vehicle.stop_distance == null) return null
  if (vehicle.speed > 5) return null
  if (vehicle.stop_distance > 30) return null
  return Math.round(vehicle.stop_distance * 10)
}

/** @deprecated 使用 resolveStopErrorCm */
export function estimateStopErrorCm(vehicle) {
  return resolveStopErrorCm(vehicle)
}

export function modeLabel(mode) {
  if (!mode) return '—'
  if (mode === 'ato') return 'ATO 自动'
  if (mode === 'manual') return '手动驾驶'
  if (mode === 'atp') return 'ATP 监督'
  if (mode === 'emergency') return '紧急'
  return mode
}

export function parkingPhaseLabel(phase) {
  const map = {
    cruising: '区间运行',
    approaching: '接近站台',
    braking: '减速制动',
    docking: '精准对标',
    stopped: '停稳',
  }
  return map[phase] ?? phase ?? '—'
}

export function isManualMode(mode) {
  return mode === 'manual'
}

export function isAutomatedParking(mode) {
  return mode === 'ato' || mode === 'atp'
}

