<template>
  <section class="app-panel space-y-5">
    <!-- 标题 -->
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Driver Console</p>
        <h3 class="app-section-title">司机台状态</h3>
        <p class="app-section-copy">
          来自司机台 PLC 的实时下行帧解析（100 ms/次）。
          字段来自 <code class="text-cyan-400/80">GET /api/v1/vehicle/driver-desk</code>。
        </p>
      </div>
      <div class="flex items-center gap-2">
        <span
          class="rounded-full px-3 py-1 text-xs"
          :class="isConnected ? 'bg-emerald-950 text-emerald-300' : 'bg-slate-800 text-slate-400'"
        >
          {{ isConnected ? 'PLC 在线' : 'PLC 离线 / 无数据' }}
        </span>
        <span v-if="data" class="text-xs text-slate-500">{{ sourceLabel }}</span>
        <span v-if="data?.is_stale" class="rounded-full bg-amber-950 px-2 py-0.5 text-[11px] text-amber-300">
          数据过期
        </span>
      </div>
    </div>

    <!-- 无数据占位 -->
    <div
      v-if="!data && !loading"
      class="rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500"
    >
      暂无司机台数据。<br>
      <span class="text-xs">DATA_SOURCE=zmq 且 PLC 在线后会自动填充。</span>
    </div>

    <div v-else-if="loading && !data" class="py-4 text-center text-sm text-slate-500">
      加载中...
    </div>

    <template v-else-if="data">
      <!-- 第一行：方向 + 模式 + 紧急按钮 -->
      <div class="grid grid-cols-3 gap-3">
        <div class="app-metric-tile">
          <p class="app-metric-label">方向手柄</p>
          <p class="mt-2 text-lg font-semibold" :class="directionClass">
            {{ directionText }}
          </p>
        </div>
        <div class="app-metric-tile">
          <p class="app-metric-label">控制模式</p>
          <p class="mt-2 text-lg font-semibold" :class="modeClass">
            {{ modeText }}
          </p>
        </div>
        <div class="app-metric-tile">
          <p class="app-metric-label">紧急制动钮</p>
          <p class="mt-2 text-lg font-semibold" :class="data.emergency_button ? 'text-red-400' : 'text-slate-400'">
            {{ data.emergency_button ? '■ 按下' : '○ 正常' }}
          </p>
        </div>
      </div>

      <!-- 第二行：牵引 / 制动级位 + 百分比进度条 -->
      <div class="grid grid-cols-2 gap-3">
        <div class="app-metric-tile space-y-2">
          <p class="app-metric-label">牵引</p>
          <div class="flex items-end gap-2">
            <span class="text-2xl font-semibold text-emerald-300">L{{ data.traction_level }}</span>
            <span class="mb-1 text-xs text-slate-500">/ 4</span>
            <span class="mb-1 ml-auto text-xs text-slate-400">{{ tractionPct }}%</span>
          </div>
          <div class="h-1.5 overflow-hidden rounded-full bg-slate-900">
            <div
              class="h-full rounded-full bg-emerald-500 transition-all duration-300"
              :style="{ width: tractionPct + '%' }"
            />
          </div>
        </div>
        <div class="app-metric-tile space-y-2">
          <p class="app-metric-label">制动</p>
          <div class="flex items-end gap-2">
            <span class="text-2xl font-semibold text-amber-300">L{{ data.brake_level }}</span>
            <span class="mb-1 text-xs text-slate-500">/ 7</span>
            <span class="mb-1 ml-auto text-xs text-slate-400">{{ brakePct }}%</span>
          </div>
          <div class="h-1.5 overflow-hidden rounded-full bg-slate-900">
            <div
              class="h-full rounded-full bg-amber-500 transition-all duration-300"
              :style="{ width: brakePct + '%' }"
            />
          </div>
        </div>
      </div>

      <!-- 第三行：ATO 相关 -->
      <div>
        <p class="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">ATO</p>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatusBadge label="具备 ATO"   :active="data.ato_capable ?? false" />
          <StatusBadge label="ATO 激活"   :active="data.ato_active ?? false"          active-class="text-sky-300" />
          <StatusBadge label="ATO 启动钮" :active="data.ato_start_btn"                active-class="text-cyan-300" />
          <StatusBadge label="自动折返"   :active="data.auto_reverse_active ?? false"  active-class="text-violet-300" />
        </div>
      </div>

      <!-- 第四行：车门 -->
      <div>
        <p class="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">车门</p>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatusBadge label="开左门" :active="data.open_left_door"  active-class="text-amber-300" />
          <StatusBadge label="开右门" :active="data.open_right_door" active-class="text-amber-300" />
          <StatusBadge label="关左门" :active="data.close_left_door" />
          <StatusBadge label="关右门" :active="data.close_right_door" />
        </div>
        <div class="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div class="app-metric-tile py-2">
            <p class="app-metric-label">门模式</p>
            <p class="mt-1 text-sm text-slate-200">{{ doorModeText }}</p>
          </div>
          <StatusBadge label="门关好灯" :active="data.door_closed_light ?? false" active-class="text-emerald-300" />
        </div>
      </div>

      <!-- 第五行：其他指示 -->
      <div>
        <p class="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">其他</p>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatusBadge label="钥匙开关"   :active="data.key_switch ?? true"           active-class="text-emerald-300" />
          <StatusBadge label="高断合"     :active="data.high_voltage_light ?? false"  active-class="text-yellow-300" />
          <StatusBadge label="制动故障灯" :active="data.brake_bad_light ?? false"     active-class="text-red-400" />
          <StatusBadge label="网络故障灯" :active="data.network_fault_light ?? false" active-class="text-red-400" />
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import StatusBadge from './StatusBadge.vue'
import { getAllDriverDesk, getDriverDesk } from '@/api/vehicle'

const props = defineProps({
  /**
   * 要展示的 vehicle_id。
   * 传入时调用 /driver-desk/:id；不传时取 /driver-desk 列表的第一条。
   */
  vehicleId: {
    type: String,
    default: null,
  },
})

// ── 状态 ──────────────────────────────────────────────────────────────────
const data    = ref(null)   // DriverDeskResponse
const loading = ref(false)
let   timer   = null
const POLL_MS = 300         // 300ms 轮询，比 PLC 100ms 帧率适当降频

// ── 拉取逻辑 ─────────────────────────────────────────────────────────────
async function fetchData() {
  try {
    if (props.vehicleId) {
      data.value = await getDriverDesk(props.vehicleId)
    } else {
      const res = await getAllDriverDesk()
      // 取第一条；如果后续有多车需求，可在 VehicleStatusView 里传 vehicleId
      data.value = res?.items?.[0] ?? null
    }
  } catch {
    // 404 或网络错误：保持旧值，不弹 toast（suppressErrorLog 已处理）
  }
}

function startPolling() {
  if (timer) return
  loading.value = true
  fetchData().finally(() => { loading.value = false })
  timer = setInterval(fetchData, POLL_MS)
}

function stopPolling() {
  if (timer) { clearInterval(timer); timer = null }
}

onMounted(startPolling)
onBeforeUnmount(stopPolling)

// vehicleId 变化时立刻重新拉取
watch(() => props.vehicleId, () => fetchData())

// ── 计算属性 ──────────────────────────────────────────────────────────────
const isConnected = computed(() => !!data.value && !data.value.is_stale)

const sourceLabel = computed(() => {
  const src = data.value?.source
  if (src === 'driver_tcp') return '来源：司机台 PLC TCP'
  if (src === 'mock')       return '来源：Mock 模拟'
  if (src === 'udp')        return '来源：UDP'
  return src ? `来源：${src}` : ''
})

const directionText = computed(() => {
  const d = data.value?.direction
  if (d === 'forward')  return '▶ 正向'
  if (d === 'backward' || d === 'reverse') return '◀ 反向'
  if (d === 'neutral')  return '— 中位'
  return d ?? '—'
})
const directionClass = computed(() => {
  const d = data.value?.direction
  if (d === 'forward')  return 'text-emerald-300'
  if (d === 'backward' || d === 'reverse') return 'text-amber-300'
  return 'text-slate-400'
})

const modeText = computed(() => {
  const m = data.value?.control_mode
  if (m === 'ato')    return 'ATO 自动'
  if (m === 'manual') return '手动'
  return m ?? '—'
})
const modeClass = computed(() =>
  data.value?.control_mode === 'ato' ? 'text-sky-300' : 'text-slate-300'
)

const tractionPct = computed(() => {
  if (data.value?.traction_percent != null) return Math.round(data.value.traction_percent)
  return Math.round(((data.value?.traction_level ?? 0) / 4) * 100)
})
const brakePct = computed(() => {
  if (data.value?.brake_percent != null) return Math.round(data.value.brake_percent)
  return Math.round(((data.value?.brake_level ?? 0) / 7) * 100)
})

const doorModeText = computed(() => {
  const m = data.value?.door_mode
  if (m === 'semi_auto') return '半自动'
  if (m === 'auto')      return '自动'
  if (m === 'manual')    return '手动'
  return m ?? '—'
})
</script>
