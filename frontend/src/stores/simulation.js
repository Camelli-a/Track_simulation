import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { getVehicleColor, pruneVehicleColors } from '@/utils/vehicleColors'
import { normalizeTick, resolveStopErrorCm } from '@/adapters/simulation'
import { normalizeSignalStatus } from '@/adapters/signalApi'
import { fetchDashboardSnapshot, publishTrackInfo } from '@/api/dashboard'
import { getSignalStatus } from '@/api/signal'
import { sendVehicleControl } from '@/api/vehicleControl'
import { getManagedTrains, getVehicleStatus, manageVehicle } from '@/api/vehicle'
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
const SIGNAL_PROTOCOL_POLL_MS = 4000

function mergeCollectionById(primary = [], overlay = [], primaryId = 'segment_id', overlayId = primaryId) {
  if (!primary.length) return overlay
  if (!overlay.length) return primary

  const map = new Map()
  for (const item of primary) {
    const key = item?.[primaryId] ?? item?.[overlayId]
    if (key == null) continue
    map.set(key, { ...item })
  }
  for (const item of overlay) {
    const key = item?.[overlayId] ?? item?.[primaryId]
    if (key == null) continue
    map.set(key, { ...(map.get(key) ?? {}), ...item })
  }
  return [...map.values()]
}

function applyAuthorityToVehicle(vehicle, authority) {
  if (!authority) return vehicle
  return {
    ...vehicle,
    ma_limit: authority.ma_limit ?? vehicle.ma_limit,
    distance_to_ma: authority.distance_to_ma ?? vehicle.distance_to_ma ?? null,
    permission: authority.permission ?? vehicle.permission ?? null,
    signal_state: authority.signal_state ?? vehicle.signal_state ?? null,
    speed_limit: authority.speed_limit ?? vehicle.speed_limit ?? null,
    target_speed: authority.target_speed ?? vehicle.target_speed,
    ma_route_id: authority.route_id ?? vehicle.ma_route_id ?? null,
    ma_permission: authority.permission ?? vehicle.ma_permission ?? null,
    ma_signal_state: authority.signal_state ?? vehicle.ma_signal_state ?? null,
    ma_speed_limit: authority.speed_limit ?? vehicle.ma_speed_limit ?? null,
    ma_reason: authority.reason ?? vehicle.ma_reason ?? null,
    ma_front_vehicle_id: authority.front_vehicle_id ?? vehicle.ma_front_vehicle_id ?? null,
    ma_front_train_length: authority.front_train_length ?? vehicle.ma_front_train_length ?? null,
    ma_location_uncertainty: authority.location_uncertainty ?? vehicle.ma_location_uncertainty ?? null,
    ma_communication_margin: authority.communication_margin ?? vehicle.ma_communication_margin ?? null,
    ma_safety_margin: authority.safety_margin ?? vehicle.ma_safety_margin ?? null,
    ma_front_protection_point: authority.front_protection_point ?? vehicle.ma_front_protection_point ?? null,
    ma_safe_distance: authority.safe_distance ?? vehicle.ma_safe_distance ?? null,
    ma_current_speed: authority.current_speed ?? vehicle.ma_current_speed ?? null,
    ma_route_speed_limit: authority.route_speed_limit ?? vehicle.ma_route_speed_limit ?? null,
    ma_required_stop_distance: authority.required_stop_distance ?? vehicle.ma_required_stop_distance ?? null,
    ma_emergency_stop_distance: authority.emergency_stop_distance ?? vehicle.ma_emergency_stop_distance ?? null,
    ma_warning_distance: authority.warning_distance ?? vehicle.ma_warning_distance ?? null,
    ma_braking_curve_speed_limit: authority.braking_curve_speed_limit ?? vehicle.ma_braking_curve_speed_limit ?? null,
    ma_braking_model: authority.braking_model ?? vehicle.ma_braking_model ?? null,
  }
}

function toEpochMs(value) {
  if (value == null) return null
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return null
  return numeric > 1e12 ? numeric : numeric * 1000
}

function normalizeManagedTrain(train = {}) {
  return {
    vehicle_id: train.vehicle_id ?? null,
    train_index: train.train_index != null ? Number(train.train_index) : null,
    line_id: train.line_id ?? null,
    position: Number(train.position ?? 0),
    speed: Number(train.speed ?? 0),
    acceleration: Number(train.acceleration ?? 0),
    mode: train.mode ?? 'manual',
    is_running: Boolean(train.is_running),
    emergency_brake: Boolean(train.emergency_brake),
    updated_at: train.updated_at ?? null,
  }
}

function normalizeManagedTrainList(payload) {
  if (Array.isArray(payload)) return payload.map(normalizeManagedTrain)
  if (Array.isArray(payload?.trains)) return payload.trains.map(normalizeManagedTrain)
  return []
}

export const useSimulationStore = defineStore('simulation', () => {
  const tick = ref(null)
  const signalProtocol = ref(null)
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
  const managedTrains = ref([])
  const managedTrainsLoading = ref(false)
  const managedTrainsError = ref('')
  const lastManagedSyncAt = ref(0)
  const lastManageAction = ref(null)
  const vehicleManagementMode = ref('unknown')

  const lineLayout = useLineLayoutStore()
  const ui = useUiStore()

  const { connected, connecting, lastError, connect: wsConnect, disconnect: wsDisconnect } =
    useWebSocket('/ws/dashboard')

  let staleTimer = null
  let snapshotPollTimer = null
  let signalProtocolPollTimer = null
  const lastStopState = new Map()
  const recentEventKeys = new Map()
  const recentMaEventAt = new Map()
  let eventCounter = 0
  let controlCounter = 0

  const communication = computed(() => tick.value?.communication ?? null)
  const protocolMessageAt = computed(() => toEpochMs(communication.value?.last_message_at))
  const driverInputs = computed(() => tick.value?.driver_inputs ?? [])
  const atoCommands = computed(() => tick.value?.ato_commands ?? [])

  const maStates = computed(() => {
    if (tick.value?.ma_limits?.length) return tick.value.ma_limits
    return signalProtocol.value?.ma_limits ?? []
  })

  const maStateByVehicleId = computed(() =>
    new Map(maStates.value.map((authority) => [authority.vehicle_id, authority]))
  )

  const vehicles = computed(() =>
    (tick.value?.vehicles ?? []).map((vehicle) =>
      applyAuthorityToVehicle(vehicle, maStateByVehicleId.value.get(vehicle.vehicle_id)),
    )
  )

  const managedTrainById = computed(() =>
    new Map(managedTrains.value.map((train) => [train.vehicle_id, train]))
  )

  const liveVehicleById = computed(() =>
    new Map(vehicles.value.map((vehicle) => [vehicle.vehicle_id, vehicle]))
  )

  const managedOnlyTrains = computed(() =>
    managedTrains.value.filter((train) => !liveVehicleById.value.has(train.vehicle_id))
  )

  const liveOnlyVehicles = computed(() =>
    vehicles.value.filter((vehicle) => !managedTrainById.value.has(vehicle.vehicle_id))
  )

  const selectedVehicle = computed(() =>
    vehicles.value.find((vehicle) => vehicle.vehicle_id === selectedVehicleId.value) ?? null
  )

  const selectedVehicleAuthority = computed(() =>
    selectedVehicle.value
      ? maStateByVehicleId.value.get(selectedVehicle.value.vehicle_id) ?? null
      : null
  )

  const routeResults = computed(() => {
    if (tick.value?.route_results?.length) return tick.value.route_results
    return signalProtocol.value?.route_results ?? []
  })

  const infrastructureSections = computed(() =>
    tick.value?.track_info?.sections?.length
      ? tick.value.track_info.sections
      : lineLayout.infrastructureSections
  )

  const totalLength = computed(() =>
    tick.value?.track_info?.total_length
    || lineLayout.totalLength
    || tick.value?.total_length
    || 5000
  )

  const stations = computed(() => {
    if (tick.value?.track_info?.stations?.length) return tick.value.track_info.stations
    if (lineLayout.stations.length) return lineLayout.stations
    return tick.value?.stations ?? []
  })

  const dynamicTrackSegments = computed(() =>
    mergeCollectionById(
      tick.value?.track_segments ?? [],
      signalProtocol.value?.sections ?? [],
      'segment_id',
      'segment_id',
    )
  )

  const dynamicSignals = computed(() =>
    mergeCollectionById(
      tick.value?.signals ?? [],
      signalProtocol.value?.signals ?? [],
      'signal_id',
      'signal_id',
    )
  )

  const dynamicTurnouts = computed(() =>
    mergeCollectionById(
      tick.value?.turnouts ?? [],
      signalProtocol.value?.switches ?? [],
      'turnout_id',
      'turnout_id',
    )
  )

  const trackSegments = computed(() => {
    const blocks = lineLayout.blocks
    const dynamic = dynamicTrackSegments.value
    const veh = vehicles.value

    if (blocks.length && dynamic.length) {
      return mergeSegments(blocks, dynamic, infrastructureSections.value)
    }
    if (blocks.length) {
      return mergeSegments(
        blocks,
        overlayOccupancy(
          blocks.map((block) => ({ ...block, occupied: false, aspect: 'green', occupied_by: null })),
          veh,
        ),
        infrastructureSections.value,
      )
    }
    return mergeSegments([], dynamic, infrastructureSections.value)
  })

  const signals = computed(() =>
    mergeSignals(lineLayout.signals, dynamicSignals.value)
  )

  const turnouts = computed(() =>
    mergeTurnouts(lineLayout.turnouts, dynamicTurnouts.value)
  )

  const slopeProfile = computed(() => lineLayout.slopeProfile)

  const power = computed(() => tick.value?.power ?? null)
  const alarms = computed(() => tick.value?.alarms ?? [])
  const systemInfo = computed(() => tick.value?.system ?? null)
  const dataSource = computed(() => tick.value?.system?.data_source ?? null)
  const protocolVersion = computed(() => tick.value?.protocol_version ?? null)

  const systemMode = computed(() => {
    const systemMode = tick.value?.system?.system_mode
    if (systemMode) return systemMode
    return tick.value?.system_mode ?? signalProtocol.value?.system_mode ?? 'offline'
  })

  const currentStopErrorCm = computed(() => {
    const vehicle = selectedVehicle.value
    return vehicle ? resolveStopErrorCm(vehicle) : null
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
    const labels = {
      traction: '牵引',
      brake: '制动',
      emergency_brake: '紧急制动',
      emergency_stop: '紧急制动',
      ato: 'ATO 目标命令',
    }
    const label = cmd.label ?? labels[cmd.type] ?? cmd.type
    const historyId = recordControlHistory({
      vehicleId,
      label,
      command: cmd.type,
      level: cmd.level ?? 1,
      source: cmd.source ?? 'keyboard',
      direction: cmd.direction ?? 'forward',
      target_speed: cmd.target_speed ?? null,
      target_position: cmd.target_position ?? null,
      traction_level: cmd.traction_level ?? null,
      brake_level: cmd.brake_level ?? null,
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
        line_id: cmd.line_id ?? 'LINE-1',
        command: cmd.type,
        level: cmd.level ?? 1,
        source: cmd.source ?? 'keyboard',
        direction: cmd.direction ?? 'forward',
        traction_level: cmd.traction_level ?? 0,
        brake_level: cmd.brake_level ?? 0,
        target_speed: cmd.target_speed,
        target_position: cmd.target_position,
        reason: cmd.reason,
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

  async function publishTrackInfoMessage() {
    try {
      const result = await publishTrackInfo()
      ui.showToast({
        type: result?.published ? 'success' : 'warning',
        title: result?.published ? '线路数据已发布' : '线路数据未成功发布',
        message: `topic=${result?.topic ?? 'track_info'} · sections=${result?.section_count ?? 0}`,
        duration: 2600,
      })
      return result
    } catch (err) {
      const errorMessage = err.response?.data?.detail ?? err.message
      ui.showToast({
        type: 'error',
        title: '发布线路数据失败',
        message: errorMessage,
        duration: 3600,
      })
      throw err
    }
  }

  async function hydrateManagedTrains({ silent = false } = {}) {
    if (!silent) managedTrainsLoading.value = true
    managedTrainsError.value = ''
    try {
      const response = await getManagedTrains()
      managedTrains.value = normalizeManagedTrainList(response)
      lastManagedSyncAt.value = Date.now()
      vehicleManagementMode.value = 'full'
      return managedTrains.value
    } catch (err) {
      if (err.response?.status === 404) {
        return hydrateManagedTrainsFromLegacyStatus({ silent })
      }
      managedTrainsError.value = err.response?.data?.detail ?? err.message ?? 'managed_trains_fetch_failed'
      vehicleManagementMode.value = 'unavailable'
      if (!silent) {
        ui.showToast({
          type: 'error',
          title: '车辆管理列表刷新失败',
          message: managedTrainsError.value,
          duration: 3600,
        })
      }
      throw err
    } finally {
      if (!silent) managedTrainsLoading.value = false
    }
  }

  async function hydrateManagedTrainsFromLegacyStatus({ silent = false } = {}) {
    try {
      const legacy = await getVehicleStatus()
      const trains = legacy?.vehicle_id ? [normalizeManagedTrain(legacy)] : []
      managedTrains.value = trains
      lastManagedSyncAt.value = Date.now()
      vehicleManagementMode.value = 'status_fallback'
      managedTrainsError.value = '当前后端未提供 /vehicle/trains，已临时退回旧版 /vehicle/status，因此这里只能看到单车快照，不能做增删管理。'
      return trains
    } catch (legacyErr) {
      managedTrainsError.value = legacyErr.response?.data?.detail ?? legacyErr.message ?? 'vehicle_status_fallback_failed'
      vehicleManagementMode.value = 'unavailable'
      if (!silent) {
        ui.showToast({
          type: 'error',
          title: '车辆列表接口不可用',
          message: managedTrainsError.value,
          duration: 3600,
        })
      }
      throw legacyErr
    }
  }

  async function submitVehicleManage(payload) {
    const type = payload?.type ?? 'unknown'
    const actionLabels = {
      add_train: '添加车辆',
      remove_train: '删除车辆',
      clear_trains: '清空车辆',
      reset_trains: '重置车辆',
    }
    const actionLabel = actionLabels[type] ?? type

    managedTrainsLoading.value = true
    managedTrainsError.value = ''

    try {
      const response = await manageVehicle(payload)
      const ok = Boolean(response?.ok)
      const trains = normalizeManagedTrainList(response)
      if (trains.length || type === 'clear_trains' || (type === 'reset_trains' && Number(payload?.count) === 0)) {
        managedTrains.value = trains
      }
      lastManagedSyncAt.value = Date.now()
      lastManageAction.value = {
        type,
        ok,
        published: Boolean(response?.published),
        topic: response?.topic ?? null,
        result: response?.result ?? null,
        reason: response?.result?.reason ?? response?.reason ?? null,
        at: Date.now(),
      }

      if (!ok) {
        const reason = response?.result?.reason ?? response?.reason ?? `${type}_failed`
        managedTrainsError.value = reason
        ui.showToast({
          type: 'warning',
          title: `${actionLabel}未完成`,
          message: reason,
          duration: 3400,
        })
        return response
      }

      ui.showToast({
        type: response?.published === false ? 'warning' : 'success',
        title: `${actionLabel}成功`,
        message: buildVehicleManageToastMessage(response),
        duration: 2800,
      })
      return response
    } catch (err) {
      if (err.response?.status === 404) {
        vehicleManagementMode.value = 'status_fallback'
        const missingMessage = '当前后端还没有 /vehicle/manage 接口，所以暂时不能在前端执行添加、删除、清空或重置车辆。请先切换到包含车辆管理接口的新后端分支。'
        managedTrainsError.value = missingMessage
        lastManageAction.value = {
          type,
          ok: false,
          published: false,
          topic: null,
          result: null,
          reason: missingMessage,
          at: Date.now(),
        }
        ui.showToast({
          type: 'warning',
          title: '车辆管理接口未接入',
          message: missingMessage,
          duration: 4200,
        })
        return {
          ok: false,
          reason: 'vehicle_manage_endpoint_missing',
        }
      }
      const errorMessage = err.response?.data?.detail ?? err.message ?? `${type}_failed`
      managedTrainsError.value = errorMessage
      lastManageAction.value = {
        type,
        ok: false,
        published: false,
        topic: null,
        result: null,
        reason: errorMessage,
        at: Date.now(),
      }
      ui.showToast({
        type: 'error',
        title: `${actionLabel}失败`,
        message: errorMessage,
        duration: 3600,
      })
      throw err
    } finally {
      managedTrainsLoading.value = false
    }
  }

  function recordParkingEvents(vehicleList) {
    for (const vehicle of vehicleList) {
      const err = resolveStopErrorCm(vehicle)
      const prev = lastStopState.get(vehicle.vehicle_id)
      const isStopping = err != null

      if (isStopping && !prev?.wasStopping && err <= 50) {
        parkingRecords.value = [
          ...parkingRecords.value,
          {
            vehicleId: vehicle.vehicle_id,
            station: vehicle.station_name ?? '未知站',
            errorCm: err,
            at: Date.now(),
          },
        ].slice(-PARKING_RECORD_LIMIT)
      }
      lastStopState.set(vehicle.vehicle_id, { wasStopping: isStopping, err })
    }
  }

  function recordOccupancySnapshot(vehicleList, lengthM) {
    const total = lengthM || lineLayout.totalLength || 47500
    const binSize = total / OCCUPANCY_BINS
    const bins = new Array(OCCUPANCY_BINS).fill(0)

    for (let i = 0; i < OCCUPANCY_BINS; i += 1) {
      const start = i * binSize
      const end = (i + 1) * binSize
      const occupied = vehicleList.some((vehicle) => vehicle.position >= start && vehicle.position < end)
      if (occupied) {
        bins[i] = 2
        continue
      }
      const near = vehicleList.some(
        (vehicle) => vehicle.position >= start - 250 && vehicle.position < end + 250,
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

  async function hydrateSignalProtocol() {
    try {
      signalProtocol.value = normalizeSignalStatus(await getSignalStatus())
      return true
    } catch (err) {
      console.warn('[Simulation] signal protocol fallback failed', err?.message ?? err)
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

  function startSignalProtocolPolling() {
    if (signalProtocolPollTimer) return
    signalProtocolPollTimer = setInterval(() => {
      hydrateSignalProtocol()
    }, SIGNAL_PROTOCOL_POLL_MS)
  }

  function stopSignalProtocolPolling() {
    if (!signalProtocolPollTimer) return
    clearInterval(signalProtocolPollTimer)
    signalProtocolPollTimer = null
  }

  function effectiveSystemMode(snapshot) {
    const systemMode = snapshot?.system?.system_mode
    if (systemMode) return systemMode
    const status = snapshot?.system?.status
    if (status === 'emergency' || status === 'degraded' || status === 'offline') return status
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
        detail: [alarm.source_label ?? alarm.source, alarm.vehicle_id].filter(Boolean).join(' · '),
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
        detail: [alarm.source_label ?? alarm.source, alarm.vehicle_id].filter(Boolean).join(' · '),
        source: 'ALARM',
        vehicleId: alarm.vehicle_id ?? null,
        at,
        key: `alarm-close:${alarmId}`,
      })
    }

    const prevVehicles = new Map((prevPayload?.vehicles ?? []).map((vehicle) => [vehicle.vehicle_id, vehicle]))
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

    const activeIds = payload.vehicles.map((vehicle) => vehicle.vehicle_id)
    pruneVehicleColors(activeIds)
    recordParkingEvents(vehicles.value.length ? vehicles.value : payload.vehicles)
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
    await Promise.all([
      hydrateFromSnapshot(),
      hydrateSignalProtocol(),
      hydrateManagedTrains({ silent: true }).catch(() => []),
    ])
    startSignalProtocolPolling()
    wsConnect(handleTick)
  }

  function disconnect() {
    if (staleTimer) clearTimeout(staleTimer)
    stopSnapshotPolling()
    stopSignalProtocolPolling()
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
    selectedVehicleAuthority,
    eventTimeline,
    controlHistory,
    powerTransitions,
    managedTrains,
    managedTrainsLoading,
    managedTrainsError,
    lastManagedSyncAt,
    lastManageAction,
    managedOnlyTrains,
    liveOnlyVehicles,
    vehicleManagementMode,
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
    communication,
    protocolMessageAt,
    driverInputs,
    atoCommands,
    routeResults,
    maStates,
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
    publishTrackInfoMessage,
    hydrateManagedTrains,
    submitVehicleManage,
    hydrateFromSnapshot,
    connect,
    disconnect,
  }
})

function buildVehicleManageToastMessage(response) {
  const topic = response?.topic ? `topic=${response.topic}` : null
  const count = Array.isArray(response?.trains) ? `当前 ${response.trains.length} 列` : null
  const published = response?.published === false ? '消息总线未发布' : null
  return [count, topic, published].filter(Boolean).join(' · ') || '车辆列表已刷新'
}
