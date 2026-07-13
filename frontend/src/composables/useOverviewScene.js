import { computed, watchEffect } from 'vue'
import { useSimulationStore } from '@/stores/simulation'
import { useUiStore } from '@/stores/ui'

const RECENT_EVENT_MS = 45000
const METRIC_LABELS = {
  speed_kmh: '当前速度',
  target_speed_kmh: '目标速度',
  recommended_speed_kmh: '推荐速度',
  remaining_distance_m: '剩余距离',
  distance_to_ma_m: '距离 MA',
  ma_limit_m: 'MA 边界',
  old_ma_limit_m: '原始 MA',
  new_ma_limit_m: '新 MA',
  stop_error_cm: '停车误差',
  signal_state: '信号状态',
  atp_triggered: 'ATP 状态',
  emergency_brake: '紧急制动',
  driver_brake_level: '司机制动级位',
  blocked_section_id: '封锁对象',
  affected_vehicle_count: '受影响车辆',
  target_vehicle_id: '目标车辆',
  mode: '当前模式',
  current_section_id: '当前区段',
}

const EVENT_LABELS = {
  approach_started: '开始接近站台',
  service_brake_started: '常用制动开始',
  stop_completed: '列车停稳',
  signal_red: '前方红灯',
  ma_updated: 'MA 更新',
  brake_command_sent: '制动命令下发',
  ma_shrink: 'MA 收缩',
  recommended_speed_drop: '推荐速度下降',
  atp_warning: 'ATP 预警',
  atp_triggered: 'ATP 触发',
  emergency_brake_applied: '紧急制动施加',
  section_blocked: '区段封锁',
  route_denied: '进路拒绝',
  driver_no_response: '司机未及时响应',
}

const SCENARIO_DISPLAY = {
  normal_stop: {
    label: '正常进站停车',
    shortLabel: '正常停车',
    summary: '列车按正常进站停车流程运行，可继续观察对标与停车误差。',
  },
  red_signal_stop: {
    label: '前方红灯停车',
    shortLabel: '红灯停车',
    summary: '前方信号变为停车，列车应在授权边界前安全制动并停住。',
  },
  ma_shrink: {
    label: 'MA 突然缩短',
    shortLabel: 'MA 收缩',
    summary: '运行中的移动授权发生收缩，重点观察剩余授权距离与制动响应。',
  },
  section_block_stop: {
    label: '进路 / 区段约束停车',
    shortLabel: '进路受阻',
    summary: '区段或进路条件不满足，列车需要等待或执行约束停车。',
  },
  manual_overspeed_atp: {
    label: 'ATP 介入停车',
    shortLabel: 'ATP 介入',
    summary: '司机未按推荐速度控制或车辆超出安全包络，ATP 触发保护制动。',
  },
  external_event_stop: {
    label: '外部事件约束停车',
    shortLabel: '外部约束',
    summary: '外部扰动更新了信号或 MA 约束，列车需按新的边界安全停车。',
  },
  line_run: {
    label: '区间运行监视',
    shortLabel: '区间运行',
    summary: '当前全线没有明显异常或停车事件，重点观察线路运行与数据接入状态。',
  },
}

export function useOverviewScene() {
  const simulation = useSimulationStore()
  const ui = useUiStore()

  const scenarioCatalog = computed(() =>
    new Map((simulation.scenarios ?? []).map((scenario) => [scenario.scenario_id, scenario]))
  )
  const backendSceneState = computed(() => simulation.sceneState ?? null)
  const backendVehicleSceneMap = computed(() =>
    new Map(
      (backendSceneState.value?.vehicle_scene_map ?? [])
        .filter(Boolean)
        .map((scene) => [scene.vehicle_id ?? scene.target_vehicle_id, scene]),
    )
  )

  function buildScene({
    code,
    label,
    shortLabel,
    scope,
    targetVehicleId = null,
    summary,
    reason = null,
    source = 'frontend_fallback',
    keyMetrics = [],
    highlightEvents = [],
  }) {
    const backendScenario = scenarioCatalog.value.get(code) ?? null
    const display = SCENARIO_DISPLAY[code] ?? {}
    const pageConfig = backendScenario?.page_config ?? {}

    return {
      code,
      scenario_id: backendScenario?.scenario_id ?? code,
      label: display.label ?? label ?? backendScenario?.name ?? code,
      shortLabel: shortLabel
        ? shortLabel
        : (display.shortLabel && targetVehicleId ? `${display.shortLabel} · ${targetVehicleId}` : (display.shortLabel ?? label ?? code)),
      scope,
      targetVehicleId,
      summary: summary
        ?? display.summary
        ?? backendScenario?.description
        ?? '',
      backendName: backendScenario?.name ?? null,
      backendDescription: backendScenario?.description ?? null,
      reason,
      source,
      pageConfig,
      keyMetrics: pageConfig.key_metrics?.length ? pageConfig.key_metrics : keyMetrics,
      highlightEvents: pageConfig.highlight_events?.length ? pageConfig.highlight_events : highlightEvents,
    }
  }

  function sceneFromBackendState(sceneStateItem) {
    if (!sceneStateItem?.scenario_id) return null
    const targetVehicleId = sceneStateItem.target_vehicle_id ?? sceneStateItem.vehicle_id ?? null
    return buildScene({
      code: sceneStateItem.scenario_id,
      scope: sceneStateItem.scope ?? (targetVehicleId ? 'vehicle' : 'network'),
      targetVehicleId,
      summary: sceneStateItem.summary ?? null,
      reason: sceneStateItem.reason ?? null,
      source: 'backend_scene_state',
      keyMetrics: sceneStateItem.key_metrics ?? [],
      highlightEvents: sceneStateItem.highlight_events ?? [],
    })
  }

  const recentEvents = computed(() => {
    const now = Date.now()
    return simulation.eventTimeline.filter((event) => now - Number(event.at ?? 0) <= RECENT_EVENT_MS)
  })

  const recentMaShrinkEvent = computed(() =>
    recentEvents.value.find((event) => event.title?.includes('MA 收缩')) ?? null
  )

  const recentAtpEvent = computed(() =>
    recentEvents.value.find((event) =>
      event.title?.includes('ATP')
      || event.title?.includes('紧急制动')
      || event.type === 'alarm' && event.source === 'ALARM'
    ) ?? null
  )

  const activeEmergencyVehicle = computed(() =>
    simulation.vehicles.find((vehicle) => vehicle.emergency_brake) ?? null
  )

  const blockedRoute = computed(() =>
    simulation.routeResults.find((result) => !result.allowed) ?? null
  )

  const redSignalVehicle = computed(() =>
    simulation.vehicles.find((vehicle) => vehicle.permission === 'stop' && vehicle.signal_state === 'red') ?? null
  )

  const approachingVehicle = computed(() =>
    simulation.selectedVehicle
    ?? simulation.vehicles.find((vehicle) => ['approaching', 'braking', 'docking', 'stopped'].includes(vehicle.parking_phase))
    ?? simulation.vehicles[0]
    ?? null
  )

  const focusedVehicleScene = computed(() => {
    const vehicle = simulation.selectedVehicle
    if (!vehicle) return null

    const backendFocused = sceneFromBackendState(
      backendVehicleSceneMap.value.get(vehicle.vehicle_id),
    )
    if (backendFocused) return backendFocused

    if (vehicle.emergency_brake) {
      return buildScene({
        code: 'manual_overspeed_atp',
        shortLabel: `ATP 介入 · ${vehicle.vehicle_id}`,
        scope: 'vehicle',
        targetVehicleId: vehicle.vehicle_id,
        summary: `${vehicle.vehicle_id} 已进入紧急制动，当前重点是确认 ATP 触发原因和停车结果。`,
        keyMetrics: ['speed_kmh', 'distance_to_ma_m', 'emergency_brake', 'atp_triggered'],
        highlightEvents: ['atp_triggered', 'emergency_brake_applied'],
      })
    }

    const hasRecentShrink = recentMaShrinkEvent.value?.vehicleId === vehicle.vehicle_id
    if (hasRecentShrink) {
      return buildScene({
        code: 'ma_shrink',
        shortLabel: `MA 收缩 · ${vehicle.vehicle_id}`,
        scope: 'vehicle',
        targetVehicleId: vehicle.vehicle_id,
        summary: `${vehicle.vehicle_id} 最近发生过 MA 收缩，需重点观察剩余授权距离和制动响应。`,
        keyMetrics: ['old_ma_limit_m', 'new_ma_limit_m', 'distance_to_ma_m', 'atp_triggered'],
        highlightEvents: ['ma_shrink', 'recommended_speed_drop', 'atp_warning'],
      })
    }

    if (vehicle.permission === 'stop' && vehicle.signal_state === 'red') {
      return buildScene({
        code: 'red_signal_stop',
        shortLabel: `红灯停车 · ${vehicle.vehicle_id}`,
        scope: 'vehicle',
        targetVehicleId: vehicle.vehicle_id,
        summary: `${vehicle.vehicle_id} 当前受前方红灯约束，正在等待或执行停车。`,
        keyMetrics: ['signal_state', 'ma_limit_m', 'distance_to_ma_m', 'recommended_speed_kmh'],
        highlightEvents: ['signal_red', 'ma_updated', 'brake_command_sent'],
      })
    }

    if (['approaching', 'braking', 'docking', 'stopped'].includes(vehicle.parking_phase)) {
      return buildScene({
        code: 'normal_stop',
        shortLabel: `正常停车 · ${vehicle.vehicle_id}`,
        scope: 'vehicle',
        targetVehicleId: vehicle.vehicle_id,
        summary: `${vehicle.vehicle_id} 正在按正常停车流程运行，可继续观察对标与停车误差。`,
        keyMetrics: ['speed_kmh', 'target_speed_kmh', 'remaining_distance_m', 'stop_error_cm'],
        highlightEvents: ['approach_started', 'service_brake_started', 'stop_completed'],
      })
    }

    return buildScene({
      code: 'line_run',
      shortLabel: `区间运行 · ${vehicle.vehicle_id}`,
      scope: 'vehicle',
      targetVehicleId: vehicle.vehicle_id,
      summary: `${vehicle.vehicle_id} 当前处于区间运行阶段，暂未进入重点停车场景。`,
      keyMetrics: ['speed_kmh', 'mode', 'current_section_id'],
      highlightEvents: [],
    })
  })

  const globalScene = computed(() => {
    const backendGlobal = sceneFromBackendState(backendSceneState.value?.active_scene)
    if (backendGlobal) return backendGlobal

    if (activeEmergencyVehicle.value) {
      return buildScene({
        code: 'manual_overspeed_atp',
        shortLabel: `ATP 介入 · ${activeEmergencyVehicle.value.vehicle_id}`,
        scope: 'vehicle',
        targetVehicleId: activeEmergencyVehicle.value.vehicle_id,
        summary: `${activeEmergencyVehicle.value.vehicle_id} 已进入紧急制动，系统当前处于安全保底优先态。`,
        keyMetrics: ['speed_kmh', 'recommended_speed_kmh', 'driver_brake_level', 'atp_triggered'],
        highlightEvents: ['driver_no_response', 'atp_triggered', 'emergency_brake_applied'],
      })
    }

    if (recentMaShrinkEvent.value) {
      return buildScene({
        code: 'ma_shrink',
        shortLabel: `MA 收缩 · ${recentMaShrinkEvent.value.vehicleId ?? '重点列车'}`,
        scope: recentMaShrinkEvent.value.vehicleId ? 'vehicle' : 'network',
        targetVehicleId: recentMaShrinkEvent.value.vehicleId ?? null,
        summary: recentMaShrinkEvent.value.detail ?? '最近发生过 MA 收缩，建议继续核对授权边界和列车响应。',
        keyMetrics: ['old_ma_limit_m', 'new_ma_limit_m', 'distance_to_ma_m', 'atp_triggered'],
        highlightEvents: ['ma_shrink', 'recommended_speed_drop', 'atp_warning', 'atp_triggered'],
      })
    }

    if (blockedRoute.value) {
      return buildScene({
        code: 'section_block_stop',
        shortLabel: '进路受阻',
        scope: blockedRoute.value.vehicle_id ? 'vehicle' : 'network',
        targetVehicleId: blockedRoute.value.vehicle_id ?? null,
        summary: blockedRoute.value.reason
          ? `当前存在未通过进路申请，原因为 ${blockedRoute.value.reason}。`
          : '当前存在未通过进路申请，系统处于约束停车或等待进路状态。',
        keyMetrics: ['blocked_section_id', 'affected_vehicle_count', 'target_vehicle_id', 'remaining_distance_m'],
        highlightEvents: ['route_denied', 'section_blocked', 'ma_updated'],
      })
    }

    if (redSignalVehicle.value) {
      return buildScene({
        code: 'red_signal_stop',
        shortLabel: `红灯停车 · ${redSignalVehicle.value.vehicle_id}`,
        scope: 'vehicle',
        targetVehicleId: redSignalVehicle.value.vehicle_id,
        summary: `${redSignalVehicle.value.vehicle_id} 当前受红灯约束，停车或等待放行是全线主要关注点。`,
        keyMetrics: ['signal_state', 'ma_limit_m', 'distance_to_ma_m', 'recommended_speed_kmh'],
        highlightEvents: ['signal_red', 'ma_updated', 'brake_command_sent', 'stop_completed'],
      })
    }

    if (approachingVehicle.value) {
      return buildScene({
        code: 'normal_stop',
        shortLabel: `正常停车 · ${approachingVehicle.value.vehicle_id}`,
        scope: 'vehicle',
        targetVehicleId: approachingVehicle.value.vehicle_id,
        summary: `${approachingVehicle.value.vehicle_id} 正在按正常进站停车流程运行，可作为当前主展示车辆。`,
        keyMetrics: ['speed_kmh', 'target_speed_kmh', 'remaining_distance_m', 'stop_error_cm'],
        highlightEvents: ['approach_started', 'service_brake_started', 'stop_completed'],
      })
    }

    return buildScene({
      code: 'line_run',
      shortLabel: '区间运行',
      scope: 'network',
      targetVehicleId: null,
      summary: '当前全线没有明显异常或停车事件，重点观察线路运行与数据接入状态。',
      keyMetrics: ['affected_vehicle_count'],
      highlightEvents: [],
    })
  })

  const affectedVehicles = computed(() =>
    simulation.vehicles.filter((vehicle) =>
      vehicle.emergency_brake
      || vehicle.permission === 'stop'
      || vehicle.permission === 'restricted'
      || ['braking', 'docking', 'stopped'].includes(vehicle.parking_phase)
    )
  )

  const sceneVehicle = computed(() => {
    const targetId = globalScene.value.targetVehicleId
    if (targetId) {
      return simulation.vehicles.find((vehicle) => vehicle.vehicle_id === targetId) ?? null
    }
    return simulation.selectedVehicle ?? approachingVehicle.value ?? null
  })

  const maShrinkAmount = computed(() => {
    const match = recentMaShrinkEvent.value?.title?.match(/MA 收缩\s+(\d+)/)
    return match ? Number(match[1]) : null
  })

  const globalSceneMetricCards = computed(() =>
    globalScene.value.keyMetrics.map((metric) => buildMetricCard(metric))
  )

  const globalSceneEventCards = computed(() =>
    globalScene.value.highlightEvents.map((eventKey) => buildSceneEventCard(eventKey))
  )

  const focusedSceneVehicle = computed(() => simulation.selectedVehicle ?? sceneVehicle.value)

  const activeOverviewScene = computed(() =>
    simulation.selectedVehicle ? (focusedVehicleScene.value ?? globalScene.value) : globalScene.value
  )

  const activeOverviewSceneSourceLabel = computed(() =>
    activeOverviewScene.value?.source === 'backend_scene_state'
      ? '场景判定来自后端接口'
      : '当前为前端回退判断'
  )

  const activeOverviewSceneConfigLabel = computed(() =>
    activeOverviewScene.value?.backendName
      ? '页面配置来自后端场景目录'
      : '页面配置使用前端默认映射'
  )

  const activeOverviewSceneMetricCards = computed(() =>
    (activeOverviewScene.value?.keyMetrics ?? []).map((metric) =>
      buildMetricCard(metric, {
        scene: activeOverviewScene.value,
        vehicle: simulation.selectedVehicle ?? sceneVehicle.value,
      })
    )
  )

  const activeOverviewSceneEventCards = computed(() =>
    (activeOverviewScene.value?.highlightEvents ?? []).map((eventKey) =>
      buildSceneEventCard(eventKey, {
        scene: activeOverviewScene.value,
        vehicle: simulation.selectedVehicle ?? sceneVehicle.value,
        scopeMode: simulation.selectedVehicle ? 'focused' : 'global',
      })
    )
  )

  const focusedVehicleSceneMetricCards = computed(() =>
    (focusedVehicleScene.value?.keyMetrics ?? []).map((metric) =>
      buildMetricCard(metric, {
        scene: focusedVehicleScene.value,
        vehicle: focusedSceneVehicle.value,
      })
    )
  )

  const focusedVehicleSceneEventCards = computed(() =>
    (focusedVehicleScene.value?.highlightEvents ?? []).map((eventKey) =>
      buildSceneEventCard(eventKey, {
        scene: focusedVehicleScene.value,
        vehicle: focusedSceneVehicle.value,
        scopeMode: 'focused',
      })
    )
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

  function buildMetricCard(metric, options = {}) {
    const vehicle = options.vehicle ?? sceneVehicle.value
    const scene = options.scene ?? globalScene.value
    const label = METRIC_LABELS[metric] ?? metric

    if (metric === 'speed_kmh') {
      return metricCard(metric, label, vehicle ? `${Math.round(vehicle.speed ?? 0)} km/h` : '—', metricVehicleHint(vehicle), '后端车辆状态')
    }

    if (metric === 'target_speed_kmh') {
      return metricCard(metric, label, vehicle?.target_speed != null ? `${Math.round(vehicle.target_speed)} km/h` : '—', '来自当前车辆控制目标速度', '后端车辆 / MA 数据')
    }

    if (metric === 'recommended_speed_kmh') {
      const recommended = vehicle?.ma_braking_curve_speed_limit ?? vehicle?.target_speed ?? null
      return metricCard(metric, label, recommended != null ? `${Math.round(recommended)} km/h` : '—', '当前以前端可见的制动曲线限速近似推荐速度', '前端基于后端 MA 数据换算')
    }

    if (metric === 'remaining_distance_m') {
      return metricCard(metric, label, vehicle?.stop_distance != null ? `${Math.max(0, vehicle.stop_distance).toFixed(1)} m` : '—', '到停车点的剩余距离', '后端车辆状态')
    }

    if (metric === 'distance_to_ma_m') {
      return metricCard(metric, label, vehicle?.distance_to_ma != null ? `${Math.max(0, vehicle.distance_to_ma).toFixed(1)} m` : '—', '当前授权边界剩余距离', '后端 MA 数据')
    }

    if (metric === 'ma_limit_m') {
      return metricCard(metric, label, vehicle?.ma_limit != null ? `${Math.round(vehicle.ma_limit)} m` : '—', '当前移动授权边界', '后端 MA 数据')
    }

    if (metric === 'old_ma_limit_m') {
      const value = vehicle?.ma_limit != null && maShrinkAmount.value != null
        ? `${Math.round(vehicle.ma_limit + maShrinkAmount.value)} m`
        : '—'
      return metricCard(metric, label, value, '由最近一次 MA 收缩事件反推', '前端基于事件时间线反推')
    }

    if (metric === 'new_ma_limit_m') {
      return metricCard(metric, label, vehicle?.ma_limit != null ? `${Math.round(vehicle.ma_limit)} m` : '—', '收缩后当前 MA 边界', '后端 MA 数据')
    }

    if (metric === 'stop_error_cm') {
      const value = vehicle?.stop_error_cm != null ? `${Math.round(vehicle.stop_error_cm)} cm` : '—'
      return metricCard(metric, label, value, '用于判断进站停车精度', '后端车辆状态')
    }

    if (metric === 'signal_state') {
      return metricCard(metric, label, signalStateLabel(vehicle?.signal_state), '当前主约束信号状态', '后端信号 / MA 数据')
    }

    if (metric === 'atp_triggered') {
      const triggered = Boolean(vehicle?.emergency_brake || activeEmergencyVehicle.value || recentAtpEvent.value)
      return metricCard(metric, label, triggered ? '已触发' : '未触发', triggered ? '系统当前已进入 ATP 保护相关场景' : '当前未见 ATP 介入信号', '前端结合后端状态与事件判断')
    }

    if (metric === 'emergency_brake') {
      return metricCard(
        metric,
        label,
        vehicle?.emergency_brake ? '已施加' : '未施加',
        vehicle?.emergency_brake ? '当前车辆已经进入紧急制动' : '当前车辆尚未进入紧急制动',
        '后端车辆状态',
      )
    }

    if (metric === 'driver_brake_level') {
      const latestDriverInput = simulation.driverInputs.find((input) => input.vehicle_id === vehicle?.vehicle_id)
      return metricCard(
        metric,
        label,
        latestDriverInput ? `B${latestDriverInput.brake_level ?? 0}` : '—',
        latestDriverInput ? '来自最近一次司机输入回显' : '当前还没有这辆车的司机制动级位回显',
        '后端司机台输入回显',
      )
    }

    if (metric === 'blocked_section_id') {
      const blockedLabel = blockedRoute.value?.locked_by_route_id ?? blockedRoute.value?.route_id ?? blockedRoute.value?.required_switch_id ?? '—'
      return metricCard(metric, label, blockedLabel, '当前仅能从未通过进路结果近似提取封锁对象', '前端基于后端进路结果提取')
    }

    if (metric === 'affected_vehicle_count') {
      return metricCard(metric, label, `${affectedVehicles.value.length} 列`, '当前处于限速、停车等待或 ATP 介入的车辆数', '前端基于全量车辆聚合')
    }

    if (metric === 'target_vehicle_id') {
      return metricCard(metric, label, scene.targetVehicleId ?? vehicle?.vehicle_id ?? '—', '当前场景的主要展示车辆', scene.source === 'backend_scene_state' ? '后端场景接口' : '前端回退判断')
    }

    if (metric === 'mode') {
      return metricCard(metric, label, vehicle?.mode ?? '—', '来自当前主展示车辆运行模式', '后端车辆状态')
    }

    if (metric === 'current_section_id') {
      return metricCard(metric, label, vehicle?.section_id ?? '—', '当前车辆所在区段', '后端车辆状态')
    }

    return metricCard(metric, label, '—', '当前尚未完成该指标映射', '待补充')
  }

  function metricVehicleHint(vehicle) {
    if (!vehicle) return '当前场景没有明确目标车辆'
    return `${vehicle.vehicle_id}${vehicle.station_name ? ` · ${vehicle.station_name}` : ''}`
  }

  function signalStateLabel(state) {
    if (state === 'red') return '红灯'
    if (state === 'yellow') return '黄灯'
    if (state === 'green') return '绿灯'
    return state ?? '—'
  }

  function metricCard(key, label, value, hint, sourceLabel) {
    return { key, label, value, hint, sourceLabel }
  }

  function buildSceneEventCard(eventKey, options = {}) {
    const scene = options.scene ?? globalScene.value
    const vehicle = options.vehicle ?? sceneVehicle.value
    const matched = findSceneEvent(eventKey, { scene, vehicle, scopeMode: options.scopeMode ?? 'global' })
    return {
      key: eventKey,
      label: EVENT_LABELS[eventKey] ?? eventKey,
      matched: Boolean(matched),
      title: matched?.title ?? '当前尚未捕获该事件',
      detail: matched?.detail ?? '说明当前场景已识别，但事件时间线里还没有对应的显式事件。',
      atLabel: matched?.at ? formatEventTime(matched.at) : '待触发',
      level: matched?.level ?? 'info',
      sourceLabel: matched?.sourceLabel ?? '前端基于后端数据回填',
    }
  }

  function findSceneEvent(eventKey, options = {}) {
    const scene = options.scene ?? globalScene.value
    const vehicle = options.vehicle ?? sceneVehicle.value
    const vehicleId = scene.targetVehicleId ?? vehicle?.vehicle_id ?? null
    const scopedEvents = vehicleId
      ? recentEvents.value.filter((event) => !event.vehicleId || event.vehicleId === vehicleId)
      : recentEvents.value

    if (eventKey === 'ma_shrink') {
      const match = scopedEvents.find((event) => event.title?.includes('MA 收缩')) ?? null
      return match ? { ...match, sourceLabel: '前端事件时间线匹配' } : null
    }
    if (eventKey === 'atp_triggered' || eventKey === 'emergency_brake_applied') {
      const match = scopedEvents.find((event) => event.title?.includes('进入紧急制动') || event.title?.includes('ATP')) ?? null
      return match ? { ...match, sourceLabel: '前端事件时间线匹配' } : null
    }
    if (eventKey === 'route_denied' || eventKey === 'section_blocked') {
      const route = blockedRoute.value
      if (!route) return null
      return {
        title: route.allowed ? '进路已恢复' : `进路 ${route.route_id ?? '未命名进路'} 未通过`,
        detail: route.reason ? `原因：${route.reason}` : '当前存在未通过进路申请。',
        at: Date.now(),
        level: route.allowed ? 'info' : 'warn',
        sourceLabel: '后端进路结果',
      }
    }
    if (eventKey === 'signal_red') {
      const redVehicle = redSignalVehicle.value ?? vehicle
      if (!redVehicle) return null
      return {
        title: `${redVehicle.vehicle_id} 前方信号为红灯`,
        detail: `许可状态 ${redVehicle.permission ?? 'unknown'} · 距离 MA ${redVehicle.distance_to_ma != null ? `${redVehicle.distance_to_ma.toFixed(1)} m` : '—'}`,
        at: Date.now(),
        level: 'warn',
        sourceLabel: '后端车辆 / MA 快照',
      }
    }
    if (eventKey === 'ma_updated') {
      if (!vehicle?.ma_limit) return null
      return {
        title: `${vehicle.vehicle_id} 当前 MA 已更新`,
        detail: `当前 MA ${Math.round(vehicle.ma_limit)} m · 剩余 ${vehicle.distance_to_ma != null ? `${vehicle.distance_to_ma.toFixed(1)} m` : '—'}`,
        at: Date.now(),
        level: 'info',
        sourceLabel: '后端 MA 快照',
      }
    }
    if (eventKey === 'recommended_speed_drop') {
      const recommended = vehicle?.ma_braking_curve_speed_limit ?? vehicle?.target_speed ?? null
      if (recommended == null) return null
      return {
        title: `${vehicle.vehicle_id} 推荐速度已下调`,
        detail: `当前推荐速度近似 ${Math.round(recommended)} km/h`,
        at: Date.now(),
        level: 'warn',
        sourceLabel: '前端基于后端 MA 数据换算',
      }
    }
    if (eventKey === 'atp_warning') {
      if (!vehicle || vehicle.distance_to_ma == null || vehicle.distance_to_ma > 120) return null
      return {
        title: `${vehicle.vehicle_id} 接近 ATP 风险边界`,
        detail: `距离 MA ${vehicle.distance_to_ma.toFixed(1)} m，建议继续核对制动曲线和当前速度。`,
        at: Date.now(),
        level: 'warn',
        sourceLabel: '前端基于后端 MA 快照判断',
      }
    }
    if (eventKey === 'brake_command_sent') {
      const latestAto = simulation.atoCommands.find((command) => command.vehicle_id === vehicle?.vehicle_id)
      if (!latestAto) return null
      return {
        title: `${latestAto.vehicle_id} 已收到 ATO 命令`,
        detail: `目标速度 ${Math.round(latestAto.target_speed ?? 0)} km/h · 制动级位 ${latestAto.brake_level ?? 0}`,
        at: latestAto.updated_at ? Number(latestAto.updated_at) * 1000 : Date.now(),
        level: 'info',
        sourceLabel: '后端 ATO 命令回显',
      }
    }
    if (eventKey === 'driver_no_response') {
      const vehicle = activeEmergencyVehicle.value
      if (!vehicle) return null
      return {
        title: `${vehicle.vehicle_id} 当前疑似未及时制动`,
        detail: '当前以前端可见的 ATP 介入结果近似表达“司机未及时响应”场景，后续仍建议后端补正式事件字段。',
        at: Date.now(),
        level: 'warn',
        sourceLabel: '前端根据 ATP 结果近似表达',
      }
    }
    if (eventKey === 'approach_started' || eventKey === 'service_brake_started' || eventKey === 'stop_completed') {
      if (!vehicle) return null
      if (eventKey === 'approach_started' && ['approaching', 'braking', 'docking', 'stopped'].includes(vehicle.parking_phase)) {
        return {
          title: `${vehicle.vehicle_id} 已进入接近阶段`,
          detail: `当前停车阶段 ${vehicle.parking_phase} · 站名 ${vehicle.station_name ?? '未知站'}`,
          at: Date.now(),
          level: 'info',
          sourceLabel: '后端停车阶段状态',
        }
      }
      if (eventKey === 'service_brake_started' && ['braking', 'docking', 'stopped'].includes(vehicle.parking_phase)) {
        return {
          title: `${vehicle.vehicle_id} 已进入制动阶段`,
          detail: `当前速度 ${Math.round(vehicle.speed ?? 0)} km/h · 剩余距离 ${vehicle.stop_distance != null ? `${vehicle.stop_distance.toFixed(1)} m` : '—'}`,
          at: Date.now(),
          level: 'info',
          sourceLabel: '后端停车阶段状态',
        }
      }
      if (eventKey === 'stop_completed' && vehicle.parking_phase === 'stopped') {
        return {
          title: `${vehicle.vehicle_id} 已停稳`,
          detail: `停车误差 ${vehicle.stop_error_cm != null ? `${Math.round(vehicle.stop_error_cm)} cm` : '—'}`,
          at: Date.now(),
          level: 'info',
          sourceLabel: '后端停车结果状态',
        }
      }
      return null
    }

    const fallbackEvent = scopedEvents.find((event) => event.title?.includes(EVENT_LABELS[eventKey] ?? '')) ?? null
    return fallbackEvent ? { ...fallbackEvent, sourceLabel: '前端事件时间线匹配' } : null
  }

  function formatEventTime(at) {
    return new Date(Number(at)).toLocaleTimeString('zh-CN', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }
}
