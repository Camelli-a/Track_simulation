<template>
  <div class="space-y-5">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-xl font-semibold">车辆仿真</h2>
        <p class="text-sm text-gray-500 mt-1">
          多实例动力学解算 · ATP/ATO 状态监控（F2.1 / F2.2 / F4）
        </p>
      </div>
      <ConnectionBadge :connected="store.connected" :data-stale="store.dataStale" />
    </header>

    <PageEmptyState
      v-if="!store.vehicles.length"
      title="等待车辆数据接入"
      description="当前还没有收到列车位置、速度和运行模式数据，因此无法展示目标速度对比、制动曲线和控制历史。"
      next-step="请确认后端仿真正在推送车辆快照，或先返回 OCC 大屏检查实时链路状态。"
    />

    <template v-else>
      <!-- 车辆选择 -->
      <div class="flex flex-wrap gap-2">
        <button
          v-for="v in store.vehicles"
          :key="v.vehicle_id"
          type="button"
          class="px-3 py-1.5 rounded-lg text-sm border transition-all"
          :class="store.selectedVehicleId === v.vehicle_id
            ? 'border-white bg-gray-800 text-white'
            : 'border-gray-700 text-gray-400 hover:border-gray-500'"
          @click="store.selectVehicle(v.vehicle_id)"
        >
          <span class="inline-block w-2 h-2 rounded-full mr-1.5" :style="{ backgroundColor: store.vehicleColor(v.vehicle_id) }" />
          {{ v.vehicle_id }}
        </button>
      </div>

      <div v-if="active" class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="app-panel">
          <div class="flex items-center gap-2 mb-4">
            <span class="w-3 h-3 rounded-full" :style="{ backgroundColor: store.vehicleColor(active.vehicle_id) }" />
            <h3 class="font-semibold">{{ active.vehicle_id }}</h3>
            <span
              class="text-xs px-2 py-0.5 rounded-full"
              :class="active.mode === 'ato' ? 'bg-sky-950 text-sky-400' : 'bg-gray-800 text-gray-400'"
            >{{ modeLabel(active.mode) }}</span>
            <span v-if="active.emergency_brake" class="text-xs px-2 py-0.5 rounded-full bg-red-900 text-red-300 animate-pulse">ATP 紧急制动</span>
          </div>
          <SpeedGauge :speed="active.speed" :limit="active.target_speed ?? 80" />
        </div>

        <div class="lg:col-span-2 space-y-4">
          <div class="grid grid-cols-2 md:grid-cols-3 gap-3 content-start">
            <StatusCard label="速度" :value="active.speed" unit="km/h" />
            <StatusCard label="位置" :value="active.position" unit="m" />
            <StatusCard label="加速度" :value="active.acceleration" unit="m/s²" />
            <StatusCard label="限速" :value="active.target_speed ?? '--'" unit="km/h" />
            <StatusCard label="MA 边界" :value="active.ma_limit ?? '--'" unit="m" />
            <StatusCard label="停车距离" :value="active.stop_distance?.toFixed(1) ?? '--'" unit="m" />
          </div>

          <div class="app-panel">
            <div class="app-section-head">
              <div>
                <p class="app-section-kicker">Manual Control</p>
                <h3 class="app-section-title">手动控车操作</h3>
                <p class="app-section-copy">
                  普通控车动作直接发送，紧急制动会经过轻量确认；所有结果都会写入下方控制历史与全局提示。
                </p>
              </div>
              <span
                class="text-xs px-2 py-0.5 rounded-full"
                :class="active.mode === 'manual'
                  ? 'bg-orange-950 text-orange-300'
                  : 'bg-gray-800 text-gray-400'"
              >
                {{ active.mode === 'manual' ? '当前允许手动控车' : '当前车辆非手动模式' }}
              </span>
            </div>

            <div class="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                class="rounded-xl border border-emerald-700/50 bg-emerald-950/40 px-4 py-2.5 text-sm font-medium text-emerald-200 transition hover:border-emerald-500 disabled:cursor-not-allowed disabled:opacity-45"
                :disabled="!canManualControl"
                @click="sendManualCommand('traction')"
              >
                牵引 +1
              </button>
              <button
                type="button"
                class="rounded-xl border border-amber-700/50 bg-amber-950/40 px-4 py-2.5 text-sm font-medium text-amber-200 transition hover:border-amber-500 disabled:cursor-not-allowed disabled:opacity-45"
                :disabled="!canManualControl"
                @click="sendManualCommand('brake')"
              >
                制动 +1
              </button>
              <button
                type="button"
                class="rounded-xl border border-red-700/50 bg-red-950/40 px-4 py-2.5 text-sm font-medium text-red-200 transition hover:border-red-500 disabled:cursor-not-allowed disabled:opacity-45"
                :disabled="!active"
                @click="sendManualCommand('emergency_brake')"
              >
                紧急制动
              </button>
            </div>

            <div class="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div class="app-metric-tile">
                <p class="app-metric-label">当前模式</p>
                <p class="mt-1 text-gray-200">{{ modeLabel(active.mode) }}</p>
              </div>
              <div class="app-metric-tile">
                <p class="app-metric-label">操作提示</p>
                <p class="mt-1 text-gray-200">{{ canManualControl ? '按钮与键盘控车均已启用' : '请先切换到手动模式再下发普通控车指令' }}</p>
              </div>
              <div class="app-metric-tile">
                <p class="app-metric-label">最近反馈</p>
                <p class="mt-1" :class="lastControlFeedbackClass">{{ lastControlFeedbackText }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <ParkingPrecision
        :current-error="store.currentStopErrorCm"
        :records="store.parkingRecords"
      />

      <div v-if="active" class="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Speed Supervision</p>
              <h3 class="app-section-title">目标速度 vs 实际速度</h3>
              <p class="app-section-copy">用于快速判断当前列车是否超速或存在速度裕量。</p>
            </div>
            <span
              class="text-xs px-2 py-0.5 rounded-full"
              :class="speedDelta >= 0 ? 'bg-red-950 text-red-300' : 'bg-emerald-950 text-emerald-300'"
            >
              {{ speedDelta >= 0 ? `超出 ${speedDelta.toFixed(1)} km/h` : `低于 ${Math.abs(speedDelta).toFixed(1)} km/h` }}
            </span>
          </div>

          <div class="mt-5 grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">实际速度</p>
              <p class="mt-2 text-2xl font-semibold text-white">{{ active.speed }}</p>
              <p class="mt-1 text-xs text-gray-500">km/h</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">目标速度</p>
              <p class="mt-2 text-2xl font-semibold text-sky-300">{{ active.target_speed ?? '--' }}</p>
              <p class="mt-1 text-xs text-gray-500">km/h</p>
            </div>
          </div>

          <div class="mt-4">
            <div class="flex items-center justify-between text-[11px] text-gray-500">
              <span>速度利用率</span>
              <span>{{ speedUsage.toFixed(0) }}%</span>
            </div>
            <div class="mt-2 h-2 rounded-full bg-gray-800 overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-300"
                :class="speedUsage > 100 ? 'bg-red-500' : speedUsage > 85 ? 'bg-amber-400' : 'bg-emerald-400'"
                :style="{ width: `${Math.min(100, speedUsage)}%` }"
              />
            </div>
          </div>
        </div>

        <div class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Movement Authority</p>
              <h3 class="app-section-title">MA 裕量</h3>
              <p class="app-section-copy">衡量列车到当前移动授权边界的剩余安全空间。</p>
            </div>
            <span
              class="text-xs px-2 py-0.5 rounded-full"
              :class="maRemaining != null && maRemaining < 120 ? 'bg-amber-950 text-amber-300' : 'bg-sky-950 text-sky-300'"
            >
              {{ maRemainingText }}
            </span>
          </div>

          <div class="mt-5 grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">当前位置</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ active.position }}</p>
              <p class="mt-1 text-xs text-gray-500">m</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">MA 边界</p>
              <p class="mt-2 text-lg font-semibold text-sky-300">{{ active.ma_limit ?? '--' }}</p>
              <p class="mt-1 text-xs text-gray-500">m</p>
            </div>
          </div>

          <div class="mt-4">
            <div class="flex items-center justify-between text-[11px] text-gray-500">
              <span>授权使用率</span>
              <span>{{ maUsage.toFixed(0) }}%</span>
            </div>
            <div class="mt-2 h-2 rounded-full bg-gray-800 overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-300"
                :class="maUsage > 90 ? 'bg-red-500' : maUsage > 70 ? 'bg-amber-400' : 'bg-sky-400'"
                :style="{ width: `${Math.min(100, maUsage)}%` }"
              />
            </div>
          </div>
        </div>

        <div class="app-panel">
          <p class="app-section-kicker">Command Trace</p>
          <h3 class="app-section-title">最近控制指令历史</h3>
          <p class="app-section-copy">优先显示当前列车的最近操作记录，用于回看控车动作和执行结果。</p>

          <div v-if="!recentControls.length" class="mt-6 rounded-xl border border-dashed border-gray-800 bg-gray-950/40 px-4 py-6 text-sm text-center text-gray-600">
            当前列车还没有控制指令记录
          </div>

          <div v-else class="mt-4 space-y-2">
            <div
              v-for="entry in recentControls"
              :key="entry.id"
              class="rounded-xl border px-4 py-3"
              :class="entry.status === 'error'
                ? 'border-red-900/60 bg-red-950/20'
                : entry.status === 'ok'
                  ? 'border-emerald-900/60 bg-emerald-950/20'
                  : 'border-sky-900/60 bg-sky-950/20'"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="text-sm font-medium text-gray-100">{{ entry.label }}</span>
                <span class="text-[11px]" :class="entry.status === 'error' ? 'text-red-300' : entry.status === 'ok' ? 'text-emerald-300' : 'text-sky-300'">
                  {{ controlStatusLabel(entry.status) }}
                </span>
              </div>
              <p class="mt-1 text-xs text-gray-400">
                {{ entry.vehicleId }} · level {{ entry.level }} · {{ formatTime(entry.at) }}
              </p>
              <p v-if="entry.error" class="mt-2 text-xs text-red-300">
                {{ entry.error }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div v-if="active" class="app-panel-compact">
        <EChartsContainer :option="brakingCurveOption" height="300px" />
      </div>

      <!-- 全车队列 -->
      <div class="app-panel">
        <h3 class="text-sm font-semibold text-gray-300 mb-4">全车队列状态</h3>
        <div class="app-table-shell">
          <table class="app-table">
            <thead>
              <tr>
                <th class="text-left">车辆</th>
                <th class="text-right">模式</th>
                <th class="text-right">速度</th>
                <th class="text-right">位置</th>
                <th class="text-right">加速度</th>
                <th class="text-right">MA</th>
                <th class="text-right">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="v in store.vehicles"
                :key="v.vehicle_id"
                class="cursor-pointer"
                :class="store.selectedVehicleId === v.vehicle_id ? 'bg-gray-800/50' : ''"
                @click="store.selectVehicle(v.vehicle_id)"
              >
                <td>
                  <span class="inline-flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: store.vehicleColor(v.vehicle_id) }" />
                    {{ v.vehicle_id }}
                  </span>
                </td>
                <td class="text-right text-gray-400">{{ modeLabel(v.mode) }}</td>
                <td class="text-right" :class="v.speed > (v.target_speed ?? 80) ? 'text-red-400' : 'text-gray-300'">{{ v.speed }}</td>
                <td class="text-right text-gray-400">{{ v.position }}</td>
                <td class="text-right text-gray-400">{{ v.acceleration }}</td>
                <td class="text-right text-gray-400">{{ v.ma_limit ?? '—' }}</td>
                <td class="text-right">
                  <span v-if="v.emergency_brake" class="text-red-400 text-xs">EB</span>
                  <span v-else class="text-emerald-500 text-xs">运行</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="app-panel-compact">
          <MultiVehicleChart
            :vehicle-history="store.vehicleHistory"
            :time-labels="store.timeLabels"
            :color-fn="store.vehicleColor"
          />
        </div>
        <div class="app-panel-compact">
          <PositionChart
            :vehicle-history="store.vehicleHistory"
            :time-labels="store.timeLabels"
            :color-fn="store.vehicleColor"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { modeLabel } from '@/adapters/simulation'
import { usePageSimulation } from '@/composables/usePageSimulation'
import EChartsContainer from '@/components/EChartsContainer.vue'
import PageEmptyState from '@/components/PageEmptyState.vue'
import StatusCard from '@/components/StatusCard.vue'
import SpeedGauge from '@/components/SpeedGauge.vue'
import MultiVehicleChart from '@/components/MultiVehicleChart.vue'
import PositionChart from '@/components/PositionChart.vue'
import ConnectionBadge from '@/components/ConnectionBadge.vue'
import ParkingPrecision from '@/components/ParkingPrecision.vue'
import { useUiStore } from '@/stores/ui'

const store = usePageSimulation()
const ui = useUiStore()
const active = computed(() => store.selectedVehicle)
const canManualControl = computed(() => active.value?.mode === 'manual')

const speedDelta = computed(() => {
  if (!active.value) return 0
  return active.value.speed - (active.value.target_speed ?? active.value.speed)
})

const speedUsage = computed(() => {
  if (!active.value || !active.value.target_speed) return Math.min(100, active.value?.speed ?? 0)
  return Math.max(0, (active.value.speed / active.value.target_speed) * 100)
})

const maRemaining = computed(() => {
  if (!active.value || active.value.ma_limit == null) return null
  return active.value.ma_limit - active.value.position
})

const maRemainingText = computed(() => {
  if (maRemaining.value == null) return '暂无 MA'
  return `${Math.max(0, maRemaining.value).toFixed(1)} m`
})

const maUsage = computed(() => {
  if (!active.value || active.value.ma_limit == null || active.value.ma_limit <= 0) return 0
  return Math.max(0, (active.value.position / active.value.ma_limit) * 100)
})

const recentControls = computed(() => {
  const all = store.controlHistory
  if (!active.value) return all.slice(0, 8)
  const own = all.filter((entry) => entry.vehicleId === active.value.vehicle_id)
  return (own.length ? own : all).slice(0, 8)
})

const lastControlFeedbackText = computed(() => {
  const latest = recentControls.value[0]
  if (!latest) return '暂未发送控制指令'
  if (latest.status === 'ok') return `${latest.label} 已执行`
  if (latest.status === 'error') return latest.error ?? `${latest.label} 失败`
  return `${latest.label} 发送中`
})

const lastControlFeedbackClass = computed(() => {
  const latest = recentControls.value[0]
  if (!latest) return 'text-gray-400'
  if (latest.status === 'ok') return 'text-emerald-300'
  if (latest.status === 'error') return 'text-red-300'
  return 'text-sky-300'
})

const brakingCurveOption = computed(() => {
  if (!active.value) {
    return {
      title: {
        text: '制动曲线',
        textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
      },
      xAxis: { show: false, type: 'value' },
      yAxis: { show: false, type: 'value' },
      series: [],
    }
  }

  const currentSpeed = Math.max(0, active.value.speed ?? 0)
  const stopDistance = Math.max(
    active.value.stop_distance ?? maRemaining.value ?? 220,
    40,
  )
  const speedMs = currentSpeed / 3.6
  const decel = speedMs > 0
    ? Math.max(0.35, Math.min(1.35, (speedMs * speedMs) / (2 * stopDistance)))
    : 0.45
  const points = []
  const markers = []

  for (let index = 0; index <= 20; index += 1) {
    const distance = (stopDistance / 20) * index
    const remaining = Math.max(0, stopDistance - distance)
    const speed = Math.sqrt(Math.max(0, 2 * decel * remaining)) * 3.6
    points.push([distance.toFixed(1), speed.toFixed(1)])
  }

  markers.push({
    name: '当前速度',
    xAxis: 0,
    yAxis: currentSpeed,
  })

  if (active.value.target_speed != null) {
    markers.push({
      name: '目标速度',
      xAxis: 0,
      yAxis: active.value.target_speed,
    })
  }

  return {
    title: {
      text: '制动曲线估计',
      subtext: `当前速度 ${currentSpeed} km/h · 估计减速度 ${decel.toFixed(2)} m/s²`,
      textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
      subtextStyle: { color: '#6b7280', fontSize: 11 },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      formatter: (params) => {
        const item = params?.[0]
        if (!item) return ''
        return `距离 ${item.value[0]} m<br/>估计速度 ${item.value[1]} km/h`
      },
    },
    grid: { left: 48, right: 20, top: 58, bottom: 36 },
    xAxis: {
      type: 'value',
      name: '制动距离 m',
      min: 0,
      max: Number(stopDistance.toFixed(0)),
      axisLabel: { color: '#6b7280' },
      axisLine: { lineStyle: { color: '#374151' } },
      splitLine: { lineStyle: { color: '#111827' } },
      nameTextStyle: { color: '#6b7280' },
    },
    yAxis: {
      type: 'value',
      name: '速度 km/h',
      axisLabel: { color: '#6b7280' },
      axisLine: { lineStyle: { color: '#374151' } },
      splitLine: { lineStyle: { color: '#1f2937' } },
      nameTextStyle: { color: '#6b7280' },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        data: points,
        symbol: 'none',
        lineStyle: { width: 3, color: '#22d3ee' },
        areaStyle: { color: 'rgba(34, 211, 238, 0.12)' },
        markLine: {
          symbol: 'none',
          data: active.value.target_speed != null ? [
            {
              yAxis: active.value.target_speed,
              lineStyle: { color: '#38bdf8', type: 'dashed' },
              label: { formatter: '目标速度', color: '#7dd3fc' },
            },
          ] : [],
        },
        markPoint: {
          symbol: 'circle',
          symbolSize: 28,
          itemStyle: { color: '#f59e0b' },
          label: { color: '#111827', fontWeight: 'bold' },
          data: markers,
        },
      },
    ],
  }
})

function controlStatusLabel(status) {
  if (status === 'ok') return '已执行'
  if (status === 'error') return '失败'
  return '发送中'
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function sendManualCommand(type) {
  if (!active.value) return

  const vehicleId = active.value.vehicle_id
  const command = { type, level: 1, source: 'panel' }

  if (type !== 'emergency_brake' && !canManualControl.value) {
    ui.showToast({
      type: 'warning',
      title: `${vehicleId} 当前不是手动模式`,
      message: '普通牵引/制动按钮仅对手动模式车辆开放，请先切换车辆或调整模式。',
      duration: 3200,
    })
    return
  }

  if (type === 'emergency_brake') {
    ui.requestConfirm({
      title: `确认对 ${vehicleId} 下发紧急制动？`,
      message: '该动作会立即触发高优先级停车逻辑，建议只在演示异常或安全风险场景下执行。',
      confirmLabel: '执行紧急制动',
      cancelLabel: '取消',
      destructive: true,
      onConfirm: () => store.sendControlCommand(vehicleId, command),
    })
    return
  }

  store.sendControlCommand(vehicleId, command)
}
</script>
