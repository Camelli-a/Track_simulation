/** REST /signal/status 响应 → 与 WebSocket 动态层兼容的结构 */
export function normalizeSignalStatus(raw) {
  if (!raw) return null
  return {
    timestamp: raw.timestamp,
    system_mode: raw.system_mode ?? 'normal',
    signals: (raw.lights ?? raw.signals ?? []).map(normalizeSignalLight),
    sections: (raw.sections ?? []).map(normalizeSignalSection),
    switches: (raw.switches ?? []).map(normalizeSignalSwitch),
    ma_limits: (raw.ma_limits ?? []).map(normalizeMaLimit),
    route_results: (raw.route_results ?? []).map(normalizeRouteResult),
  }
}

export function normalizeSignalLight(signal) {
  const state = signal.state ?? signal.signal_state ?? 'green'
  return {
    signal_id: signal.signal_id,
    position: signal.position ?? 0,
    state,
    signal_state: signal.signal_state ?? state,
    route_id: signal.route_id ?? null,
    permission: signal.permission ?? null,
  }
}

export function normalizeSignalSection(section) {
  const occupied = Boolean(section.occupied)
  return {
    segment_id: section.section_id,
    section_id: section.section_id,
    line_id: section.line_id ?? null,
    track_seg_id: section.track_seg_id ?? null,
    start: section.start ?? 0,
    end: section.end ?? 0,
    gradient: section.gradient ?? null,
    speed_limit: section.speed_limit ?? null,
    station_id: section.station_id ?? null,
    stop_position: section.stop_position ?? null,
    occupied,
    aspect: section.aspect ?? (occupied ? 'red' : 'green'),
    condition: section.condition ?? 'normal',
    occupied_by: section.vehicle_id ?? null,
    locked: Boolean(section.locked),
    locked_by_route_id: section.locked_by_route_id ?? null,
  }
}

export function normalizeSignalSwitch(turnout) {
  return {
    turnout_id: turnout.switch_id ?? turnout.turnout_id,
    switch_id: turnout.switch_id ?? turnout.turnout_id,
    position: turnout.position ?? 'unknown',
    routing: turnout.routing ?? turnout.position ?? turnout.state ?? 'normal',
    state: turnout.routing ?? turnout.position ?? turnout.state ?? 'normal',
    locked: Boolean(turnout.locked),
    related_section: turnout.related_section ?? null,
    locked_by_route_id: turnout.locked_by_route_id ?? null,
    reason: turnout.reason ?? null,
  }
}

function normalizeMaLimit(authority) {
  return {
    vehicle_id: authority.vehicle_id,
    position: authority.position ?? 0,
    route_id: authority.route_id ?? null,
    ma_limit: authority.ma_limit ?? authority.ma_end ?? null,
    distance_to_ma: authority.distance_to_ma ?? authority.distanceToMa ?? null,
    permission: authority.permission ?? null,
    signal_state: authority.signal_state ?? authority.state ?? null,
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
