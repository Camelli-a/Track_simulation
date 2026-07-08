<template>
  <div class="space-y-5">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-xl font-semibold">供电仿真</h2>
        <p class="text-sm text-gray-500 mt-1">
          接触网 1500V 直流 · 多车累加能耗与再生制动仿真（F2.3）
        </p>
      </div>
      <ConnectionBadge :connected="store.connected" :data-stale="store.dataStale" />
    </header>

    <PageEmptyState
      v-if="!store.power"
      title="等待供电快照接入"
      description="当前还没有收到接触网电压、电流和功率数据，因此无法判断故障前后波形、分车功率贡献和再生制动回馈占比。"
      next-step="请确认后端已经推送 power 字段；如果只是想看车辆负荷趋势，也可以先在车辆页或 OCC 大屏检查实时列车状态。"
    />

    <template v-else>
      <SelectedVehicleSummary
        :vehicle="store.selectedVehicle"
        :color="store.vehicleColor"
        :insight="selectedVehicleInsight"
        description="当前关注列车会和调度沙盘、事件时间线保持联动，便于判断它对供电负荷的影响。"
      />

      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatusCard label="接触网电压" :value="store.power.voltage.toFixed(1)" unit="V" />
        <StatusCard label="总电流" :value="store.power.current.toFixed(1)" unit="A" />
        <StatusCard label="牵引功率" :value="store.power.power.toFixed(1)" unit="kW" />
        <StatusCard
          label="供电状态"
          :value="store.power.is_fault ? '故障' : '正常'"
        />
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Energy Feedback</p>
              <h3 class="app-section-title">再生制动回馈占比</h3>
              <p class="app-section-copy">按减速度和速度估算当前回馈功率占全网瞬时功率的比例。</p>
            </div>
            <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300">
              {{ regenRatioLabel }}
            </span>
          </div>

          <div class="mt-5">
            <div class="flex items-end justify-between gap-4">
              <div>
                <p class="text-[11px] text-gray-500">估算回馈功率</p>
                <p class="mt-2 text-3xl font-semibold text-emerald-300">{{ regenPowerTotal.toFixed(0) }}</p>
                <p class="mt-1 text-xs text-gray-500">kW</p>
              </div>
              <div class="text-right">
                <p class="text-[11px] text-gray-500">牵引 + 回馈总量</p>
                <p class="mt-2 text-xl font-semibold text-white">{{ combinedPowerTotal.toFixed(0) }}</p>
                <p class="mt-1 text-xs text-gray-500">kW</p>
              </div>
            </div>

            <div class="mt-4 h-3 rounded-full bg-gray-800 overflow-hidden">
              <div
                class="h-full rounded-full bg-gradient-to-r from-emerald-500 to-cyan-400 transition-all duration-300"
                :style="{ width: `${regenRatioPercent}%` }"
              />
            </div>
            <div class="mt-2 flex items-center justify-between text-[11px] text-gray-500">
              <span>回馈占比</span>
              <span>{{ regenRatioPercent.toFixed(0) }}%</span>
            </div>
          </div>

          <div class="mt-4 space-y-2">
            <div
              v-for="entry in regenerativeVehicles"
              :key="`regen-${entry.vehicle_id}`"
              class="rounded-xl border border-emerald-900/40 bg-emerald-950/10 px-3 py-2"
            >
              <div class="flex items-center justify-between gap-3 text-sm">
                <span class="inline-flex items-center gap-2 text-gray-200">
                  <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: store.vehicleColor(entry.vehicle_id) }" />
                  {{ entry.vehicle_id }}
                </span>
                <span class="text-emerald-300">{{ entry.regenPower.toFixed(0) }} kW</span>
              </div>
              <p class="mt-1 text-[11px] text-gray-500">
                速度 {{ entry.speed }} km/h · 加速度 {{ entry.acceleration }} m/s²
              </p>
            </div>
            <div
              v-if="!regenerativeVehicles.length"
              class="rounded-xl border border-dashed border-gray-800 bg-gray-950/40 px-4 py-5 text-center text-sm text-gray-600"
            >
              当前没有处于明显回馈制动状态的车辆
            </div>
          </div>
        </div>

        <div class="lg:col-span-2 rounded-2xl bg-gray-900 border border-gray-800 p-5">
          <div class="flex items-center justify-between gap-3 mb-4">
            <div>
              <h3 class="text-sm font-semibold text-gray-200">分车功率排行</h3>
              <p class="mt-1 text-xs text-gray-500">按瞬时牵引功率估算排序，便于定位当前负荷主因车辆</p>
            </div>
            <span class="text-xs text-gray-500">Top {{ vehiclePowerRanking.length }}</span>
          </div>

          <div v-if="vehiclePowerRanking.length" class="space-y-3">
            <div
              v-for="(entry, index) in vehiclePowerRanking"
              :key="`rank-${entry.vehicle_id}`"
              class="rounded-xl border border-gray-800 bg-gray-950 px-4 py-3"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-3">
                  <span class="flex h-7 w-7 items-center justify-center rounded-full bg-gray-800 text-xs font-semibold text-gray-300">
                    {{ index + 1 }}
                  </span>
                  <span class="inline-flex items-center gap-2 text-sm font-medium text-gray-100">
                    <span class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: store.vehicleColor(entry.vehicle_id) }" />
                    {{ entry.vehicle_id }}
                  </span>
                </div>
                <span class="text-sm font-semibold text-sky-300">{{ entry.power.toFixed(0) }} kW</span>
              </div>

              <div class="mt-3 h-2 rounded-full bg-gray-800 overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-300"
                  :style="{
                    width: `${entry.sharePercent}%`,
                    backgroundColor: store.vehicleColor(entry.vehicle_id),
                  }"
                />
              </div>

              <div class="mt-2 flex items-center justify-between text-[11px] text-gray-500">
                <span>速度 {{ entry.speed }} km/h · 加速度 {{ entry.acceleration }} m/s²</span>
                <span>占总牵引 {{ entry.sharePercent.toFixed(0) }}%</span>
              </div>
            </div>
          </div>

          <div v-else class="rounded-xl border border-dashed border-gray-800 bg-gray-950/40 px-4 py-8 text-center text-sm text-gray-600">
            当前没有可用于估算功率排行的在线车辆
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5 flex flex-col items-center">
          <p class="text-xs text-gray-500 self-start mb-2">网压实时仪表</p>
          <VoltageGauge
            :voltage="store.power.voltage"
            :is-fault="store.power.is_fault"
          />
          <p class="text-xs text-gray-600 mt-2 text-center">
            多车加速时电压跌落 · 再生制动时电压回升
          </p>
        </div>
        <div class="lg:col-span-2 rounded-2xl bg-gray-900 border border-gray-800 p-4">
          <VoltageChart
            :voltage-history="store.voltageHistory"
            :time-labels="store.timeLabels"
          />
        </div>
      </div>

      <!-- 各车能耗贡献 -->
      <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
        <h3 class="text-sm font-semibold text-gray-300 mb-4">各车瞬时牵引负荷估算</h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div
            v-for="v in store.vehicles"
            :key="v.vehicle_id"
            class="rounded-xl bg-gray-950 border border-gray-800 p-4"
          >
            <div class="flex items-center gap-2 mb-3">
              <span class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: store.vehicleColor(v.vehicle_id) }" />
              <span class="font-medium">{{ v.vehicle_id }}</span>
              <span v-if="v.emergency_brake" class="text-[10px] px-1.5 py-0.5 rounded bg-red-900 text-red-300">EB</span>
            </div>
            <div class="space-y-1 text-xs">
              <div class="flex justify-between">
                <span class="text-gray-500">速度</span>
                <span class="text-gray-300">{{ v.speed }} km/h</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">加速度</span>
                <span class="text-gray-300">{{ v.acceleration }} m/s²</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">累计能耗</span>
                <span class="text-gray-300">{{ v.energy_kwh?.toFixed(1) }} kWh</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">估算功率</span>
                <span class="text-sky-400">{{ estimatePower(v).toFixed(0) }} kW</span>
              </div>
            </div>
            <div class="mt-3 h-1.5 rounded-full bg-gray-800 overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-200"
                :style="{
                  width: `${Math.min(100, v.speed)}%`,
                  backgroundColor: store.vehicleColor(v.vehicle_id),
                }"
              />
            </div>
          </div>
        </div>
        <p v-if="!store.vehicles.length" class="text-sm text-gray-600 text-center py-6">暂无在线车辆</p>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div class="app-panel-compact">
          <EChartsContainer :option="powerBreakdownOption" height="260px" />
        </div>
        <div class="app-panel-compact">
          <EChartsContainer :option="powerTransitionOption" height="260px" />
        </div>
      </div>

      <div class="app-panel">
        <div class="app-section-head mb-4">
          <div>
            <p class="app-section-kicker">Fault Replay</p>
            <h3 class="app-section-title">故障前后电压对比</h3>
            <p class="app-section-copy">记录故障触发和恢复瞬间的电压、电流快照，便于复盘影响范围。</p>
          </div>
          <span class="text-xs text-gray-500">最近 {{ store.powerTransitions.length }} 次</span>
        </div>

        <div v-if="store.powerTransitions.length" class="app-table-shell">
          <table class="app-table">
            <thead>
              <tr>
                <th class="text-left">事件</th>
                <th class="text-right">前电压</th>
                <th class="text-right">后电压</th>
                <th class="text-right">电压变化</th>
                <th class="text-right">前电流</th>
                <th class="text-right">后电流</th>
                <th class="text-right">时间</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="transition in store.powerTransitions"
                :key="transition.id"
              >
                <td>
                  <span
                    class="text-xs px-2 py-0.5 rounded-full"
                    :class="transition.type === 'fault'
                      ? 'bg-red-950 text-red-300'
                      : 'bg-emerald-950 text-emerald-300'"
                  >
                    {{ transition.type === 'fault' ? '故障触发' : '故障恢复' }}
                  </span>
                </td>
                <td class="text-right text-gray-400">{{ formatMetric(transition.beforeVoltage, 'V') }}</td>
                <td class="text-right text-gray-300">{{ formatMetric(transition.afterVoltage, 'V') }}</td>
                <td
                  class="text-right"
                  :class="deltaClass(transition.afterVoltage, transition.beforeVoltage)"
                >
                  {{ formatDelta(transition.afterVoltage, transition.beforeVoltage, 'V') }}
                </td>
                <td class="text-right text-gray-400">{{ formatMetric(transition.beforeCurrent, 'A') }}</td>
                <td class="text-right text-gray-300">{{ formatMetric(transition.afterCurrent, 'A') }}</td>
                <td class="text-right text-gray-500">{{ formatTime(transition.at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div
          v-else
          class="rounded-xl border border-dashed border-gray-800 bg-gray-950/40 px-4 py-8 text-center text-sm text-gray-600"
        >
          还没有记录到供电故障或恢复事件，当前正在等待这类状态变化快照
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { usePageSimulation } from '@/composables/usePageSimulation'
import PageEmptyState from '@/components/PageEmptyState.vue'
import StatusCard from '@/components/StatusCard.vue'
import VoltageGauge from '@/components/VoltageGauge.vue'
import VoltageChart from '@/components/VoltageChart.vue'
import EChartsContainer from '@/components/EChartsContainer.vue'
import ConnectionBadge from '@/components/ConnectionBadge.vue'
import SelectedVehicleSummary from '@/components/SelectedVehicleSummary.vue'

const store = usePageSimulation()

function estimatePower(v) {
  return Math.max(0, v.speed * 4.5 + Math.abs(v.acceleration) * 80)
}

function estimateRegenerativePower(v) {
  if (!v) return 0
  if ((v.acceleration ?? 0) >= -0.05 && !v.emergency_brake) return 0
  return Math.max(0, v.speed * 2.2 + Math.abs(v.acceleration) * 140)
}

const selectedVehicleInsight = computed(() => {
  const vehicle = store.selectedVehicle
  if (!vehicle) return ''

  const estPower = estimatePower(vehicle).toFixed(0)
  if (store.power?.is_fault) {
    return `当前接触网处于故障态，${vehicle.vehicle_id} 估算负荷约 ${estPower} kW，建议结合网压波动重点观察该车运行。`
  }
  if (vehicle.emergency_brake) {
    return `${vehicle.vehicle_id} 正在紧急制动，估算负荷约 ${estPower} kW，可关注是否伴随再生制动引起的电压回升。`
  }
  return `${vehicle.vehicle_id} 当前估算牵引负荷约 ${estPower} kW，可结合右侧曲线判断其对总功率变化的贡献。`
})

const vehiclePowerRanking = computed(() => {
  const total = store.vehicles.reduce((sum, vehicle) => sum + estimatePower(vehicle), 0)
  return [...store.vehicles]
    .map((vehicle) => {
      const power = estimatePower(vehicle)
      return {
        ...vehicle,
        power,
        sharePercent: total > 0 ? (power / total) * 100 : 0,
      }
    })
    .sort((a, b) => b.power - a.power)
})

const regenerativeVehicles = computed(() =>
  store.vehicles
    .map((vehicle) => ({
      ...vehicle,
      regenPower: estimateRegenerativePower(vehicle),
    }))
    .filter((vehicle) => vehicle.regenPower > 0)
    .sort((a, b) => b.regenPower - a.regenPower)
)

const regenPowerTotal = computed(() =>
  regenerativeVehicles.value.reduce((sum, vehicle) => sum + vehicle.regenPower, 0)
)

const tractionPowerTotal = computed(() =>
  store.vehicles.reduce((sum, vehicle) => sum + estimatePower(vehicle), 0)
)

const combinedPowerTotal = computed(() =>
  tractionPowerTotal.value + regenPowerTotal.value
)

const regenRatioPercent = computed(() => {
  if (!combinedPowerTotal.value) return 0
  return Math.min(100, (regenPowerTotal.value / combinedPowerTotal.value) * 100)
})

const regenRatioLabel = computed(() => `${regenRatioPercent.value.toFixed(0)}%`)

const powerBreakdownOption = computed(() => ({
  title: {
    text: '多车功率占比',
    textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
  },
  tooltip: {
    trigger: 'item',
    backgroundColor: '#1f2937',
    borderColor: '#374151',
    textStyle: { color: '#e5e7eb' },
  },
  series: [{
    type: 'pie',
    radius: ['40%', '65%'],
    label: { color: '#9ca3af', fontSize: 11 },
    data: store.vehicles.map((v) => ({
      name: v.vehicle_id,
      value: estimatePower(v),
      itemStyle: { color: store.vehicleColor(v.vehicle_id) },
    })),
  }],
}))

const powerTransitionOption = computed(() => ({
  title: {
    text: '故障前后电压对比',
    textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
  },
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#1f2937',
    borderColor: '#374151',
    textStyle: { color: '#e5e7eb' },
  },
  legend: {
    top: 0,
    textStyle: { color: '#9ca3af' },
  },
  grid: { left: 48, right: 20, top: 52, bottom: 32 },
  xAxis: {
    type: 'category',
    data: store.powerTransitions.map((transition, index) =>
      `${transition.type === 'fault' ? '故障' : '恢复'} ${store.powerTransitions.length - index}`
    ),
    axisLabel: { color: '#6b7280', fontSize: 10 },
    axisLine: { lineStyle: { color: '#374151' } },
  },
  yAxis: {
    type: 'value',
    name: '电压 V',
    axisLabel: { color: '#6b7280' },
    nameTextStyle: { color: '#6b7280' },
    splitLine: { lineStyle: { color: '#1f2937' } },
  },
  series: [
    {
      name: '前电压',
      type: 'bar',
      barGap: '20%',
      itemStyle: { color: '#64748b' },
      data: store.powerTransitions.map((transition) => transition.beforeVoltage ?? 0),
    },
    {
      name: '后电压',
      type: 'bar',
      itemStyle: { color: '#38bdf8' },
      data: store.powerTransitions.map((transition) => transition.afterVoltage ?? 0),
    },
  ],
}))

function formatMetric(value, unit) {
  if (value == null) return '—'
  return `${Number(value).toFixed(1)} ${unit}`
}

function formatDelta(after, before, unit) {
  if (after == null || before == null) return '—'
  const delta = after - before
  const prefix = delta > 0 ? '+' : ''
  return `${prefix}${delta.toFixed(1)} ${unit}`
}

function deltaClass(after, before) {
  if (after == null || before == null) return 'text-gray-500'
  const delta = after - before
  if (delta > 0) return 'text-emerald-300'
  if (delta < 0) return 'text-red-300'
  return 'text-gray-400'
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
</script>
