<template>
  <div class="space-y-5">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-xl font-semibold">信号系统</h2>
        <p class="text-sm text-gray-500 mt-1">
          闭塞联锁 · 移动授权 MA · 道岔控制（F1.2 / F1.3）
        </p>
      </div>
      <ConnectionBadge :connected="store.connected" :data-stale="store.dataStale" />
    </header>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatusCard label="系统模式" :value="store.systemMode" />
      <StatusCard label="闭塞分区" :value="store.trackSegments.length" unit="个" />
      <StatusCard label="信号机" :value="store.signals.length" unit="架" />
      <StatusCard label="道岔" :value="store.turnouts.length" unit="组" />
    </div>

    <!-- 闭塞分区条 -->
    <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
      <h3 class="text-sm font-semibold text-gray-300 mb-3">闭塞分区联锁状态</h3>
      <SegmentStatusBar :segments="store.trackSegments" />
    </div>

    <!-- 信号机 -->
    <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
      <h3 class="text-sm font-semibold text-gray-300 mb-4">沿线信号机</h3>
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <div
          v-for="light in store.signals"
          :key="light.signal_id"
          class="rounded-xl bg-gray-950 border border-gray-800 p-3 flex flex-col items-center gap-2"
        >
          <div class="flex flex-col items-center gap-1 py-1 px-2 rounded-lg bg-gray-900">
            <span class="w-3 h-3 rounded-full" :class="light.state === 'red' ? 'bg-red-500 shadow-[0_0_6px_#ef4444]' : 'bg-red-900/30'" />
            <span class="w-3 h-3 rounded-full" :class="light.state === 'yellow' ? 'bg-yellow-400 shadow-[0_0_6px_#facc15]' : 'bg-yellow-900/20'" />
            <span class="w-3 h-3 rounded-full" :class="light.state === 'green' ? 'bg-green-500 shadow-[0_0_6px_#22c55e]' : 'bg-green-900/20'" />
          </div>
          <span class="text-xs text-gray-300">{{ light.signal_id }}</span>
          <span class="text-[10px] text-gray-500">{{ light.position }} m</span>
        </div>
      </div>
    </div>

    <!-- 道岔 -->
    <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
      <h3 class="text-sm font-semibold text-gray-300 mb-4">道岔锁闭状态</h3>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-xs text-gray-500 border-b border-gray-800">
              <th class="text-left py-2 pr-3">道岔</th>
              <th class="text-right py-2 px-2">位置</th>
              <th class="text-right py-2 px-2">状态</th>
              <th class="text-right py-2 pl-2">锁闭</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="t in store.turnouts"
              :key="t.turnout_id"
              class="border-b border-gray-800/50 last:border-0"
            >
              <td class="py-2.5 pr-3 text-gray-300">{{ t.turnout_id }}</td>
              <td class="text-right py-2.5 px-2 text-gray-400">{{ t.position }} m</td>
              <td class="text-right py-2.5 px-2">
                <span :class="t.state === 'reverse' ? 'text-purple-400' : 'text-gray-300'">
                  {{ t.state === 'reverse' ? '反位' : '定位' }}
                </span>
              </td>
              <td class="text-right py-2.5 pl-2">
                <span :class="t.locked ? 'text-amber-400' : 'text-gray-500'">
                  {{ t.locked ? '锁闭' : '解锁' }}
                </span>
              </td>
            </tr>
            <tr v-if="!store.turnouts.length">
              <td colspan="4" class="py-6 text-center text-gray-600">暂无道岔数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- MA 移动授权 -->
    <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
      <h3 class="text-sm font-semibold text-gray-300 mb-4">各车移动授权（MA）</h3>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-xs text-gray-500 border-b border-gray-800">
              <th class="text-left py-2 pr-3">车辆</th>
              <th class="text-right py-2 px-2">当前位置</th>
              <th class="text-right py-2 px-2">MA 终点</th>
              <th class="text-right py-2 px-2">授权长度</th>
              <th class="text-right py-2 pl-2">剩余距离</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="v in store.vehicles"
              :key="v.vehicle_id"
              class="border-b border-gray-800/50 last:border-0"
            >
              <td class="py-2.5 pr-3">
                <span class="inline-flex items-center gap-2">
                  <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: store.vehicleColor(v.vehicle_id) }" />
                  {{ v.vehicle_id }}
                </span>
              </td>
              <td class="text-right py-2.5 px-2 text-gray-400">{{ v.position }} m</td>
              <td class="text-right py-2.5 px-2 text-gray-300">{{ v.ma_limit ?? '—' }} m</td>
              <td class="text-right py-2.5 px-2 text-sky-400">
                {{ maLength(v) }}
              </td>
              <td class="text-right py-2.5 pl-2 text-gray-400">
                {{ v.ma_limit != null ? (v.ma_limit - v.position).toFixed(1) + ' m' : '—' }}
              </td>
            </tr>
            <tr v-if="!store.vehicles.length">
              <td colspan="5" class="py-6 text-center text-gray-600">暂无列车 MA 数据</td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- MA 可视化条 -->
      <div class="mt-4 space-y-2">
        <div v-for="v in store.vehicles" :key="`ma-bar-${v.vehicle_id}`" class="flex items-center gap-3">
          <span class="text-xs text-gray-500 w-10 shrink-0">{{ v.vehicle_id }}</span>
          <div class="flex-1 h-2 rounded-full bg-gray-800 relative overflow-hidden">
            <div
              class="absolute h-full rounded-full opacity-60"
              :style="maBarStyle(v)"
            />
            <div
              class="absolute w-1.5 h-full bg-white rounded-full -translate-x-1/2"
              :style="{ left: `${(v.position / store.totalLength) * 100}%` }"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { usePageSimulation } from '@/composables/usePageSimulation'
import StatusCard from '@/components/StatusCard.vue'
import SegmentStatusBar from '@/components/SegmentStatusBar.vue'
import ConnectionBadge from '@/components/ConnectionBadge.vue'

const store = usePageSimulation()

function maLength(v) {
  if (v.ma_limit == null) return '—'
  return `${(v.ma_limit - v.position).toFixed(1)} m`
}

function maBarStyle(v) {
  if (v.ma_limit == null) return {}
  const left = (v.position / store.totalLength) * 100
  const width = ((v.ma_limit - v.position) / store.totalLength) * 100
  return {
    left: `${left}%`,
    width: `${Math.max(0, width)}%`,
    backgroundColor: store.vehicleColor(v.vehicle_id),
  }
}
</script>
