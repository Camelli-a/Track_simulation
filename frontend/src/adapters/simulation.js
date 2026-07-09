/** WebSocket 数据适配层：协议 v1.0 dashboard_snapshot + 旧版 tick 兼容 */

const SUPPORTED_TYPES = new Set(['dashboard_snapshot', 'tick'])

export function normalizeTick(raw) {
  if (!raw || !SUPPORTED_TYPES.has(raw.type)) return null
  if (raw.type === 'dashboard_snapshot') return normalizeDashboardSnapshot(raw)
  return normalizeLegacyTick(raw)
}

function normalizeDashboardSnapshot(raw) {
  return {
    type: 'dashboard_snapshot',
    protocol_version: raw.protocol_version ?? '1.0',
    timestamp: raw.timestamp ?? Date.now() / 1000,
    vehicles: (raw.trains ?? []).map(normalizeVehicle),
    track_segments: (raw.sections ?? []).map(normalizeSection),
    signals: (raw.signals ?? []).map(normalizeSignal),
    turnouts: (raw.switches ?? []).map(normalizeSwitch),
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
    vehicles: (raw.vehicles ?? raw.trains ?? []).map(normalizeVehicle),
    track_segments: (raw.track_segments ?? raw.sections ?? []).map(normalizeSection),
    signals: (raw.signals ?? []).map(normalizeSignal),
    turnouts: (raw.turnouts ?? raw.switches ?? []).map(normalizeSwitch),
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
    line_id: v.line_id ?? null,
    position: v.position ?? 0,
    speed: v.speed ?? 0,
    acceleration: v.acceleration ?? 0,
    mode,
    is_running: v.is_running ?? true,
    emergency_brake: Boolean(v.emergency_brake),
    ma_limit: v.ma_limit ?? v.ma_end ?? null,
    target_speed: v.target_speed ?? v.target_speed_limit ?? null,
    energy_kwh: v.energy_kwh ?? 0,
    stop_distance: v.stop_distance ?? null,
    station_name: v.station_name ?? null,
    parking_phase: v.parking_phase ?? deriveParkingPhase(v),
    stop_error_cm: v.stop_error_cm ?? null,
    platform_id: v.platform_id ?? null,
    updated_at: v.updated_at ?? null,
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
    start: s.start ?? 0,
    end: s.end ?? 0,
    occupied,
    aspect,
    condition: s.condition ?? 'normal',
    occupied_by: s.vehicle_id ?? s.occupied_by ?? null,
  }
}

function normalizeSignal(s) {
  return {
    signal_id: s.signal_id,
    position: s.position ?? 0,
    state: s.state ?? 'green',
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
    state: routing,
    locked: Boolean(sw.locked),
    related_section: sw.related_section ?? null,
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
  return map[source] ?? source ?? '未知来源'
}

function deriveSystemMode(raw) {
  const status = raw.system?.status
  if (status === 'emergency' || status === 'degraded') return status
  return raw.system_mode ?? 'normal'
}

/** 对标误差 (cm)：优先用 A 组 stop_error_cm，否则前端估算 */
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
    docking: '精确对标',
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
