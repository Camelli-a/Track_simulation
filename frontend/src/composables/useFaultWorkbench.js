import { computed, ref } from 'vue'
import { useSimulationStore } from '@/stores/simulation'
import { useUiStore } from '@/stores/ui'
import { useOverviewScene } from '@/composables/useOverviewScene'

const operatorActions = ref([])
let actionCounter = 0

export function useFaultWorkbench() {
  const simulation = useSimulationStore()
  const ui = useUiStore()
  const { globalScene } = useOverviewScene()

  const abnormalVehicles = computed(() =>
    simulation.vehicles.filter((vehicle) =>
      vehicle.emergency_brake
      || vehicle.permission === 'stop'
      || vehicle.permission === 'restricted'
      || ['braking', 'docking', 'stopped'].includes(vehicle.parking_phase)
    )
  )

  const activeSystemEvents = computed(() => {
    const list = []

    if (simulation.power?.is_fault) {
      list.push({
        id: 'power-fault-active',
        kind: 'power_fault',
        title: '当前存在供电故障',
        detail: `电压 ${Math.round(simulation.power?.voltage ?? 0)} V · 电流 ${Math.round(simulation.power?.current ?? 0)} A`,
        level: 'error',
        status: 'active',
        source: 'POWER',
        vehicleId: null,
        at: simulation.power?.updated_at ? normalizeAt(simulation.power.updated_at) : Date.now(),
        actionHint: '请切换到供电页确认故障影响范围。',
      })
    }

    for (const vehicle of simulation.vehicles.filter((item) => item.emergency_brake)) {
      list.push({
        id: `eb-${vehicle.vehicle_id}`,
        kind: 'emergency_brake',
        title: `${vehicle.vehicle_id} 当前处于紧急制动`,
        detail: `当前位置 ${Math.round(vehicle.position ?? 0)} m · 速度 ${Math.round(vehicle.speed ?? 0)} km/h`,
        level: 'error',
        status: 'active',
        source: 'ATP',
        vehicleId: vehicle.vehicle_id,
        at: normalizeAt(vehicle.updated_at) ?? Date.now(),
        actionHint: '建议切到停车控制页核对 ATP 触发原因和停车结果。',
      })
    }

    for (const route of simulation.routeResults.filter((item) => !item.allowed)) {
      list.push({
        id: `route-${route.vehicle_id ?? 'na'}-${route.route_id ?? 'na'}`,
        kind: 'route_denied',
        title: `${route.route_id ?? '未命名进路'} 未通过联锁校验`,
        detail: route.reason ?? '当前存在未通过进路申请。',
        level: 'warn',
        status: 'active',
        source: 'SIGNAL',
        vehicleId: route.vehicle_id ?? null,
        at: Date.now(),
        actionHint: '建议切到信号与联锁页查看进路不满足和道岔约束。',
      })
    }

    for (const alarm of simulation.alarms) {
      list.push({
        id: `alarm-${alarm.alarm_id}`,
        kind: 'alarm',
        title: alarm.message || alarm.alarm_id,
        detail: [alarm.source_label ?? alarm.source, alarm.vehicle_id].filter(Boolean).join(' · '),
        level: alarm.level === 'critical' ? 'error' : alarm.level === 'warning' ? 'warn' : 'info',
        status: 'active',
        source: alarm.source ?? 'ALARM',
        vehicleId: alarm.vehicle_id ?? null,
        at: alarm.timestamp ? alarm.timestamp * 1000 : Date.now(),
        actionHint: '建议结合事件时间线确认该告警对应的链路变化。',
      })
    }

    return list
      .sort((a, b) => Number(b.at ?? 0) - Number(a.at ?? 0))
      .slice(0, 12)
  })

  const recentFaultEvents = computed(() =>
    simulation.eventTimeline
      .filter((event) => event.level === 'error' || event.level === 'warn')
      .slice(0, 12)
  )

  const latestOperatorAction = computed(() => operatorActions.value[0] ?? null)

  const activeFaultCount = computed(() =>
    activeSystemEvents.value.filter((event) => event.level === 'error' || event.level === 'warn').length
  )

  const maShrinkEventCount = computed(() =>
    simulation.eventTimeline.filter((event) => event.title?.includes('MA 收缩')).length
  )

  const redSignalCount = computed(() =>
    simulation.signals.filter((signal) => (signal.signal_state ?? signal.state) === 'red').length
  )

  const restrictedVehicleCount = computed(() =>
    simulation.vehicles.filter((vehicle) =>
      vehicle.permission === 'stop' || vehicle.permission === 'restricted'
    ).length
  )

  function focusLatestAnomalyVehicle() {
    const target = abnormalVehicles.value[0] ?? simulation.vehicles[0] ?? null
    if (!target) {
      ui.showToast({
        type: 'warning',
        title: '当前没有可聚焦的异常车辆',
        message: '请先确认是否已有在线列车和异常状态。',
        duration: 2800,
      })
      return
    }

    simulation.selectVehicle(target.vehicle_id)
    recordOperatorAction({
      type: 'focus_vehicle',
      title: `聚焦 ${target.vehicle_id}`,
      detail: '已自动切到当前最需要关注的车辆。',
      vehicleId: target.vehicle_id,
      status: 'ok',
    })
    ui.showToast({
      type: 'info',
      title: `已聚焦 ${target.vehicle_id}`,
      message: '你现在可以切到停车控制页或信号页继续看这辆车。',
      duration: 2600,
    })
  }

  async function publishTrackInfoAction() {
    recordOperatorAction({
      type: 'publish_track_info',
      title: '重新发布线路静态数据',
      detail: '向消息总线重新发布 track_info。',
      status: 'pending',
    })
    try {
      await simulation.publishTrackInfoMessage()
      markLatestPendingAction('publish_track_info', { status: 'ok' })
    } catch (error) {
      markLatestPendingAction('publish_track_info', {
        status: 'error',
        error: error?.response?.data?.detail ?? error?.message ?? 'publish_track_info_failed',
      })
    }
  }

  function injectEmergencyBrake() {
    const vehicle = simulation.selectedVehicle
    if (!vehicle) {
      ui.showToast({
        type: 'warning',
        title: '请先选择一辆车',
        message: '紧急制动演示需要明确目标车辆。',
        duration: 2800,
      })
      return
    }

    ui.requestConfirm({
      title: `确认对 ${vehicle.vehicle_id} 执行紧急制动演示？`,
      message: '这会向当前车辆发送真实的紧急制动控制指令，适合用于 ATP 介入停车演示。',
      confirmLabel: '执行紧急制动',
      cancelLabel: '取消',
      destructive: true,
      onConfirm: async () => {
        recordOperatorAction({
          type: 'emergency_brake_demo',
          title: `对 ${vehicle.vehicle_id} 下发紧急制动`,
          detail: '演示 ATP 介入停车。',
          vehicleId: vehicle.vehicle_id,
          status: 'pending',
        })
        const result = await simulation.sendControlCommand(vehicle.vehicle_id, {
          type: 'emergency_brake',
          label: '紧急制动演示',
          source: 'fault-page',
          line_id: vehicle.line_id ?? 'LINE-1',
          direction: 'forward',
          traction_level: 0,
          brake_level: 4,
        })
        if (result?.ok) {
          markLatestPendingAction('emergency_brake_demo', { status: 'ok' })
        } else {
          markLatestPendingAction('emergency_brake_demo', {
            status: 'error',
            error: result?.error ?? 'emergency_brake_demo_failed',
          })
        }
      },
    })
  }

  function injectLowSpeedCommand() {
    const vehicle = simulation.selectedVehicle
    if (!vehicle) {
      ui.showToast({
        type: 'warning',
        title: '请先选择一辆车',
        message: '限速演示需要明确目标车辆。',
        duration: 2800,
      })
      return
    }

    ui.requestConfirm({
      title: `确认对 ${vehicle.vehicle_id} 下发低速运行目标？`,
      message: '这会通过 ATO 控制接口向当前车辆发送低速目标，用于演示约束收紧后的速度下降效果。',
      confirmLabel: '下发低速目标',
      cancelLabel: '取消',
      destructive: false,
      onConfirm: async () => {
        recordOperatorAction({
          type: 'low_speed_demo',
          title: `对 ${vehicle.vehicle_id} 下发 15 km/h 低速目标`,
          detail: '演示目标速度骤降或保守运行状态。',
          vehicleId: vehicle.vehicle_id,
          status: 'pending',
        })
        const result = await simulation.sendControlCommand(vehicle.vehicle_id, {
          type: 'ato',
          label: '低速运行演示',
          source: 'fault-page',
          line_id: vehicle.line_id ?? 'LINE-1',
          target_speed: 15,
          target_position: vehicle.ma_limit ?? undefined,
          traction_level: 0,
          brake_level: 2,
          reason: 'fault_demo_speed_drop',
        })
        if (result?.ok) {
          markLatestPendingAction('low_speed_demo', { status: 'ok' })
        } else {
          markLatestPendingAction('low_speed_demo', {
            status: 'error',
            error: result?.error ?? 'low_speed_demo_failed',
          })
        }
      },
    })
  }

  function injectStopAtMa() {
    const vehicle = simulation.selectedVehicle
    if (!vehicle) {
      ui.showToast({
        type: 'warning',
        title: '请先选择一辆车',
        message: '停车目标演示需要明确目标车辆。',
        duration: 2800,
      })
      return
    }

    const targetPosition = Number.isFinite(Number(vehicle.ma_limit))
      ? Number(vehicle.ma_limit)
      : Number(vehicle.position ?? 0) + 30

    ui.requestConfirm({
      title: `确认对 ${vehicle.vehicle_id} 下发停车目标？`,
      message: '这会通过 ATO 控制接口发送 0 km/h 停车目标，用于演示“前方受限后安全停车”的结果。',
      confirmLabel: '下发停车目标',
      cancelLabel: '取消',
      destructive: false,
      onConfirm: async () => {
        recordOperatorAction({
          type: 'stop_target_demo',
          title: `对 ${vehicle.vehicle_id} 下发停车目标`,
          detail: `目标位置 ${Math.round(targetPosition)} m`,
          vehicleId: vehicle.vehicle_id,
          status: 'pending',
        })
        const result = await simulation.sendControlCommand(vehicle.vehicle_id, {
          type: 'ato',
          label: '停车目标演示',
          source: 'fault-page',
          line_id: vehicle.line_id ?? 'LINE-1',
          target_speed: 0,
          target_position: targetPosition,
          traction_level: 0,
          brake_level: 3,
          reason: 'fault_demo_stop_target',
        })
        if (result?.ok) {
          markLatestPendingAction('stop_target_demo', { status: 'ok' })
        } else {
          markLatestPendingAction('stop_target_demo', {
            status: 'error',
            error: result?.error ?? 'stop_target_demo_failed',
          })
        }
      },
    })
  }

  function clearOperatorActions() {
    operatorActions.value = []
    ui.showToast({
      type: 'info',
      title: '已清空本地演示记录',
      message: '这不会影响后端当前运行状态，只清理前端演示操作痕迹。',
      duration: 2400,
    })
  }

  return {
    simulation,
    ui,
    globalScene,
    operatorActions,
    latestOperatorAction,
    activeSystemEvents,
    recentFaultEvents,
    abnormalVehicles,
    activeFaultCount,
    maShrinkEventCount,
    redSignalCount,
    restrictedVehicleCount,
    focusLatestAnomalyVehicle,
    publishTrackInfoAction,
    injectEmergencyBrake,
    injectLowSpeedCommand,
    injectStopAtMa,
    clearOperatorActions,
  }
}

function recordOperatorAction(entry) {
  actionCounter += 1
  operatorActions.value = [
    {
      id: `fault-action-${Date.now()}-${actionCounter}`,
      at: Date.now(),
      ...entry,
    },
    ...operatorActions.value,
  ].slice(0, 12)
}

function markLatestPendingAction(type, patch) {
  const index = operatorActions.value.findIndex((item) => item.type === type && item.status === 'pending')
  if (index < 0) return
  const next = [...operatorActions.value]
  next[index] = {
    ...next[index],
    ...patch,
    finishedAt: Date.now(),
  }
  operatorActions.value = next
}

function normalizeAt(raw) {
  if (raw == null) return null
  const numeric = Number(raw)
  if (Number.isFinite(numeric)) return numeric > 1e12 ? numeric : numeric * 1000
  const parsed = Date.parse(raw)
  return Number.isFinite(parsed) ? parsed : null
}
