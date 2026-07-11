<template>
  <div class="space-y-5">
    <header class="app-panel">
      <div class="app-section-head">
        <div>
          <p class="app-section-kicker">Power Boundary</p>
          <h2 class="text-xl font-semibold text-slate-100">供电与故障</h2>
          <p class="app-section-copy">
            从网压健康切入，再看回馈制动和分车负荷，最后用故障前后对比表做复盘，避免把供电页做成零散图表堆砌。
          </p>
        </div>
        <ConnectionBadge :connected="store.connected" :data-stale="store.dataStale" />
      </div>
    </header>

    <PageEmptyState
      v-if="!store.power"
      title="等待供电快照接入"
      description="当前还没有收到接触网电压、电流和功率数据，因此无法判断故障前后波形、分车功率贡献和再生制动回馈占比。"
      next-step="请确认后端已经推送 power 字段；如果只是想看车辆负荷趋势，也可以先在列车驾驶室或全线态势页检查实时列车状态。"
    />

    <template v-else>
      <section class="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatusCard label="接触网电压" :value="store.power.voltage.toFixed(1)" unit="V" />
        <StatusCard label="总电流" :value="store.power.current.toFixed(1)" unit="A" />
        <StatusCard label="牵引功率" :value="store.power.power.toFixed(1)" unit="kW" />
        <StatusCard label="供电状态" :value="store.power.is_fault ? '故障' : '正常'" />
      </section>

      <section class="grid grid-cols-1 gap-4 xl:grid-cols-[3fr_1fr]">
        <div class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Voltage Trend</p>
              <h3 class="app-section-title">电压趋势图</h3>
              <p class="app-section-copy">先看网压是否稳定，这是判断供电健康度的第一眼；再结合故障状态和负荷排行分析原因。</p>
            </div>
            <span
              class="rounded-full px-3 py-1 text-xs"
              :class="store.power.is_fault ? 'bg-red-950 text-red-300' : 'bg-emerald-950 text-emerald-300'"
            >
              {{ store.power.is_fault ? '当前存在供电故障' : '当前网压正常' }}
            </span>
          </div>

          <div class="mt-4 rounded-[1.15rem] border border-white/10 bg-black/10 p-4">
            <VoltageChart
              :voltage-history="store.voltageHistory"
              :time-labels="store.timeLabels"
            />
          </div>
        </div>

        <div class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Gauge</p>
              <h3 class="app-section-title">网压实时仪表</h3>
              <p class="app-section-copy">配合趋势图判断此刻是跌落、恢复还是回馈抬升。</p>
            </div>
          </div>

          <div class="mt-4 flex flex-col items-center rounded-[1.15rem] border border-white/10 bg-black/10 px-4 py-4">
            <VoltageGauge
              :voltage="store.power.voltage"
              :is-fault="store.power.is_fault"
            />
            <p class="mt-3 text-center text-xs leading-5 text-slate-500">
              多车加速时电压跌落，再生制动时可能出现局部回升。
            </p>
          </div>
        </div>
      </section>

      <section class="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1.2fr]">
        <article class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Regenerative Braking</p>
              <h3 class="app-section-title">再生制动回馈占比</h3>
              <p class="app-section-copy">按当前减速度与速度估算回馈功率占比，帮助解释网压回升或总负荷回落的来源。</p>
            </div>
            <span class="rounded-full bg-emerald-950 px-3 py-1 text-xs text-emerald-300">
              {{ regenRatioLabel }}
            </span>
          </div>

          <div class="mt-5">
            <div class="flex items-end justify-between gap-4">
              <div>
                <p class="text-[11px] text-slate-500">估算回馈功率</p>
                <p class="mt-2 text-3xl font-semibold text-emerald-300">{{ regenPowerTotal.toFixed(0) }}</p>
                <p class="mt-1 text-xs text-slate-500">kW</p>
              </div>
              <div class="text-right">
                <p class="text-[11px] text-slate-500">牵引 + 回馈总量</p>
                <p class="mt-2 text-xl font-semibold text-white">{{ combinedPowerTotal.toFixed(0) }}</p>
                <p class="mt-1 text-xs text-slate-500">kW</p>
              </div>
            </div>

            <div class="mt-4 h-3 overflow-hidden rounded-full bg-slate-900">
              <div
                class="h-full rounded-full bg-gradient-to-r from-emerald-500 to-cyan-400 transition-all duration-300"
                :style="{ width: `${regenRatioPercent}%` }"
              />
            </div>

            <div class="mt-2 flex items-center justify-between text-[11px] text-slate-500">
              <span>回馈占比</span>
              <span>{{ regenRatioPercent.toFixed(0) }}%</span>
            </div>
          </div>

          <div class="mt-4 space-y-2">
            <div
              v-for="entry in regenerativeVehicles"
              :key="`regen-${entry.vehicle_id}`"
              class="rounded-xl border border-emerald-900/40 bg-emerald-950/10 px-3 py-3"
            >
              <div class="flex items-center justify-between gap-3 text-sm">
                <span class="inline-flex items-center gap-2 text-slate-200">
                  <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: store.vehicleColor(entry.vehicle_id) }" />
                  {{ entry.vehicle_id }}
                </span>
                <span class="text-emerald-300">{{ entry.regenPower.toFixed(0) }} kW</span>
              </div>
              <p class="mt-1 text-[11px] text-slate-500">
                速度 {{ entry.speed }} km/h · 加速度 {{ entry.acceleration }} m/s²
              </p>
            </div>

            <div
              v-if="!regenerativeVehicles.length"
              class="rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-6 text-center text-sm text-slate-500"
            >
              当前没有处于明显回馈制动状态的车辆
            </div>
          </div>
        </article>

        <article class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Vehicle Ranking</p>
              <h3 class="app-section-title">分车功率排行</h3>
              <p class="app-section-copy">按瞬时牵引功率估算排序，定位当前是谁在主导供电负荷变化。</p>
            </div>
            <span class="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-400">
              Top {{ vehiclePowerRanking.length }}
            </span>
          </div>

          <div v-if="vehiclePowerRanking.length" class="mt-4 space-y-3">
            <div
              v-for="(entry, index) in vehiclePowerRanking"
              :key="`rank-${entry.vehicle_id}`"
              class="rounded-[1.05rem] border border-white/10 bg-black/10 px-4 py-4"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-3">
                  <span class="flex h-7 w-7 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-slate-300">
                    {{ index + 1 }}
                  </span>
                  <span class="inline-flex items-center gap-2 text-sm font-medium text-slate-100">
                    <span class="h-2.5 w-2.5 rounded-full" :style="{ backgroundColor: store.vehicleColor(entry.vehicle_id) }" />
                    {{ entry.vehicle_id }}
                  </span>
                </div>
                <span class="text-sm font-semibold text-cyan-300">{{ entry.power.toFixed(0) }} kW</span>
              </div>

              <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-900">
                <div
                  class="h-full rounded-full transition-all duration-300"
                  :style="{
                    width: `${entry.sharePercent}%`,
                    backgroundColor: store.vehicleColor(entry.vehicle_id),
                  }"
                />
              </div>

              <div class="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                <span>速度 {{ entry.speed }} km/h · 加速度 {{ entry.acceleration }} m/s²</span>
                <span>占总牵引 {{ entry.sharePercent.toFixed(0) }}%</span>
              </div>
            </div>
          </div>

          <div
            v-else
            class="mt-4 rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500"
          >
            当前没有可用于估算功率排行的在线车辆
          </div>
        </article>
      </section>

      <section class="app-panel">
        <div class="app-section-head">
          <div>
            <p class="app-section-kicker">Fault Replay</p>
            <h3 class="app-section-title">故障前后电压对比</h3>
            <p class="app-section-copy">记录故障触发和恢复瞬间的电压、电流快照，便于复盘供电波动对全线的影响。</p>
          </div>
          <span class="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-400">
            最近 {{ store.powerTransitions.length }} 次
          </span>
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
                    class="rounded-full px-2 py-0.5 text-xs"
                    :class="transition.type === 'fault'
                      ? 'bg-red-950 text-red-300'
                      : 'bg-emerald-950 text-emerald-300'"
                  >
                    {{ transition.type === 'fault' ? '故障触发' : '故障恢复' }}
                  </span>
                </td>
                <td class="text-right text-slate-400">{{ formatMetric(transition.beforeVoltage, 'V') }}</td>
                <td class="text-right text-slate-300">{{ formatMetric(transition.afterVoltage, 'V') }}</td>
                <td class="text-right" :class="deltaClass(transition.afterVoltage, transition.beforeVoltage)">
                  {{ formatDelta(transition.afterVoltage, transition.beforeVoltage, 'V') }}
                </td>
                <td class="text-right text-slate-400">{{ formatMetric(transition.beforeCurrent, 'A') }}</td>
                <td class="text-right text-slate-300">{{ formatMetric(transition.afterCurrent, 'A') }}</td>
                <td class="text-right text-slate-500">{{ formatTime(transition.at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div
          v-else
          class="mt-4 rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500"
        >
          还没有记录到供电故障或恢复事件，当前正在等待这类状态变化快照。
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { usePageSimulation } from '@/composables/usePageSimulation'
import ConnectionBadge from '@/components/ConnectionBadge.vue'
import PageEmptyState from '@/components/PageEmptyState.vue'
import StatusCard from '@/components/StatusCard.vue'
import VoltageChart from '@/components/VoltageChart.vue'
import VoltageGauge from '@/components/VoltageGauge.vue'

const store = usePageSimulation()

function estimatePower(vehicle) {
  return Math.max(0, vehicle.speed * 4.5 + Math.abs(vehicle.acceleration) * 80)
}

function estimateRegenerativePower(vehicle) {
  if (!vehicle) return 0
  if ((vehicle.acceleration ?? 0) >= -0.05 && !vehicle.emergency_brake) return 0
  return Math.max(0, vehicle.speed * 2.2 + Math.abs(vehicle.acceleration) * 140)
}

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
  if (after == null || before == null) return 'text-slate-500'
  const delta = after - before
  if (delta > 0) return 'text-emerald-300'
  if (delta < 0) return 'text-red-300'
  return 'text-slate-400'
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
