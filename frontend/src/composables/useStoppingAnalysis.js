import { computed } from 'vue'
import { parkingPhaseLabel, resolveStopErrorCm } from '@/adapters/simulation'
import { useSimulationStore } from '@/stores/simulation'

export function useStoppingAnalysis() {
  const simulation = useSimulationStore()
  const vehicle = computed(() => simulation.selectedVehicle)
  const authority = computed(() => simulation.selectedVehicleAuthority)
  const latestDriverInput = computed(() =>
    simulation.driverInputs.find((input) => input.vehicle_id === vehicle.value?.vehicle_id) ?? null
  )
  const latestAtoCommand = computed(() =>
    simulation.atoCommands.find((command) => command.vehicle_id === vehicle.value?.vehicle_id) ?? null
  )
  const recentControls = computed(() => {
    const all = simulation.controlHistory
    if (!vehicle.value) return all.slice(0, 6)
    const own = all.filter((entry) => entry.vehicleId === vehicle.value.vehicle_id)
    return (own.length ? own : all).slice(0, 6)
  })
  const relatedAlarms = computed(() =>
    simulation.alarms.filter((alarm) =>
      alarm.vehicle_id === vehicle.value?.vehicle_id
      || alarm.source === 'ATP'
      || alarm.source === 'ATO'
    )
  )
  const targetSpeed = computed(() =>
    vehicle.value?.target_speed
    ?? authority.value?.target_speed
    ?? null
  )
  const distanceToMa = computed(() =>
    vehicle.value?.distance_to_ma
    ?? authority.value?.distance_to_ma
    ?? null
  )
  const maLimit = computed(() =>
    vehicle.value?.ma_limit
    ?? authority.value?.ma_limit
    ?? null
  )
  const requiredStopDistance = computed(() =>
    vehicle.value?.ma_required_stop_distance
    ?? vehicle.value?.required_stop_distance
    ?? authority.value?.required_stop_distance
    ?? null
  )
  const emergencyStopDistance = computed(() =>
    vehicle.value?.ma_emergency_stop_distance
    ?? vehicle.value?.emergency_stop_distance
    ?? authority.value?.emergency_stop_distance
    ?? null
  )
  const warningDistance = computed(() =>
    vehicle.value?.ma_warning_distance
    ?? vehicle.value?.warning_distance
    ?? authority.value?.warning_distance
    ?? null
  )
  const brakingCurveLimit = computed(() =>
    vehicle.value?.ma_braking_curve_speed_limit
    ?? vehicle.value?.braking_curve_speed_limit
    ?? authority.value?.braking_curve_speed_limit
    ?? null
  )
  const stopErrorCm = computed(() => resolveStopErrorCm(vehicle.value))
  const parkingPhaseText = computed(() => parkingPhaseLabel(vehicle.value?.parking_phase))
  const serviceMargin = computed(() =>
    distanceToMa.value != null && requiredStopDistance.value != null
      ? distanceToMa.value - requiredStopDistance.value
      : null
  )
  const emergencyMargin = computed(() =>
    distanceToMa.value != null && emergencyStopDistance.value != null
      ? distanceToMa.value - emergencyStopDistance.value
      : null
  )
  const heartbeatText = computed(() => {
    const timestamp = resolveVehicleTimestamp(vehicle.value, simulation)
    if (!timestamp) return '等待心跳'
    const delta = Math.max(0, Date.now() - timestamp)
    if (delta < 1000) return '刚刚更新'
    if (delta < 60000) return `${Math.floor(delta / 1000)} 秒前`
    return `${Math.floor(delta / 60000)} 分钟前`
  })
  const chartOption = computed(() => buildBrakingChartOption({
    vehicle: vehicle.value,
    targetSpeed: targetSpeed.value,
    distanceToMa: distanceToMa.value,
    requiredStopDistance: requiredStopDistance.value,
    emergencyStopDistance: emergencyStopDistance.value,
    warningDistance: warningDistance.value,
    brakingCurveLimit: brakingCurveLimit.value,
  }))

  return {
    vehicle,
    authority,
    latestDriverInput,
    latestAtoCommand,
    recentControls,
    relatedAlarms,
    targetSpeed,
    distanceToMa,
    maLimit,
    requiredStopDistance,
    emergencyStopDistance,
    warningDistance,
    brakingCurveLimit,
    stopErrorCm,
    parkingPhaseText,
    serviceMargin,
    emergencyMargin,
    heartbeatText,
    chartOption,
    atoCommands: computed(() => simulation.atoCommands),
    driverInputs: computed(() => simulation.driverInputs),
    alarms: computed(() => simulation.alarms),
  }
}

function resolveVehicleTimestamp(vehicle, simulation) {
  if (vehicle?.updated_at != null) {
    const raw = vehicle.updated_at
    if (typeof raw === 'string') {
      const parsed = Date.parse(raw)
      if (Number.isFinite(parsed)) return parsed
    }
    const numeric = Number(raw)
    if (Number.isFinite(numeric)) return numeric > 1e12 ? numeric : numeric * 1000
  }

  if (simulation.protocolMessageAt) return simulation.protocolMessageAt
  if (simulation.lastTickAt) return simulation.lastTickAt
  return null
}

function buildBrakingChartOption({
  vehicle,
  targetSpeed,
  distanceToMa,
  requiredStopDistance,
  emergencyStopDistance,
  warningDistance,
  brakingCurveLimit,
}) {
  if (!vehicle) {
    return {
      title: {
        text: '速度-距离主图',
        textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
      },
      xAxis: { show: false, type: 'value' },
      yAxis: { show: false, type: 'value' },
      series: [],
    }
  }

  const currentSpeed = Math.max(0, Number(vehicle.speed ?? 0))
  const currentTarget = Number.isFinite(Number(targetSpeed)) ? Number(targetSpeed) : null
  const stopDistance = Number.isFinite(Number(vehicle.stop_distance))
    ? Math.max(20, Number(vehicle.stop_distance))
    : null
  const serviceDistance = Number.isFinite(Number(requiredStopDistance))
    ? Math.max(20, Number(requiredStopDistance))
    : stopDistance
  const emergencyDistance = Number.isFinite(Number(emergencyStopDistance))
    ? Math.max(12, Number(emergencyStopDistance))
    : null
  const maDistance = Number.isFinite(Number(distanceToMa))
    ? Math.max(0, Number(distanceToMa))
    : null
  const horizon = Math.max(
    60,
    stopDistance ?? 0,
    serviceDistance ?? 0,
    emergencyDistance ?? 0,
    maDistance ?? 0,
    Number.isFinite(Number(warningDistance)) ? Number(warningDistance) : 0,
  )

  const serviceCurve = buildCurvePoints(currentSpeed, serviceDistance ?? horizon)
  const emergencyCurve = emergencyDistance ? buildCurvePoints(currentSpeed, emergencyDistance) : []
  const targetLine = currentTarget != null ? [[0, currentTarget], [horizon, currentTarget]] : []
  const atpLine = Number.isFinite(Number(brakingCurveLimit))
    ? [[0, Number(brakingCurveLimit)], [horizon, Number(brakingCurveLimit)]]
    : []

  const markers = [
    {
      name: '当前速度',
      xAxis: 0,
      yAxis: currentSpeed,
      itemStyle: { color: '#f59e0b' },
      label: { color: '#111827', fontWeight: 'bold' },
    },
  ]

  if (currentTarget != null) {
    markers.push({
      name: '目标速度',
      xAxis: 0,
      yAxis: currentTarget,
      itemStyle: { color: '#38bdf8' },
      label: { color: '#111827', fontWeight: 'bold' },
    })
  }

  const verticalLines = [
    maDistance != null ? {
      xAxis: maDistance,
      lineStyle: { color: '#f97316', type: 'dashed' },
      label: { formatter: 'MA 边界', color: '#fdba74' },
    } : null,
    stopDistance != null ? {
      xAxis: stopDistance,
      lineStyle: { color: '#34d399', type: 'dashed' },
      label: { formatter: '停车点', color: '#86efac' },
    } : null,
    Number.isFinite(Number(warningDistance)) ? {
      xAxis: Number(warningDistance),
      lineStyle: { color: '#facc15', type: 'dotted' },
      label: { formatter: 'ATP 预警', color: '#fde68a' },
    } : null,
  ].filter(Boolean)

  return {
    title: {
      text: '速度-距离主图',
      subtext: `${vehicle.vehicle_id} · 当前速度 ${currentSpeed.toFixed(1)} km/h`,
      textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
      subtextStyle: { color: '#6b7280', fontSize: 11 },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      formatter: (params) => {
        const lines = [`距离 ${params?.[0]?.axisValueLabel ?? '0'} m`]
        for (const item of params ?? []) {
          if (item.value?.[1] == null) continue
          lines.push(`${item.marker}${item.seriesName}：${Number(item.value[1]).toFixed(1)} km/h`)
        }
        return lines.join('<br/>')
      },
    },
    legend: {
      bottom: 0,
      textStyle: { color: '#94a3b8' },
    },
    grid: { left: 48, right: 22, top: 62, bottom: 56 },
    xAxis: {
      type: 'value',
      name: '前向距离 m',
      min: 0,
      max: Math.ceil(horizon),
      axisLabel: { color: '#6b7280' },
      axisLine: { lineStyle: { color: '#334155' } },
      splitLine: { lineStyle: { color: '#0f172a' } },
      nameTextStyle: { color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      name: '速度 km/h',
      min: 0,
      axisLabel: { color: '#6b7280' },
      axisLine: { lineStyle: { color: '#334155' } },
      splitLine: { lineStyle: { color: '#1e293b' } },
      nameTextStyle: { color: '#64748b' },
    },
    series: [
      {
        name: '常用制动曲线',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: serviceCurve,
        lineStyle: { width: 3, color: '#22d3ee' },
        areaStyle: { color: 'rgba(34, 211, 238, 0.08)' },
        markPoint: {
          symbol: 'circle',
          symbolSize: 28,
          data: markers,
        },
        markLine: {
          symbol: 'none',
          data: verticalLines,
        },
      },
      {
        name: '紧急制动曲线',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: emergencyCurve,
        lineStyle: { width: 2, color: '#fb7185', type: 'dashed' },
      },
      {
        name: '目标速度',
        type: 'line',
        symbol: 'none',
        data: targetLine,
        lineStyle: { width: 2, color: '#38bdf8', type: 'dashed' },
      },
      {
        name: 'ATP 曲线限速',
        type: 'line',
        symbol: 'none',
        data: atpLine,
        lineStyle: { width: 2, color: '#f59e0b', type: 'dotted' },
      },
    ],
  }
}

function buildCurvePoints(initialSpeedKmh, distanceM) {
  const totalDistance = Math.max(10, Number(distanceM) || 10)
  const speedMs = Math.max(0, initialSpeedKmh / 3.6)
  const decel = speedMs > 0
    ? Math.max(0.35, Math.min(1.6, (speedMs * speedMs) / (2 * totalDistance)))
    : 0.45
  const points = []

  for (let index = 0; index <= 24; index += 1) {
    const distance = (totalDistance / 24) * index
    const remaining = Math.max(0, totalDistance - distance)
    const speed = Math.sqrt(Math.max(0, 2 * decel * remaining)) * 3.6
    points.push([Number(distance.toFixed(1)), Number(speed.toFixed(1))])
  }

  return points
}
