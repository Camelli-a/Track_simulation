/** REST /signal/status 响应 → 与 WebSocket 动态层兼容的结构 */
export function normalizeSignalStatus(raw) {
  if (!raw) return null
  return {
    timestamp: raw.timestamp,
    system_mode: raw.system_mode ?? 'normal',
    signals: (raw.lights ?? raw.signals ?? []).map(normalizeSignalLight),
    sections: (raw.sections ?? []).map(normalizeSignalSection),
    switches: (raw.switches ?? []).map(normalizeSignalSwitch),
    ma_limits: raw.ma_limits ?? [],
    route_results: raw.route_results ?? [],
  }
}

export function normalizeSignalLight(s) {
  return {
    signal_id: s.signal_id,
    position: s.position ?? 0,
    state: s.state ?? s.signal_state ?? 'green',
  }
}

export function normalizeSignalSection(s) {
  const occupied = Boolean(s.occupied)
  return {
    segment_id: s.section_id,
    section_id: s.section_id,
    start: s.start ?? 0,
    end: s.end ?? 0,
    occupied,
    aspect: s.aspect ?? (occupied ? 'red' : 'green'),
    condition: s.condition ?? 'normal',
    occupied_by: s.vehicle_id ?? null,
  }
}

export function normalizeSignalSwitch(sw) {
  return {
    turnout_id: sw.switch_id ?? sw.turnout_id,
    switch_id: sw.switch_id ?? sw.turnout_id,
    state: sw.routing ?? sw.position ?? sw.state ?? 'normal',
    locked: Boolean(sw.locked),
    related_section: sw.related_section ?? null,
  }
}
