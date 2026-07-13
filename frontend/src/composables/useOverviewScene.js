import { computed, watchEffect } from 'vue'
import { useSimulationStore } from '@/stores/simulation'
import { useUiStore } from '@/stores/ui'

const RECENT_EVENT_MS = 60_000

const METRIC_LABELS = {
  speed_kmh: '当前速度',
  target_speed_kmh: '目标速度',
  recommended_speed_kmh: '推荐速度',
  remaining_distance_m: '停车剩余距离',
  distance_to_ma_m: '距离 MA',
  ma_limit_m: 'MA 终点',
  stop_error_cm: '停车误差',
  signal_state: '信号状态',
  atp_triggered: 'ATP 介入',
  emergency_brake: '紧急制动',
  driver_brake_level: '司机制动级位',
  affected_vehicle_count: '受影响车辆',
  target_vehicle_id: '目标车辆',
  mode: '控制来源',
  driving_mode: '驾驶模式',
  current_section_id: '当前区段',
  permission: '运行许可',
  brake_level: '实际制动级位',
  traction_level: '实际牵引级位',
}

const EVENT_LABELS = {
  realtime_snapshot: '实时快照',
  ma_updated: 'MA 已更新',
  signal_state: '信号状态',
  ato_command: 'ATO 命令',
  atp_state: 'ATP 状态',
  door_state: '车门状态',
  route_denied: '进路未通过',
  alarm_event: '告警事件',
  stop_completed: '停车完成',
}

export function useOverviewScene() {
  const simulation = useSimulationStore()
  const ui = useUiStore()

  const recentEvents = computed(() => {
    const now = Date.now()
    return simulation.eventTimeline.filter((event) => now - Number(event.at ?? 0) <= RECENT_EVENT_MS)
  })

  const routeDenied = computed(() =>
    simulation.routeResults.find((result) => result && result.allowed === false) ?? null
  )

  const activeEmergencyVehicle = computed(() =>
    simulation.vehicles.find((vehicle) => vehicle.emergency_brake) ?? null
  )

  const firstRestrictedVehicle = computed(() =>
    simulation.vehicles.find((vehicle) =>
      vehicle.permission === 'stop'
      || vehicle.permission === 'restricted'
      || vehicle.signal_state === 'red'
      || vehicle.signal_state === 'yellow'
    ) ?? null
  )

  const firstStoppingVehicle = computed(() =>
    simulation.vehicles.find((vehicle) =>
      ['approaching', 'braking', 'docking', 'stopped'].includes(vehicle.parking_phase)
    ) ?? null
  )

  const primaryVehicle = computed(() =>
    simulation.selectedVehicle
    ?? activeEmergencyVehicle.value
    ?? firstRestrictedVehicle.value
    ?? firstStoppingVehicle.value
    ?? simulation.vehicles[0]
    ?? null
  )

  const affectedVehicles = computed(() =>
    simulation.vehicles
      .filter(isAffectedVehicle)
      .sort((a, b) => vehiclePriority(a) - vehiclePriority(b))
  )

  const focusedVehicleScene = computed(() => {
    const vehicle = simulation.selectedVehicle
    if (!vehicle) return null
    return buildVehicleScene(vehicle)
  })

  const globalScene = computed(() => {
    const backendActive = simulation.sceneState?.active_scene
    if (backendActive?.scenario_id) {
      return buildScene({
        code: backendActive.scenario_id,
        label: backendActive.name ?? backendActive.scenario_id,
        shortLabel: backendActive.name ?? backendActive.scenario_id,
        summary: backendActive.summary ?? '后端已给出当前场景状态。',
        source: 'backend_scene_state',
        targetVehicleId: backendActive.target_vehicle_id ?? backendActive.vehicle_id ?? primaryVehicle.value?.vehicle_id ?? null,
        keyMetrics: backendActive.key_metrics?.length ? backendActive.key_metrics : defaultMetricsForVehicle(primaryVehicle.value),
        highlightEvents: backendActive.highlight_events?.length ? backendActive.highlight_events : defaultEventKeys(),
      })
    }

    if (activeEmergencyVehicle.value) return buildVehicleScene(activeEmergencyVehicle.value, 'manual_overspeed_atp')
    if (routeDenied.value) {
      return buildScene({
        code: 'route_denied',
        label: '进路未通过',
        shortLabel: '进路约束',
        summary: `后端 route_result 显示进路 ${routeDenied.value.route_id ?? '未知'} 未通过。`,
        source: 'dashboard_snapshot.route_results',
        targetVehicleId: routeDenied.value.vehicle_id ?? primaryVehicle.value?.vehicle_id ?? null,
        keyMetrics: ['target_vehicle_id', 'affected_vehicle_count', 'permission', 'distance_to_ma_m'],
        highlightEvents: ['route_denied', 'ma_updated', 'signal_state'],
      })
    }
    if (firstRestrictedVehicle.value) return buildVehicleScene(firstRestrictedVehicle.value)
    if (firstStoppingVehicle.value) return buildVehicleScene(firstStoppingVehicle.value, 'normal_stop')

    return buildScene({
      code: 'line_run',
      label: '区间运行监视',
      shortLabel: primaryVehicle.value ? `运行监视 · ${primaryVehicle.value.vehicle_id}` : '运行监视',
      summary: simulation.vehicles.length
        ? '当前无停车、红灯、紧急制动等异常约束，页面展示后端实时车辆与线路状态。'
        : '后端暂未收到车辆状态，等待真实模块通过 ZMQ 发布 train_state。',
      source: 'dashboard_snapshot',
      targetVehicleId: primaryVehicle.value?.vehicle_id ?? null,
      keyMetrics: primaryVehicle.value
        ? ['speed_kmh', 'mode', 'driving_mode', 'current_section_id']
        : ['affected_vehicle_count'],
      highlightEvents: defaultEventKeys(),
    })
  })

  const activeOverviewScene = computed(() =>
    simulation.selectedVehicle ? (focusedVehicleScene.value ?? globalScene.value) : globalScene.value
  )

  const activeOverviewSceneMetricCards = computed(() =>
    activeOverviewScene.value.keyMetrics.map((metric) =>
      buildMetricCard(metric, sceneVehicle(activeOverviewScene.value), activeOverviewScene.value)
    )
  )

  const activeOverviewSceneEventCards = computed(() =>
    activeOverviewScene.value.highlightEvents.map((eventKey) =>
      buildSceneEventCard(eventKey, sceneVehicle(activeOverviewScene.value), activeOverviewScene.value)
    )
  )

  const globalSceneMetricCards = computed(() =>
    globalScene.value.keyMetrics.map((metric) =>
      buildMetricCard(metric, sceneVehicle(globalScene.value), globalScene.value)
    )
  )

  const globalSceneEventCards = computed(() =>
    globalScene.value.highlightEvents.map((eventKey) =>
      buildSceneEventCard(eventKey, sceneVehicle(globalScene.value), globalScene.value)
    )
  )

  const focusedVehicleSceneMetricCards = computed(() =>
    (focusedVehicleScene.value?.keyMetrics ?? []).map((metric) =>
      buildMetricCard(metric, simulation.selectedVehicle, focusedVehicleScene.value)
    )
  )

  const focusedVehicleSceneEventCards = computed(() =>
    (focusedVehicleScene.value?.highlightEvents ?? []).map((eventKey) =>
      buildSceneEventCard(eventKey, simulation.selectedVehicle, focusedVehicleScene.value)
    )
  )

  const activeOverviewSceneSourceLabel = computed(() => {
    const source = activeOverviewScene.value?.source
    if (source === 'backend_scene_state') return '来自后端场景状态'
    if (source?.startsWith('dashboard_snapshot')) return '来自后端实时快照'
    return '来自实时状态推导'
  })

  const activeOverviewSceneConfigLabel = computed(() => '指标与事件由当前后端状态实时生成')

  const scenarioCatalog = computed(() =>
    new Map((simulation.scenarios ?? []).map((scenario) => [scenario.scenario_id, scenario]))
  )

  watchEffect(() => {
    ui.setSceneLabel(globalScene.value.shortLabel)
  })

  return {
    globalScene,
    focusedVehicleScene,
    activeOverviewScene,
    activeOverviewSceneSourceLabel,
    activeOverviewSceneConfigLabel,
    affectedVehicles,
    globalSceneMetricCards,
    globalSceneEventCards,
    activeOverviewSceneMetricCards,
    activeOverviewSceneEventCards,
    focusedVehicleSceneMetricCards,
    focusedVehicleSceneEventCards,
    scenarioCatalog,
    alarms: computed(() => simulation.alarms),
    vehicles: computed(() => simulation.vehicles),
  }

  function buildVehicleScene(vehicle, forcedCode = null) {
    const code = forcedCode ?? inferVehicleSceneCode(vehicle)
    const label = sceneLabel(code)
    return buildScene({
      code,
      label,
      shortLabel: `${label} · ${vehicle.vehicle_id}`,
      summary: vehicleSummary(vehicle),
      source: 'dashboard_snapshot.trains',
      targetVehicleId: vehicle.vehicle_id,
      keyMetrics: defaultMetricsForVehicle(vehicle, code),
      highlightEvents: defaultEventKeys(vehicle, code),
    })
  }

  function buildScene({
    code,
    label,
    shortLabel,
    summary,
    source,
    targetVehicleId = null,
    keyMetrics = [],
    highlightEvents = [],
  }) {
    return {
      code,
      scenario_id: code,
      label,
      shortLabel,
      summary,
      source,
      scope: targetVehicleId ? 'vehicle' : 'network',
      targetVehicleId,
      keyMetrics,
      highlightEvents,
    }
  }

  function sceneVehicle(scene) {
    if (scene?.targetVehicleId) {
      return simulation.vehicles.find((vehicle) => vehicle.vehicle_id === scene.targetVehicleId) ?? null
    }
    return primaryVehicle.value
  }

  function inferVehicleSceneCode(vehicle) {
    if (vehicle.emergency_brake) return 'atp_intervention'
    if (vehicle.permission === 'stop' || vehicle.signal_state === 'red') return 'red_signal_stop'
    if (vehicle.permission === 'restricted' || vehicle.signal_state === 'yellow') return 'ma_restricted'
    if (['approaching', 'braking', 'docking', 'stopped'].includes(vehicle.parking_phase)) return 'normal_stop'
    return 'line_run'
  }

  function sceneLabel(code) {
    return {
      atp_intervention: 'ATP 介入',
      red_signal_stop: '红灯/停车约束',
      ma_restricted: 'MA 受限运行',
      normal_stop: '进站停车',
      route_denied: '进路约束',
      line_run: '区间运行监视',
    }[code] ?? code
  }

  function defaultMetricsForVehicle(vehicle, code = 'line_run') {
    if (!vehicle) return ['affected_vehicle_count']
    if (code === 'atp_intervention') {
      return ['speed_kmh', 'distance_to_ma_m', 'emergency_brake', 'brake_level']
    }
    if (code === 'red_signal_stop' || code === 'ma_restricted') {
      return ['speed_kmh', 'signal_state', 'permission', 'distance_to_ma_m']
    }
    if (code === 'normal_stop') {
      return ['speed_kmh', 'target_speed_kmh', 'remaining_distance_m', 'stop_error_cm']
    }
    return ['speed_kmh', 'mode', 'driving_mode', 'current_section_id']
  }

  function defaultEventKeys(vehicle = null, code = null) {
    if (!vehicle) return ['realtime_snapshot', 'ma_updated', 'signal_state']
    if (code === 'atp_intervention') return ['atp_state', 'ma_updated', 'alarm_event']
    if (code === 'red_signal_stop' || code === 'ma_restricted') return ['signal_state', 'ma_updated', 'ato_command']
    if (code === 'normal_stop') return ['realtime_snapshot', 'ato_command', 'stop_completed']
    return ['realtime_snapshot', 'ma_updated', 'signal_state']
  }

  function buildMetricCard(metric, vehicle, scene) {
    const label = METRIC_LABELS[metric] ?? metric
    const sourceLabel = metricSource(metric)
    const value = metricValue(metric, vehicle, scene)
    const hint = metricHint(metric, vehicle)
    return { key: metric, label, value, hint, sourceLabel }
  }

  function metricValue(metric, vehicle, scene) {
    if (metric === 'affected_vehicle_count') return `${affectedVehicles.value.length} 列`
    if (metric === 'target_vehicle_id') return scene?.targetVehicleId ?? vehicle?.vehicle_id ?? '—'
    if (!vehicle) return '—'

    if (metric === 'speed_kmh') return `${round(vehicle.speed)} km/h`
    if (metric === 'target_speed_kmh') return formatKmh(vehicle.target_speed)
    if (metric === 'recommended_speed_kmh') return formatKmh(vehicle.ma_braking_curve_speed_limit ?? vehicle.target_speed)
    if (metric === 'remaining_distance_m') return formatMeters(vehicle.stop_distance)
    if (metric === 'distance_to_ma_m') return formatMeters(vehicle.distance_to_ma)
    if (metric === 'ma_limit_m') return formatMeters(vehicle.ma_limit)
    if (metric === 'stop_error_cm') return vehicle.stop_error_cm == null ? '—' : `${round(vehicle.stop_error_cm)} cm`
    if (metric === 'signal_state') return signalLabel(vehicle.signal_state)
    if (metric === 'permission') return permissionLabel(vehicle.permission)
    if (metric === 'atp_triggered') return vehicle.emergency_brake || vehicle.atp_intervention ? '已介入' : '未介入'
    if (metric === 'emergency_brake') return vehicle.emergency_brake ? '已施加' : '未施加'
    if (metric === 'driver_brake_level') {
      const input = simulation.driverInputs.find((item) => item.vehicle_id === vehicle.vehicle_id)
      return input ? `B${input.brake_level ?? 0}` : '—'
    }
    if (metric === 'mode') return vehicle.mode ?? vehicle.control_source ?? '—'
    if (metric === 'driving_mode') return vehicle.driving_mode ?? '—'
    if (metric === 'current_section_id') return vehicle.section_id ?? '—'
    if (metric === 'brake_level') return vehicle.brake_level == null ? '—' : `B${vehicle.brake_level}`
    if (metric === 'traction_level') return vehicle.traction_level == null ? '—' : `T${vehicle.traction_level}`
    return '—'
  }

  function metricSource(metric) {
    if (['signal_state', 'permission', 'distance_to_ma_m', 'ma_limit_m', 'recommended_speed_kmh'].includes(metric)) {
      return '后端 MA/信号'
    }
    if (metric === 'driver_brake_level') return '司机台输入'
    if (metric === 'affected_vehicle_count') return '后端车辆聚合'
    return '后端车辆状态'
  }

  function metricHint(metric, vehicle) {
    if (!vehicle && metric !== 'affected_vehicle_count') return '当前没有可用目标车辆。'
    return {
      speed_kmh: '来自 train_state.speed，前端仅做单位展示。',
      target_speed_kmh: '来自后端 MA/ATO 目标速度字段。',
      recommended_speed_kmh: '优先使用制动曲线限速，其次使用 target_speed。',
      remaining_distance_m: '来自车辆停车阶段状态中的 stop_distance。',
      distance_to_ma_m: '来自 ma_state.distance_to_ma。',
      ma_limit_m: '来自 ma_state.ma_limit。',
      stop_error_cm: '来自车辆停车结果 stop_error_cm。',
      signal_state: '来自信号模块发布的 signal_state/ma_state。',
      permission: '来自 MA 许可状态 allow/restricted/stop。',
      atp_triggered: '来自 train_state/atp_state 的 ATP 或紧急制动字段。',
      emergency_brake: '来自 train_state.emergency_brake。',
      driver_brake_level: '来自 driver_input.brake_level。',
      affected_vehicle_count: '统计当前被 MA、信号、停车或 ATP 影响的车辆。',
      mode: '来自 train_state.mode。',
      driving_mode: '来自 train_state.driving_mode。',
      current_section_id: '来自 train_state.section_id。',
      brake_level: '来自车辆最终实际施加制动级位。',
      traction_level: '来自车辆最终实际施加牵引级位。',
    }[metric] ?? '来自后端实时 dashboard_snapshot。'
  }

  function buildSceneEventCard(eventKey, vehicle, scene) {
    const event = eventFromBackend(eventKey, vehicle, scene)
    return {
      key: eventKey,
      label: EVENT_LABELS[eventKey] ?? eventKey,
      matched: Boolean(event),
      title: event?.title ?? '后端暂无该事件',
      detail: event?.detail ?? '当前实时快照未体现该事件条件。',
      atLabel: event?.at ? formatEventTime(event.at) : '—',
      level: event?.level ?? 'info',
      sourceLabel: event?.sourceLabel ?? '后端实时快照',
    }
  }

  function eventFromBackend(eventKey, vehicle, scene) {
    const now = Date.now()
    const eventMatch = findRecentEvent(eventKey, vehicle)
    if (eventMatch) return eventMatch

    if (eventKey === 'realtime_snapshot') {
      return {
        title: '已收到后端实时快照',
        detail: `车辆 ${simulation.vehicles.length} 列，区段 ${simulation.trackSegments.length} 个，信号 ${simulation.signals.length} 个，道岔 ${simulation.turnouts.length} 个。`,
        at: simulation.lastTickAt || now,
        level: 'info',
        sourceLabel: 'dashboard_snapshot',
      }
    }
    if (eventKey === 'ma_updated' && vehicle?.ma_limit != null) {
      return {
        title: `${vehicle.vehicle_id} MA 已更新`,
        detail: `MA 终点 ${round(vehicle.ma_limit)} m，剩余 ${formatMeters(vehicle.distance_to_ma)}，许可 ${permissionLabel(vehicle.permission)}。`,
        at: toMs(vehicle.updated_at) ?? simulation.lastTickAt ?? now,
        level: vehicle.permission === 'stop' ? 'warn' : 'info',
        sourceLabel: 'ma_state',
      }
    }
    if (eventKey === 'signal_state' && vehicle) {
      return {
        title: `${vehicle.vehicle_id} 信号状态 ${signalLabel(vehicle.signal_state)}`,
        detail: `当前许可 ${permissionLabel(vehicle.permission)}，限速 ${formatKmh(vehicle.speed_limit)}。`,
        at: toMs(vehicle.updated_at) ?? simulation.lastTickAt ?? now,
        level: vehicle.signal_state === 'red' ? 'warn' : 'info',
        sourceLabel: 'signal_state / ma_state',
      }
    }
    if (eventKey === 'ato_command' && vehicle) {
      const command = simulation.atoCommands.find((item) => item.vehicle_id === vehicle.vehicle_id)
      if (!command) return null
      return {
        title: `${vehicle.vehicle_id} 已收到 ATO 命令`,
        detail: `目标速度 ${formatKmh(command.target_speed)}，牵引 ${command.traction_level ?? 0}，制动 ${command.brake_level ?? 0}，原因 ${command.reason ?? '—'}。`,
        at: toMs(command.updated_at) ?? now,
        level: command.brake_level > 0 ? 'warn' : 'info',
        sourceLabel: 'ato_command',
      }
    }
    if (eventKey === 'atp_state' && vehicle) {
      return {
        title: vehicle.emergency_brake || vehicle.atp_intervention ? `${vehicle.vehicle_id} ATP 已介入` : `${vehicle.vehicle_id} ATP 正常监督`,
        detail: `紧急制动 ${vehicle.emergency_brake ? '已施加' : '未施加'}，距离 MA ${formatMeters(vehicle.distance_to_ma)}。`,
        at: toMs(vehicle.updated_at) ?? now,
        level: vehicle.emergency_brake ? 'error' : 'info',
        sourceLabel: 'atp_state / train_state',
      }
    }
    if (eventKey === 'door_state' && vehicle) {
      return {
        title: `${vehicle.vehicle_id} 车门状态已同步`,
        detail: `车门模式 ${vehicle.door_mode ?? '—'}，关门灯 ${vehicle.door_closed_light ? '亮' : '未亮'}。`,
        at: toMs(vehicle.updated_at) ?? now,
        level: vehicle.door_closed_light === false ? 'warn' : 'info',
        sourceLabel: 'door_state / train_state',
      }
    }
    if (eventKey === 'route_denied' && routeDenied.value) {
      return {
        title: `进路 ${routeDenied.value.route_id ?? '未知'} 未通过`,
        detail: routeDenied.value.reason ?? '后端 route_result 返回 allowed=false。',
        at: now,
        level: 'warn',
        sourceLabel: 'route_result',
      }
    }
    if (eventKey === 'alarm_event' && simulation.alarms.length) {
      const alarm = simulation.alarms[0]
      return {
        title: alarm.title ?? alarm.message ?? '收到告警',
        detail: alarm.message ?? alarm.detail ?? '后端 alarm_event 已进入 dashboard。',
        at: toMs(alarm.timestamp) ?? now,
        level: alarm.level === 'critical' ? 'error' : 'warn',
        sourceLabel: 'alarm_event',
      }
    }
    if (eventKey === 'stop_completed' && vehicle?.parking_phase === 'stopped') {
      return {
        title: `${vehicle.vehicle_id} 已停稳`,
        detail: `停车误差 ${metricValue('stop_error_cm', vehicle, scene)}。`,
        at: toMs(vehicle.updated_at) ?? now,
        level: 'info',
        sourceLabel: 'train_state',
      }
    }
    return null
  }

  function findRecentEvent(eventKey, vehicle) {
    const keyword = EVENT_LABELS[eventKey]
    if (!keyword) return null
    const matched = recentEvents.value.find((event) => {
      const sameVehicle = !vehicle || !event.vehicleId || event.vehicleId === vehicle.vehicle_id
      return sameVehicle && (`${event.title ?? ''}${event.detail ?? ''}`).includes(keyword)
    })
    if (!matched) return null
    return {
      title: matched.title,
      detail: matched.detail,
      at: matched.at,
      level: matched.level,
      sourceLabel: matched.source ?? '前端事件时间线',
    }
  }
}

function isAffectedVehicle(vehicle) {
  return Boolean(
    vehicle.emergency_brake
    || vehicle.atp_intervention
    || vehicle.permission === 'stop'
    || vehicle.permission === 'restricted'
    || vehicle.signal_state === 'red'
    || vehicle.signal_state === 'yellow'
    || ['braking', 'docking', 'stopped'].includes(vehicle.parking_phase)
    || (vehicle.distance_to_ma != null && vehicle.distance_to_ma < 120)
  )
}

function vehiclePriority(vehicle) {
  if (vehicle.emergency_brake || vehicle.atp_intervention) return 0
  if (vehicle.permission === 'stop' || vehicle.signal_state === 'red') return 1
  if (vehicle.permission === 'restricted' || vehicle.signal_state === 'yellow') return 2
  if (['braking', 'docking', 'stopped'].includes(vehicle.parking_phase)) return 3
  return 4
}

function vehicleSummary(vehicle) {
  if (vehicle.emergency_brake) return `${vehicle.vehicle_id} 已触发 ATP/紧急制动，当前以安全制动状态为准。`
  if (vehicle.permission === 'stop') return `${vehicle.vehicle_id} 当前 MA 许可为停车，需观察制动与停车结果。`
  if (vehicle.permission === 'restricted') return `${vehicle.vehicle_id} 当前受 MA 限制运行。`
  if (vehicle.signal_state === 'red') return `${vehicle.vehicle_id} 前方信号为红灯。`
  if (vehicle.signal_state === 'yellow') return `${vehicle.vehicle_id} 前方信号为黄灯限速。`
  return `${vehicle.vehicle_id} 当前状态来自后端实时 train_state/ma_state/signal_state。`
}

function round(value) {
  const number = Number(value)
  return Number.isFinite(number) ? Math.round(number) : 0
}

function formatKmh(value) {
  return value == null || !Number.isFinite(Number(value)) ? '—' : `${round(value)} km/h`
}

function formatMeters(value) {
  return value == null || !Number.isFinite(Number(value)) ? '—' : `${Math.max(0, Number(value)).toFixed(1)} m`
}

function signalLabel(state) {
  if (state === 'red') return '红灯'
  if (state === 'yellow') return '黄灯'
  if (state === 'green') return '绿灯'
  return state ?? '—'
}

function permissionLabel(permission) {
  if (permission === 'allow') return '允许'
  if (permission === 'restricted') return '受限'
  if (permission === 'stop') return '停车'
  return permission ?? '—'
}

function toMs(value) {
  if (value == null) return null
  const number = Number(value)
  if (!Number.isFinite(number)) return null
  return number > 1e12 ? number : number * 1000
}

function formatEventTime(at) {
  return new Date(Number(at)).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
