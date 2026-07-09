<template>
  <div class="space-y-5">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-xl font-semibold">轨道仿真</h2>
        <p class="text-sm text-gray-500 mt-1">
          电子地图 · {{ store.stations.length }} 站 · 全长 {{ (store.totalLength/1000).toFixed(1) }} km（线路数据.xls）
        </p>
      </div>
      <ConnectionBadge :connected="store.connected" :data-stale="store.dataStale" />
    </header>

    <div v-if="!store.trackSegments.length" class="text-gray-500">等待轨道数据...</div>

    <template v-else>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatusCard label="线路总长" :value="store.totalLength" unit="m" />
        <StatusCard label="闭塞分区" :value="store.trackSegments.length" unit="个" />
        <StatusCard label="车站数量" :value="store.stations.length" unit="座" />
        <StatusCard
          label="占用分区"
          :value="occupiedCount"
          unit="个"
        />
      </div>

      <!-- 线路沙盘 -->
      <div class="flex justify-end gap-2">
        <button
          type="button"
          class="text-xs px-3 py-1.5 rounded-lg border transition-colors"
          :class="sandboxMode === 'occ'
            ? 'border-sky-600 bg-sky-950 text-sky-300'
            : 'border-gray-700 text-gray-500 hover:text-gray-300'"
          @click="sandboxMode = 'occ'"
        >
          电子地图
        </button>
        <button
          type="button"
          class="text-xs px-3 py-1.5 rounded-lg border transition-colors"
          :class="sandboxMode === 'schematic'
            ? 'border-sky-600 bg-sky-950 text-sky-300'
            : 'border-gray-700 text-gray-500 hover:text-gray-300'"
          @click="sandboxMode = 'schematic'"
        >
          站序图
        </button>
        <button
          type="button"
          class="text-xs px-3 py-1.5 rounded-lg border transition-colors"
          :class="sandboxMode === 'linear'
            ? 'border-sky-600 bg-sky-950 text-sky-300'
            : 'border-gray-700 text-gray-500 hover:text-gray-300'"
          @click="sandboxMode = 'linear'"
        >
          里程展开
        </button>
      </div>

      <TrackGraphSandbox
        v-if="sandboxMode === 'occ'"
        :graph="store.graph"
        :blocks="store.rawBlocks"
        :segments="store.trackSegments"
        :stations="store.stations"
        :turnouts="store.turnouts"
        :signals="store.signals"
        :vehicles="store.vehicles"
        :selected-id="store.selectedVehicleId"
        :total-length="store.totalLength"
        :motion-paused="store.dataStale"
        :color="store.vehicleColor"
        @select="store.selectVehicle"
      />

      <TrackLineSchematic
        v-else-if="sandboxMode === 'schematic'"
        :stations="store.stations"
        :segments="store.trackSegments"
        :vehicles="store.vehicles"
        :total-length="store.totalLength"
        :motion-paused="store.dataStale"
        :selected-id="store.selectedVehicleId"
        :color="store.vehicleColor"
        @select="store.selectVehicle"
      />

      <TrackSandbox
        v-else
        :segments="store.trackSegments"
        :vehicles="store.vehicles"
        :signals="store.signals"
        :turnouts="store.turnouts"
        :stations="store.stations"
        :selected-id="store.selectedVehicleId"
        :total-length="store.totalLength"
        :motion-paused="store.dataStale"
        :layout-loaded="!!store.slopeProfile.length"
        :color="store.vehicleColor"
        @select="store.selectVehicle"
      />

      <!-- 闭塞分区明细 -->
      <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
        <h3 class="text-sm font-semibold text-gray-300 mb-3">闭塞分区状态</h3>
        <SegmentStatusBar :segments="store.trackSegments" />
        <div class="mt-4 overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-xs text-gray-500 border-b border-gray-800">
                <th class="text-left py-2 pr-3">分区</th>
                <th class="text-right py-2 px-2">起止里程</th>
                <th class="text-right py-2 px-2">显示</th>
                <th class="text-right py-2 px-2">占用</th>
                <th class="text-right py-2 pl-2">占用列车</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="seg in store.trackSegments"
                :key="seg.segment_id"
                class="border-b border-gray-800/50 last:border-0"
              >
                <td class="py-2 pr-3 text-gray-300">{{ seg.segment_id }}</td>
                <td class="text-right py-2 px-2 text-gray-400">{{ seg.start }} – {{ seg.end }} m</td>
                <td class="text-right py-2 px-2">
                  <span class="text-xs px-2 py-0.5 rounded-full" :class="aspectBadge(seg)">
                    {{ aspectLabel(seg) }}
                  </span>
                </td>
                <td class="text-right py-2 px-2 text-gray-400">{{ seg.occupied ? '是' : '否' }}</td>
                <td class="text-right py-2 pl-2 text-gray-400">{{ seg.occupied_by ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 车站列表 -->
      <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
        <h3 class="text-sm font-semibold text-gray-300 mb-4">车站与公里标</h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <div
            v-for="st in store.stations"
            :key="st.station_id"
            class="rounded-xl bg-gray-950 border border-gray-800 px-4 py-3 flex items-center justify-between"
          >
            <div>
              <p class="font-medium text-gray-200">{{ st.name }}</p>
              <p class="text-xs text-gray-500 mt-0.5">{{ st.station_id }}</p>
            </div>
            <span class="text-sm font-mono text-sky-400">{{ st.position }} m</span>
          </div>
        </div>
        <p v-if="!store.stations.length" class="text-sm text-gray-600 text-center py-4">暂无车站数据</p>
      </div>

      <div class="rounded-2xl bg-gray-900 border border-gray-800 p-4">
        <OccupancyTimeline
          :occupancy-history="store.occupancyHistory"
          :time-labels="store.timeLabels"
          :total-length="store.totalLength"
          :stations="store.stations"
        />
      </div>

      <div class="rounded-2xl bg-gray-900 border border-gray-800 p-4">
        <TrackProfileChart
          :profile="store.slopeProfile"
          :stations="store.stations"
        />
      </div>

      <div class="rounded-2xl bg-gray-900 border border-gray-800 p-4">
        <EChartsContainer :option="segmentChartOption" height="280px" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { usePageSimulation } from '@/composables/usePageSimulation'
import StatusCard from '@/components/StatusCard.vue'
import TrackSandbox from '@/components/TrackSandbox.vue'
import TrackGraphSandbox from '@/components/TrackGraphSandbox.vue'
import TrackLineSchematic from '@/components/TrackLineSchematic.vue'
import SegmentStatusBar from '@/components/SegmentStatusBar.vue'
import EChartsContainer from '@/components/EChartsContainer.vue'
import ConnectionBadge from '@/components/ConnectionBadge.vue'
import TrackProfileChart from '@/components/TrackProfileChart.vue'
import OccupancyTimeline from '@/components/OccupancyTimeline.vue'

const store = usePageSimulation()
const sandboxMode = ref('occ')

const occupiedCount = computed(() =>
  store.trackSegments.filter((s) => s.occupied).length
)

function aspectLabel(seg) {
  const aspect = seg.aspect ?? (seg.occupied ? 'red' : 'green')
  return { green: '绿灯', yellow: '黄灯', red: '红灯' }[aspect] ?? aspect
}

function aspectBadge(seg) {
  const aspect = seg.aspect ?? (seg.occupied ? 'red' : 'green')
  if (aspect === 'red') return 'bg-red-950 text-red-400'
  if (aspect === 'yellow') return 'bg-yellow-950 text-yellow-400'
  return 'bg-emerald-950 text-emerald-400'
}

const segmentChartOption = computed(() => ({
  title: {
    text: '闭塞分区占用分布',
    textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
  },
  tooltip: {
    backgroundColor: '#1f2937',
    borderColor: '#374151',
    textStyle: { color: '#e5e7eb' },
  },
  grid: { left: 48, right: 16, top: 48, bottom: 32 },
  xAxis: {
    type: 'category',
    data: store.trackSegments.map((s) => s.segment_id),
    axisLabel: { color: '#6b7280', fontSize: 10 },
    axisLine: { lineStyle: { color: '#374151' } },
  },
  yAxis: {
    type: 'value',
    name: '里程 m',
    max: store.totalLength,
    nameTextStyle: { color: '#6b7280' },
    axisLabel: { color: '#6b7280' },
    splitLine: { lineStyle: { color: '#1f2937' } },
  },
  series: [{
    type: 'bar',
    data: store.trackSegments.map((s) => ({
      value: s.end - s.start,
      itemStyle: {
        color: s.occupied ? '#ef4444' : s.aspect === 'yellow' ? '#eab308' : '#10b981',
        opacity: 0.8,
      },
    })),
    barWidth: '60%',
  }],
}))
</script>
