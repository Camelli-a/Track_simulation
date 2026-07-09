import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { getVehicleColor, pruneVehicleColors } from '@/utils/vehicleColors'
import { normalizeTick, resolveStopErrorCm } from '@/adapters/simulation'
import { sendVehicleControl } from '@/api/vehicleControl'
import {
  mergeSegments,
  overlayOccupancy,
  mergeSignals,
  mergeTurnouts,
} from '@/adapters/lineLayout'
import { useLineLayoutStore } from '@/stores/lineLayout'

const HISTORY_LIMIT = 120
const STALE_MS = 2000
const PARKING_RECORD_LIMIT = 20
const OCCUPANCY_BINS = 48

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

  const lineLayout = useLineLayoutStore()

  const { connected, lastError, connect: wsConnect, disconnect: wsDisconnect } =
    useWebSocket('/ws/dashboard')

  let staleTimer = null
  const lastStopState = new Map()

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

  async function sendControlCommand(vehicleId, cmd) {
    const labels = { traction: '牵引', brake: '制动', emergency_brake: '紧急制动' }
    const label = labels[cmd.type] ?? cmd.type

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
      lastControlCommand.value = {
        ...lastControlCommand.value,
        status: 'ok',
        at: Date.now(),
      }
    } catch (err) {
      lastControlCommand.value = {
        ...lastControlCommand.value,
        status: 'error',
        error: err.response?.data?.detail ?? err.message,
        at: Date.now(),
      }
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

  function handleTick(raw) {
    const payload = normalizeTick(raw)
    if (!payload) return

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
    wsConnect(handleTick)
  }

  function disconnect() {
    if (staleTimer) clearTimeout(staleTimer)
    wsDisconnect()
  }

  return {
    tick,
    connected,
    lastError,
    dataStale,
    lastControlCommand,
    parkingRecords,
    currentStopErrorCm,
    selectedVehicleId,
    selectedVehicle,
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
    sendControlCommand,
    connect,
    disconnect,
  }
})
