/**
 * speedCurve store
 *
 * 连接策略：
 *   1. 优先 WebSocket（ws/speedcurve/{id}）
 *      - 连接时服务端先推送 history 批量（type:"history"）
 *      - 之后 5 Hz 推送单点（type:"point"）
 *   2. WS 不可用时降级为 REST 轮询（1s）
 *
 * 对外暴露：
 *   historyPoints[]  — 最近 MAX_DISPLAY 条 SpeedPoint（用于图表）
 *   currentStatus    — SpeedCurveStatus 快照
 *   predictedPoints[]— 前向预测曲线（按需拉取，不随 WS 更新）
 */
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import {
  getSpeedCurveVehicles,
  getSpeedCurveStatus,
  getSpeedCurveHistory,
  getSpeedCurvePrediction,
} from '@/api/speedCurve'

// 图表最多渲染多少历史点（太多点 ECharts 会卡）
const MAX_DISPLAY = 600
// Store 内部也要限长；否则 WS 持续追加会让页面打开越久越卡。
const MAX_HISTORY_POINTS = 900
// REST 降级轮询间隔
const POLL_INTERVAL_MS = 1000
// WS 重连等待（指数退避上限）
const WS_RECONNECT_BASE_MS = 1000
const WS_RECONNECT_MAX_MS = 16000
// 预测曲线刷新间隔（不需要太频繁）
const PREDICT_INTERVAL_MS = 2000

function buildWsUrl(vehicleId) {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  // 开发时 Vite proxy 会把 /ws/* 转发到后端，生产同理
  return `${protocol}://${location.host}/ws/speedcurve/${vehicleId}`
}

export const useSpeedCurveStore = defineStore('speedCurve', () => {
  // ── 车辆列表 ─────────────────────────────────────────────────────────
  const vehicles = ref([])
  const selectedVehicleId = ref(null)

  // ── 数据 ─────────────────────────────────────────────────────────────
  /** @type {import('vue').Ref<import('@/api/speedCurve').SpeedPoint[]>} */
  const historyPoints = ref([])
  const currentStatus = ref(null)
  const predictedPoints = ref([])
  const showPrediction = ref(true)

  // ── 连接状态 ─────────────────────────────────────────────────────────
  const wsConnected = ref(false)
  const wsConnecting = ref(false)
  /** 'ws' | 'rest' | 'idle' */
  const dataSource = ref('idle')
  const loading = ref(false)
  const error = ref(null)

  // ── 内部 ─────────────────────────────────────────────────────────────
  let ws = null
  let wsReconnectTimer = null
  let wsReconnectDelay = WS_RECONNECT_BASE_MS
  let pollTimer = null
  let predictTimer = null
  let _stopped = false   // stopAll 后阻止自动重连

  // ── 图表用 computed ──────────────────────────────────────────────────
  const displayPoints = computed(() => {
    const pts = historyPoints.value
    return pts.length > MAX_DISPLAY ? pts.slice(-MAX_DISPLAY) : pts
  })

  // ── 车辆选择 ─────────────────────────────────────────────────────────
  function selectVehicle(id) {
    if (selectedVehicleId.value === id) return
    selectedVehicleId.value = id
  }

  // 选车辆时重新建连
  watch(selectedVehicleId, (id) => {
    if (!id) return
    _resetData()
    _startForVehicle(id)
  })

  function _resetData() {
    historyPoints.value = []
    currentStatus.value = null
    predictedPoints.value = []
    error.value = null
  }

  function appendHistoryPoint(point) {
    const pts = historyPoints.value
    const last = pts[pts.length - 1] ?? null
    if (shouldSkipRepeatedStopPoint(point, last)) return
    historyPoints.value = trimHistoryPoints([...pts, point])
  }

  // ── WebSocket ────────────────────────────────────────────────────────
  function _connectWs(vehicleId) {
    _closeWs()
    if (_stopped) return

    wsConnecting.value = true
    wsConnected.value = false

    try {
      ws = new WebSocket(buildWsUrl(vehicleId))
    } catch (err) {
      console.warn('[SpeedCurve] WS 创建失败，降级 REST', err)
      _fallbackToRest(vehicleId)
      return
    }

    ws.onopen = () => {
      wsConnected.value = true
      wsConnecting.value = false
      dataSource.value = 'ws'
      wsReconnectDelay = WS_RECONNECT_BASE_MS
      error.value = null
      // WS 建立后停掉 REST 轮询
      _stopPoll()
    }

    ws.onmessage = (event) => {
      let msg
      try { msg = JSON.parse(event.data) } catch { return }

      if (msg.type === 'history') {
        // 批量历史点（连接时首帧）
        const pts = normalizeHistoryPoints(msg.points ?? [])
        historyPoints.value = trimHistoryPoints(pts)
        // 顺手拉一次预测
        _fetchPredict(vehicleId)
      } else if (msg.type === 'point') {
        // 单点追加
        const pt = msg.point
        if (pt) {
          appendHistoryPoint(pt)
        }
      } else if (msg.type === 'ping') {
        // keepalive，不处理
      }

      // 从最新点更新 currentStatus（省得另发 HTTP）
      _syncStatusFromLatestPoint(vehicleId)
    }

    ws.onerror = () => {
      wsConnected.value = false
      wsConnecting.value = false
    }

    ws.onclose = () => {
      wsConnected.value = false
      wsConnecting.value = false
      if (_stopped) return
      // 断线重连，同时降级 REST 保持数据不断
      if (dataSource.value === 'ws') {
        dataSource.value = 'rest'
        _startPoll(vehicleId)
      }
      _scheduleWsReconnect(vehicleId)
    }
  }

  function _closeWs() {
    if (!ws) return
    ws.onclose = null
    ws.onerror = null
    ws.onmessage = null
    try { ws.close() } catch {}
    ws = null
    wsConnected.value = false
    wsConnecting.value = false
  }

  function _scheduleWsReconnect(vehicleId) {
    if (wsReconnectTimer) clearTimeout(wsReconnectTimer)
    wsReconnectTimer = setTimeout(() => {
      wsReconnectTimer = null
      if (!_stopped && selectedVehicleId.value === vehicleId) {
        _connectWs(vehicleId)
      }
    }, wsReconnectDelay)
    wsReconnectDelay = Math.min(wsReconnectDelay * 2, WS_RECONNECT_MAX_MS)
  }

  // ── REST 降级 ────────────────────────────────────────────────────────
  function _fallbackToRest(vehicleId) {
    dataSource.value = 'rest'
    _startPoll(vehicleId)
  }

  function _startPoll(vehicleId) {
    _stopPoll()
    _fetchRest(vehicleId)
    pollTimer = setInterval(() => _fetchRest(vehicleId), POLL_INTERVAL_MS)
  }

  function _stopPoll() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  }

  async function _fetchRest(vehicleId) {
    try {
      const [statusRes, historyRes] = await Promise.allSettled([
        getSpeedCurveStatus(vehicleId),
        getSpeedCurveHistory(vehicleId, MAX_DISPLAY),
      ])
      if (statusRes.status === 'fulfilled') currentStatus.value = statusRes.value
      if (historyRes.status === 'fulfilled') {
        historyPoints.value = trimHistoryPoints(normalizeHistoryPoints(historyRes.value?.points ?? []))
      }
      error.value = null
    } catch (err) {
      error.value = err.message ?? '数据获取失败'
    }
  }

  // ── 预测曲线（定时拉取，WS/REST 均适用） ───────────────────────────
  function _startPredictTimer(vehicleId) {
    _stopPredictTimer()
    _fetchPredict(vehicleId)
    predictTimer = setInterval(() => _fetchPredict(vehicleId), PREDICT_INTERVAL_MS)
  }

  function _stopPredictTimer() {
    if (predictTimer) { clearInterval(predictTimer); predictTimer = null }
  }

  async function _fetchPredict(vehicleId) {
    if (!vehicleId || !showPrediction.value) return
    try {
      const res = await getSpeedCurvePrediction(vehicleId)
      predictedPoints.value = res?.points ?? []
    } catch {
      // 预测失败静默
    }
  }

  // ── 从最新 SpeedPoint 同步 currentStatus ───────────────────────────
  function _syncStatusFromLatestPoint(vehicleId) {
    const pts = historyPoints.value
    if (!pts.length) return
    const latest = pts[pts.length - 1]
    currentStatus.value = {
      vehicle_id: vehicleId,
      connected: true,
      last_update_at: latest.timestamp,
      history_count: pts.length,
      current_speed_kmh: latest.speed_kmh,
      current_position_m: latest.position_m,
      current_acceleration_mps2: latest.acceleration_mps2,
      current_traction_percent: latest.traction_percent,
      current_brake_percent: latest.brake_percent,
      current_gradient_permille: latest.gradient_permille,
      current_speed_limit_kmh: latest.speed_limit_kmh ?? null,
      emergency_brake: latest.emergency_brake,
      control_mode: latest.control_mode,
      // 额外字段
      traction_level: latest.traction_level,
      brake_level: latest.brake_level,
      traction_force_n: latest.traction_force_n,
      brake_force_n: latest.brake_force_n,
    }
  }

  // ── 顶层启动逻辑 ────────────────────────────────────────────────────
  function _startForVehicle(vehicleId) {
    _connectWs(vehicleId)
    _startPredictTimer(vehicleId)
  }

  // ── 公开 API ────────────────────────────────────────────────────────
  async function fetchVehicles() {
    try {
      const res = await getSpeedCurveVehicles()
      vehicles.value = res?.vehicles ?? []
      if (!selectedVehicleId.value && vehicles.value.length) {
        selectedVehicleId.value = vehicles.value[0]
      }
    } catch {
      // 静默失败
    }
  }

  /** 页面 onMounted 调用 */
  async function startAll() {
    _stopped = false
    await fetchVehicles()
    if (selectedVehicleId.value) {
      _startForVehicle(selectedVehicleId.value)
    }
  }

  /** 页面 onBeforeUnmount 调用 */
  function stopAll() {
    _stopped = true
    _closeWs()
    _stopPoll()
    _stopPredictTimer()
    if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null }
    dataSource.value = 'idle'
  }

  return {
    // state
    vehicles,
    selectedVehicleId,
    currentStatus,
    predictedPoints,
    showPrediction,
    wsConnected,
    wsConnecting,
    dataSource,
    loading,
    error,
    // computed
    displayPoints,
    // actions
    selectVehicle,
    fetchVehicles,
    startAll,
    stopAll,
  }
})

function trimHistoryPoints(points) {
  return points.length > MAX_HISTORY_POINTS ? points.slice(-MAX_HISTORY_POINTS) : points
}

function normalizeHistoryPoints(points) {
  const normalized = []
  let last = null
  for (const point of points) {
    if (!point || shouldSkipRepeatedStopPoint(point, last)) continue
    normalized.push(point)
    last = point
  }
  return normalized
}

function shouldSkipRepeatedStopPoint(point, last) {
  if (!last) return false
  const position = Number(point.position_m)
  const speed = Number(point.speed_kmh)
  const lastPosition = Number(last.position_m)
  const lastSpeed = Number(last.speed_kmh)
  if (![position, speed, lastPosition, lastSpeed].every(Number.isFinite)) return false
  return (
    Math.abs(position - lastPosition) < 0.05
    && Math.abs(speed) < 0.05
    && Math.abs(lastSpeed) < 0.05
  )
}
