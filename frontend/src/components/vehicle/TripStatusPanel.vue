<template>
  <section class="app-panel space-y-4">
    <!-- 标题 -->
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Trip Status</p>
        <h3 class="app-section-title">行驶状态</h3>
        <p class="app-section-copy">
          列车当前区间、下一站及剩余距离。
        </p>
      </div>
      <span
        class="rounded-full px-3 py-1 text-xs"
        :class="statusBadgeClass"
      >
        {{ statusLabel }}
      </span>
    </div>

    <!-- 无数据占位 -->
    <div
      v-if="!tripData"
      class="rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500"
    >
      暂无行驶状态数据。<br>
      <span class="text-xs">车辆在线后自动填充。</span>
    </div>

    <template v-else>
      <!-- 区间导向图 -->
      <div class="flex items-center gap-2 rounded-[1.05rem] border border-white/10 bg-white/[0.02] px-4 py-4">
        <!-- 出发站 -->
        <div class="flex min-w-0 flex-1 flex-col items-center gap-1">
          <div
            class="flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold"
            :class="tripData.from_station ? 'bg-slate-700 text-slate-200' : 'bg-slate-800 text-slate-600'"
          >
            {{ fromInitial }}
          </div>
          <p class="max-w-[80px] truncate text-center text-[11px] text-slate-400">
            {{ tripData.from_station ?? '—' }}
          </p>
        </div>

        <!-- 轨道 + 列车位置 -->
        <div class="relative flex flex-1 flex-col items-stretch gap-0.5 px-1">
          <!-- 进度条底 -->
          <div class="relative h-1.5 overflow-hidden rounded-full bg-slate-800">
            <div
              class="absolute inset-y-0 left-0 rounded-full bg-cyan-500 transition-all duration-500"
              :style="{ width: progressPct + '%' }"
            />
          </div>
          <!-- 列车图标 -->
          <div
            class="absolute top-1/2 -translate-y-[calc(50%+6px)] -translate-x-1/2 transition-all duration-500"
            :style="{ left: progressPct + '%' }"
          >
            <span class="text-base" title="列车当前位置">🚃</span>
          </div>
          <!-- 距下一站 -->
          <p class="mt-3 text-center text-[11px] text-slate-500">
            {{ distanceLabel }}
          </p>
        </div>

        <!-- 到达站 -->
        <div class="flex min-w-0 flex-1 flex-col items-center gap-1">
          <div
            class="flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold"
            :class="tripData.to_station ? 'bg-cyan-900/60 text-cyan-200 ring-1 ring-cyan-500/30' : 'bg-slate-800 text-slate-600'"
          >
            {{ toInitial }}
          </div>
          <p class="max-w-[80px] truncate text-center text-[11px] text-slate-300">
            {{ tripData.to_station ?? '—' }}
          </p>
        </div>
      </div>

      <!-- 指标卡 -->
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <article
          v-for="card in metricCards"
          :key="card.label"
          class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-3"
        >
          <p class="app-metric-label">{{ card.label }}</p>
          <p class="mt-1.5 text-base font-semibold leading-none" :class="card.highlight ?? 'text-slate-100'">
            {{ card.value }}
          </p>
          <p v-if="card.hint" class="mt-1 text-xs text-slate-500">{{ card.hint }}</p>
        </article>
      </div>
    </template>
  </section>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useSimulationStore } from '@/stores/simulation'
// ── 接口预留 ──────────────────────────────────────────────────────────
// 后端已实现 /api/v1/vehicle/trip-status/:id
import { getTripStatus } from '@/api/vehicle'
const API_ENABLED = true

const props = defineProps({
  /** 要展示的 vehicle_id；不传时取 simStore.selectedVehicleId */
  vehicleId: {
    type: String,
    default: null,
  },
})

// ── Store ─────────────────────────────────────────────────────────────
const simStore = useSimulationStore()

// ── 数据状态 ──────────────────────────────────────────────────────────
const apiData  = ref(null)   // 未来接口数据落这里
const loading  = ref(false)
let   timer    = null
const POLL_MS  = 1000

// ── 目标车辆 ──────────────────────────────────────────────────────────
const targetVehicleId = computed(() =>
  props.vehicleId ?? simStore.selectedVehicleId ?? null
)

const liveVehicle = computed(() =>
  simStore.vehicles.find((v) => v.vehicle_id === targetVehicleId.value) ?? null
)

const liveAuthority = computed(() =>
  targetVehicleId.value
    ? simStore.maStateByVehicleId?.get(targetVehicleId.value) ?? null
    : null
)

// ── 接口拉取（预留，API_ENABLED=false 时跳过）────────────────────────
async function fetchData() {
  if (!API_ENABLED || !targetVehicleId.value) return
  try {
    apiData.value = await getTripStatus(targetVehicleId.value)
  } catch {
    // 保持旧值
  }
}

function startPolling() {
  if (timer) return
  fetchData()
  timer = setInterval(fetchData, POLL_MS)
}

function stopPolling() {
  if (timer) { clearInterval(timer); timer = null }
}

onMounted(startPolling)
onBeforeUnmount(stopPolling)
watch(targetVehicleId, () => fetchData())

// ── 合并数据：优先接口，降级用 store ─────────────────────────────────
const tripData = computed(() => {
  // 优先已实现的 API 数据
  if (apiData.value) return apiData.value

  const v = liveVehicle.value
  if (!v) return null

  const position = Number(v.position ?? 0)
  const direction = v.direction ?? 'forward'

  // 从 simStore.stations 推断出发站和下一站
  const allStations = simStore.stations ?? []
  const sortedStations = [...allStations].sort((a, b) => (a.position ?? 0) - (b.position ?? 0))

  let fromStation = null
  let toStation   = null
  let distanceToNext = null

  if (sortedStations.length) {
    if (direction === 'reverse' || direction === 'backward') {
      // 反向：找到列车后方（position 更大）最近的站
      const passed = sortedStations.filter((s) => (s.position ?? 0) >= position)
      const ahead  = sortedStations.filter((s) => (s.position ?? 0) <  position)
      fromStation  = passed.length ? passed[0] : null
      toStation    = ahead.length  ? ahead[ahead.length - 1] : null
    } else {
      // 正向：找已经过去（position 更小）的最近站 + 前方最近站
      const passed = sortedStations.filter((s) => (s.position ?? 0) <= position)
      const ahead  = sortedStations.filter((s) => (s.position ?? 0) >  position)
      fromStation  = passed.length ? passed[passed.length - 1] : null
      toStation    = ahead.length  ? ahead[0] : null
    }
    if (toStation?.position != null) {
      distanceToNext = Math.abs(toStation.position - position)
    }
  }

  // 兜底：直接用 vehicle 自带的 station_name（来自 MA）
  const currentStationName = v.station_name ?? null

  // 如果 stations 列表为空，只能用 MA 数据
  const fromName = fromStation?.name ?? fromStation?.station_id ?? (currentStationName ? '当前站' : null)
  const toName   = toStation?.name   ?? toStation?.station_id   ?? v.station_name ?? null

  // 距下一站：优先 ATO/MA 提供的 distance_to_ma，其次自算
  const distFromMa = liveAuthority.value?.distance_to_ma
    ?? v.distance_to_ma
    ?? v.stop_distance
    ?? null

  const resolvedDistance = distFromMa != null ? Number(distFromMa) : distanceToNext

  // 区间总长（用于进度条）
  const segmentLength =
    fromStation?.position != null && toStation?.position != null
      ? Math.abs(toStation.position - fromStation.position)
      : null

  const traveled =
    fromStation?.position != null
      ? Math.abs(position - fromStation.position)
      : null

  return {
    vehicle_id: v.vehicle_id,
    from_station: fromName,
    to_station: toName,
    current_position_m: position,
    distance_to_next_m: resolvedDistance,
    segment_length_m: segmentLength,
    traveled_m: traveled,
    direction,
    speed_kmh: Number(v.speed ?? v.speed_kmh ?? 0),
    is_stopped: Number(v.speed ?? 0) < 0.5,
  }
})

// ── 进度条（0~100） ───────────────────────────────────────────────────
const progressPct = computed(() => {
  const d = tripData.value
  if (!d || d.segment_length_m == null || d.traveled_m == null) return 50
  const pct = (d.traveled_m / Math.max(d.segment_length_m, 1)) * 100
  return Math.min(95, Math.max(5, pct))
})

// ── 状态标签 ──────────────────────────────────────────────────────────
const statusLabel = computed(() => {
  if (!tripData.value) return '无数据'
  if (tripData.value.is_stopped) return '停站中'
  return '运行中'
})

const statusBadgeClass = computed(() =>
  !tripData.value
    ? 'bg-slate-800 text-slate-400'
    : tripData.value.is_stopped
    ? 'bg-amber-950 text-amber-300'
    : 'bg-emerald-950 text-emerald-300'
)

// ── 站名首字（头像用） ────────────────────────────────────────────────
const fromInitial = computed(() => {
  const name = tripData.value?.from_station
  if (!name) return '?'
  return name.slice(-1) // 取最后一个字，中文站名惯例
})

const toInitial = computed(() => {
  const name = tripData.value?.to_station
  if (!name) return '?'
  return name.slice(-1)
})

// ── 距离文字 ─────────────────────────────────────────────────────────
const distanceLabel = computed(() => {
  const dist = tripData.value?.distance_to_next_m
  if (dist == null) return '距下一站：—'
  if (dist < 1000) return `距下一站 ${Math.round(dist)} m`
  return `距下一站 ${(dist / 1000).toFixed(2)} km`
})

// ── 指标卡 ───────────────────────────────────────────────────────────
const metricCards = computed(() => {
  const d = tripData.value
  if (!d) return []

  const distToNext = d.distance_to_next_m
  const distDisplay =
    distToNext == null
      ? '—'
      : distToNext < 1000
      ? `${Math.round(distToNext)} m`
      : `${(distToNext / 1000).toFixed(2)} km`

  const eta =
    distToNext != null && d.speed_kmh > 1
      ? `约 ${Math.ceil((distToNext / 1000) / (d.speed_kmh / 3600) / 60)} 分钟`
      : d.is_stopped
      ? '已停站'
      : '—'

  const directionText =
    d.direction === 'reverse' || d.direction === 'backward'
      ? '◀ 反向'
      : '▶ 正向'

  return [
    {
      label: '下一站',
      value: d.to_station ?? '—',
      hint: `出发：${d.from_station ?? '—'}`,
      highlight: d.to_station ? 'text-cyan-200' : 'text-slate-500',
    },
    {
      label: '剩余距离',
      value: distDisplay,
      hint: distToNext != null ? '至下一站停车点' : '暂无 MA 数据',
      highlight: distToNext != null && distToNext < 200 ? 'text-amber-300' : 'text-slate-100',
    },
    {
      label: '预计到站',
      value: eta,
      hint: d.speed_kmh > 1 ? `当前 ${d.speed_kmh.toFixed(1)} km/h` : '列车静止',
    },
    {
      label: '行驶方向',
      value: directionText,
      hint: `位置 ${Math.round(d.current_position_m)} m`,
    },
  ]
})
</script>
