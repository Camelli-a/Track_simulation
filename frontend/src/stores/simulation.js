import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { getVehicleColor, pruneVehicleColors } from '@/utils/vehicleColors'
import { normalizeTick, resolveStopErrorCm } from '@/adapters/simulation'
import { fetchDashboardSnapshot } from '@/api/dashboard'
import { sendVehicleControl } from '@/api/vehicleControl'
import {
  mergeSegments,
  overlayOccupancy,
  mergeSignals,
  mergeTurnouts,
} from '@/adapters/lineLayout'
import { useLineLayoutStore } from '@/stores/lineLayout'
import { useUiStore } from '@/stores/ui'

const HISTORY_LIMIT = 120
const STALE_MS = 2000
const PARKING_RECORD_LIMIT = 20
const OCCUPANCY_BINS = 48
const EVENT_TIMELINE_LIMIT = 40
const EVENT_DEDUP_MS = 2500
const MA_SHRINK_THRESHOLD = 150
const MA_EVENT_COOLDOWN_MS = 8000
const CONTROL_HISTORY_LIMIT = 20
const POWER_TRANSITION_LIMIT = 8
const SNAPSHOT_FALLBACK_MS = 5000

export const useSimulationStore = defineStore('simulation', () => {
  const tick = ref(null)
  const selectedVehicleId = ref(null)
  const lastTickAt = ref(0)
  const dataStale = ref(false)
  const lastControlCommand = ref(null)
  const parkingRecords = ref([])

  const vehicleHistory = ref({})
  const voltageHistory = ref([])
  const timeLabels = ref([])
  const occupancyHistory = ref([])
  const eventTimeline = ref([])
  const controlHistory = ref([])
  const powerTransitions = ref([])

  const lineLayout = useLineLayoutStore()
  const ui = useUiStore()

  const { connected, connecting, lastError, connect: wsConnect, disconnect: wsDisconnect } =
    useWebSocket('/ws/dashboard')

  let staleTimer = null
  let snapshotPollTimer = null
  const lastStopState = new Map()
  const recentEventKeys = new Map()
  const recentMaEventAt = new Map()
  let eventCounter = 0
  let controlCounter = 0

  const vehicles = computed(() => tick.value?.vehicles ?? [])

  const totalLength = computed(() =>
    lineLayout.totalLength || tick.value?.total_length || 5000
  )

  const stations = computed(() =>
    lineLayout.stations.length ? lineLayout.stations : (tick.value?.stations ?? [])
  )

  const trackSegments = computed(() => {
    const blocks = lineLayout.blocks
    const dynamic = tick.value?.track_segments ?? []
    const veh = vehicles.value

    if (blocks.length && dynamic.length) {
      return mergeSegments(blocks, dynamic)
    }
    if (blocks.length) {
      return overlayOccupancy(
        blocks.map((b) => ({ ...b, occupied: false, aspect: 'green', occupied_by: null })),
        veh,
      )
    }
    return dynamic
  })

  const signals = computed(() =>
    mergeSignals(lineLayout.signals, tick.value?.signals ?? [])
  )

  const turnouts = computed(() =>
    mergeTurnouts(lineLayout.turnouts, tick.value?.turnouts ?? [])
  )

  const slopeProfile = computed(() => lineLayout.slopeProfile)

  const power = computed(() => tick.value?.power ?? null)
  const alarms = computed(() => tick.value?.alarms ?? [])
  const systemInfo = computed(() => tick.value?.system ?? null)
  const dataSource = computed(() => tick.value?.system?.data_source ?? null)
  const protocolVersion = computed(() => tick.value?.protocol_version ?? null)

  const systemMode = computed(() => {
    const status = tick.value?.system?.status
    if (status === 'emergency' || status === 'degraded') return status
    return tick.value?.system_mode ?? 'offline'
  })

  const selectedVehicle = computed(() =>
    vehicles.value.find((v) => v.vehicle_id === selectedVehicleId.value) ?? null
  )

  const currentStopErrorCm = computed(() => {
    const v = selectedVehicle.value
    return v ? resolveStopErrorCm(v) : null
  })

  function vehicleColor(id) {
    return getVehicleColor(id)
  }

  function selectVehicle(id) {
    selectedVehicleId.value = id
  }

  function pushTimelineEvent(event) {
    const at = event.at ?? Date.now()
    const dedupeKey = event.key
      ?? `${event.type}:${event.title}:${event.vehicleId ?? ''}:${event.detail ?? ''}`
    const lastAt = recentEventKeys.get(dedupeKey)
    if (lastAt && at - lastAt < EVENT_DEDUP_MS) return

    recentEventKeys.set(dedupeKey, at)
    for (const [key, ts] of recentEventKeys) {
      if (at - ts > 30000) recentEventKeys.delete(key)
    }

    eventCounter += 1
    eventTimeline.value = [
      {
        id: `evt-${at}-${eventCounter}`,
        type: event.type ?? 'system',
        level: event.level ?? 'info',
        title: event.title,
        detail: event.detail ?? '',
        source: event.source ?? null,
        vehicleId: event.vehicleId ?? null,
        at,
      },
      ...eventTimeline.value,
    ].slice(0, EVENT_TIMELINE_LIMIT)
  }

  function recordControlHistory(entry) {
    controlCounter += 1
    const id = `cmd-${Date.now()}-${controlCounter}`
    controlHistory.value = [
      { id, ...entry },
      ...controlHistory.value,
    ].slice(0, CONTROL_HISTORY_LIMIT)
    return id
  }

  function updateControlHistory(id, patch) {
    controlHistory.value = controlHistory.value.map((entry) =>
      entry.id === id ? { ...entry, ...patch } : entry
    )
  }

  function recordPowerTransition(transition) {
    powerTransitions.value = [transition, ...powerTransitions.value].slice(0, POWER_TRANSITION_LIMIT)
  }

  async function sendControlCommand(vehicleId, cmd) {
    const labels = { traction: '牵引', brake: '制动', emergency_brake: '紧急制动' }
    const label = labels[cmd.type] ?? cmd.type
    const historyId = recordControlHistory({
      vehicleId,
      label,
      command: cmd.type,
      level: cmd.level ?? 1,
      source: cmd.source ?? 'keyboard',
      status: 'pending',
      at: Date.now(),
    })

    lastControlCommand.value = {
      vehicleId,
      cmd,
      label,
      status: 'pending',
      at: Date.now(),
    }

    try {
      await sendVehicleControl({
        vehicle_id: vehicleId,
        command: cmd.type,
        level: cmd.level ?? 1,
        source: cmd.source ?? 'keyboard',
      })
      updateControlHistory(historyId, { status: 'ok', at: Date.now() })
      lastControlCommand.value = {
        ...lastControlCommand.value,
        status: 'ok',
        at: Date.now(),
      }
      ui.showToast({
        type: 'success',
        title: `${vehicleId} 已执行${label}`,
        message: `指令来源：${cmd.source ?? 'keyboard'}`,
      })
    } catch (err) {
      const errorMessage = err.response?.data?.detail ?? err.message
      updateControlHistory(historyId, {
        status: 'error',
        error: errorMessage,
        at: Date.now(),
      })
      lastControlCommand.value = {
        ...lastControlCommand.value,
        status: 'error',
        error: errorMessage,
        at: Date.now(),
      }
      ui.showToast({
        type: 'error',
        title: `${vehicleId} 指令失败`,
        message: errorMessage,
        duration: 3800,
      })
    }
  }

  function recordParkingEvents(vehicleList) {
    for (const v of vehicleList) {
      const err = resolveStopErrorCm(v)
      const prev = lastStopState.get(v.vehicle_id)
      const isStopping = err != null

      if (isStopping && !prev?.wasStopping && err <= 50) {
        parkingRecords.value = [
          ...parkingRecords.value,
          {
            vehicleId: v.vehicle_id,
            station: v.station_name ?? '未知站',
            errorCm: err,
            at: Date.now(),
          },
        ].slice(-PARKING_RECORD_LIMIT)
      }
      lastStopState.set(v.vehicle_id, { wasStopping: isStopping, err })
    }
  }

  function recordOccupancySnapshot(vehicleList, lengthM) {
    const total = lengthM || lineLayout.totalLength || 47500
    const binSize = total / OCCUPANCY_BINS
    const bins = new Array(OCCUPANCY_BINS).fill(0)

    for (let i = 0; i < OCCUPANCY_BINS; i++) {
      const start = i * binSize
      const end = (i + 1) * binSize
      const occupied = vehicleList.some((v) => v.position >= start && v.position < end)
      if (occupied) {
        bins[i] = 2
        continue
      }
      const near = vehicleList.some(
        (v) => v.position >= start - 250 && v.position < end + 250,
      )
      bins[i] = near ? 1 : 0
    }

    occupancyHistory.value = [...occupancyHistory.value, bins].slice(-HISTORY_LIMIT)
  }

  function resetStaleTimer() {
    dataStale.value = false
    if (staleTimer) clearTimeout(staleTimer)
    staleTimer = setTimeout(() => { dataStale.value = true }, STALE_MS)
  }

  async function hydrateFromSnapshot() {
    try {
      const snapshot = await fetchDashboardSnapshot()
      handleTick(snapshot)
      return true
    } catch (err) {
      console.warn('[Simulation] snapshot fallback failed', err?.message ?? err)
      return false
    }
  }

  function startSnapshotPolling() {
    if (snapshotPollTimer) return
    snapshotPollTimer = setInterval(() => {
      if (!connected.value && !connecting.value) {
        hydrateFromSnapshot()
      }
    }, SNAPSHOT_FALLBACK_MS)
  }

  function stopSnapshotPolling() {
    if (!snapshotPollTimer) return
    clearInterval(snapshotPollTimer)
    snapshotPollTimer = null
  }

  function effectiveSystemMode(snapshot) {
    const status = snapshot?.system?.status
    if (status === 'emergency' || status === 'degraded') return status
    return snapshot?.system_mode ?? 'offline'
  }

  function levelFromAlarm(level) {
    if (level === 'critical') return 'error'
    if (level === 'warning') return 'warn'
    return 'info'
  }

  function modeText(mode) {
    if (mode === 'emergency') return '紧急模式'
    if (mode === 'degraded') return '降级运行'
    if (mode === 'normal') return '正常运行'
    if (mode === 'offline') return '离线待机'
    return mode ?? '未知状态'
  }

  function recordTimelineEvents(prevPayload, payload) {
    const at = Math.round((payload.timestamp ?? Date.now() / 1000) * 1000)
    const prevMode = effectiveSystemMode(prevPayload)
    const nextMode = effectiveSystemMode(payload)

    if (prevPayload && prevMode !== nextMode) {
      pushTimelineEvent({
        type: 'mode',
        level: nextMode === 'emergency' ? 'error' : nextMode === 'degraded' ? 'warn' : 'info',
        title: `系统模式切换为${modeText(nextMode)}`,
        detail: prevMode ? `上一状态：${modeText(prevMode)}` : '系统模式发生变化',
        source: 'SYSTEM',
        at,
        key: `mode:${nextMode}`,
      })
    }

    const prevFault = Boolean(prevPayload?.power?.is_fault)
    const nextFault = Boolean(payload.power?.is_fault)
    if (prevPayload && prevFault !== nextFault) {
      recordPowerTransition({
        id: `power-${at}`,
        type: nextFault ? 'fault' : 'recovery',
        beforeVoltage: prevPayload?.power?.voltage ?? null,
        beforeCurrent: prevPayload?.power?.current ?? null,
        afterVoltage: payload.power?.voltage ?? null,
        afterCurrent: payload.power?.current ?? null,
        at,
      })
      pushTimelineEvent({
        type: 'power',
        level: nextFault ? 'error' : 'info',
        title: nextFault ? '接触网供电故障' : '供电故障恢复',
        detail: payload.power
          ? `电压 ${Math.round(payload.power.voltage)} V · 电流 ${Math.round(payload.power.current)} A`
          : '供电状态发生变化',
        source: 'POWER',
        at,
        key: `power-fault:${nextFault}`,
      })
    }

    const prevAlarms = new Map((prevPayload?.alarms ?? []).map((alarm) => [alarm.alarm_id, alarm]))
    const nextAlarms = new Map((payload.alarms ?? []).map((alarm) => [alarm.alarm_id, alarm]))

    for (const [alarmId, alarm] of nextAlarms) {
      if (prevAlarms.has(alarmId)) continue
      pushTimelineEvent({
        type: 'alarm',
        level: levelFromAlarm(alarm.level),
        title: alarm.message || `新增告警 ${alarmId}`,
        detail: [alarm.source, alarm.vehicle_id].filter(Boolean).join(' · '),
        source: 'ALARM',
        vehicleId: alarm.vehicle_id ?? null,
        at: alarm.timestamp ? alarm.timestamp * 1000 : at,
        key: `alarm-open:${alarmId}`,
      })
    }

    for (const [alarmId, alarm] of prevAlarms) {
      if (nextAlarms.has(alarmId)) continue
      pushTimelineEvent({
        type: 'alarm',
        level: 'info',
        title: `告警恢复：${alarm.message || alarmId}`,
        detail: [alarm.source, alarm.vehicle_id].filter(Boolean).join(' · '),
        source: 'ALARM',
        vehicleId: alarm.vehicle_id ?? null,
        at,
        key: `alarm-close:${alarmId}`,
      })
    }

    const prevVehicles = new Map((prevPayload?.vehicles ?? []).map((v) => [v.vehicle_id, v]))
    for (const vehicle of payload.vehicles) {
      const prev = prevVehicles.get(vehicle.vehicle_id)
      if (!prev) {
        if (vehicle.emergency_brake) {
          pushTimelineEvent({
            type: 'vehicle',
            level: 'error',
            title: `${vehicle.vehicle_id} 进入紧急制动`,
            detail: `当前位置 ${Math.round(vehicle.position)} m · 速度 ${Math.round(vehicle.speed)} km/h`,
            source: 'VEHICLE',
            vehicleId: vehicle.vehicle_id,
            at,
            key: `eb:${vehicle.vehicle_id}:true`,
          })
        }
        continue
      }

      if (prev.emergency_brake !== vehicle.emergency_brake) {
        pushTimelineEvent({
          type: 'vehicle',
          level: vehicle.emergency_brake ? 'error' : 'info',
          title: vehicle.emergency_brake
            ? `${vehicle.vehicle_id} 进入紧急制动`
            : `${vehicle.vehicle_id} 解除紧急制动`,
          detail: `当前位置 ${Math.round(vehicle.position)} m · 速度 ${Math.round(vehicle.speed)} km/h`,
          source: 'VEHICLE',
          vehicleId: vehicle.vehicle_id,
          at,
          key: `eb:${vehicle.vehicle_id}:${vehicle.emergency_brake}`,
        })
      }

      if (prev.ma_limit != null && vehicle.ma_limit != null) {
        const shrink = prev.ma_limit - vehicle.ma_limit
        if (shrink >= MA_SHRINK_THRESHOLD) {
          const lastEventAt = recentMaEventAt.get(vehicle.vehicle_id) ?? 0
          if (at - lastEventAt >= MA_EVENT_COOLDOWN_MS) {
            recentMaEventAt.set(vehicle.vehicle_id, at)
            pushTimelineEvent({
              type: 'signal',
              level: 'warn',
              title: `${vehicle.vehicle_id} MA 收缩 ${Math.round(shrink)} m`,
              detail: `当前位置 ${Math.round(vehicle.position)} m · 当前 MA ${Math.round(vehicle.ma_limit)} m`,
              source: 'SIGNAL',
              vehicleId: vehicle.vehicle_id,
              at,
              key: `ma-shrink:${vehicle.vehicle_id}`,
            })
          }
        }
      }
    }
  }

  function handleTick(raw) {
    const payload = normalizeTick(raw)
    if (!payload) return
    const prevPayload = tick.value

    recordTimelineEvents(prevPayload, payload)

    tick.value = payload
    lastTickAt.value = Date.now()
    resetStaleTimer()

    const activeIds = payload.vehicles.map((v) => v.vehicle_id)
    pruneVehicleColors(activeIds)
    recordParkingEvents(payload.vehicles)
    recordOccupancySnapshot(payload.vehicles, totalLength.value)

    if (!selectedVehicleId.value && activeIds.length) {
      selectedVehicleId.value = activeIds[0]
    } else if (selectedVehicleId.value && !activeIds.includes(selectedVehicleId.value)) {
      selectedVehicleId.value = activeIds[0] ?? null
    }

    const label = new Date(payload.timestamp * 1000).toLocaleTimeString('zh-CN', {
      hour12: false,
      minute: '2-digit',
      second: '2-digit',
    })

    timeLabels.value = [...timeLabels.value, label].slice(-HISTORY_LIMIT)

    if (payload.power) {
      voltageHistory.value = [
        ...voltageHistory.value,
        {
          voltage: payload.power.voltage,
          current: payload.power.current,
          power: payload.power.power,
        },
      ].slice(-HISTORY_LIMIT)
    }

    const activeSet = new Set(activeIds)
    for (const id of Object.keys(vehicleHistory.value)) {
      if (!activeSet.has(id)) delete vehicleHistory.value[id]
    }

    for (const vehicle of payload.vehicles) {
      const prev = vehicleHistory.value[vehicle.vehicle_id] ?? []
      vehicleHistory.value[vehicle.vehicle_id] = [
        ...prev,
        { position: vehicle.position, speed: vehicle.speed },
      ].slice(-HISTORY_LIMIT)
    }
  }

  async function connect() {
    await lineLayout.loadLayout()
    await hydrateFromSnapshot()
    wsConnect(handleTick)
  }

  function disconnect() {
    if (staleTimer) clearTimeout(staleTimer)
    stopSnapshotPolling()
    wsDisconnect()
  }

  watch(
    () => [connected.value, connecting.value],
    ([isConnected, isConnecting]) => {
      if (isConnected || isConnecting) {
        stopSnapshotPolling()
        return
      }
      startSnapshotPolling()
    },
    { immediate: true },
  )

  return {
    tick,
    connected,
    connecting,
    lastError,
    lastTickAt,
    dataStale,
    lastControlCommand,
    parkingRecords,
    currentStopErrorCm,
    selectedVehicleId,
    selectedVehicle,
    eventTimeline,
    controlHistory,
    powerTransitions,
    vehicles,
    trackSegments,
    stations,
    totalLength,
    slopeProfile,
    rawBlocks: computed(() => lineLayout.rawBlocks),
    graph: computed(() => lineLayout.graph),
    power,
    alarms,
    systemInfo,
    dataSource,
    protocolVersion,
    signals,
    turnouts,
    systemMode,
    vehicleHistory,
    voltageHistory,
    timeLabels,
    occupancyHistory,
    vehicleColor,
    selectVehicle,
    pushTimelineEvent,
    sendControlCommand,
    hydrateFromSnapshot,
    connect,
    disconnect,
  }
})
