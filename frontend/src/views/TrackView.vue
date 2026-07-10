<template>
  <div class="space-y-5">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-xl font-semibold">轨道仿真</h2>
        <p class="text-sm text-gray-500 mt-1">
          电子地图 · {{ store.stations.length }} 站 · 全长 {{ (store.totalLength/1000).toFixed(1) }} km · 拓扑图与协议元数据分层消费
        </p>
      </div>
      <ConnectionBadge :connected="store.connected" :data-stale="store.dataStale" />
    </header>

    <PageEmptyState
      v-if="!store.trackSegments.length"
      title="等待轨道区段数据接入"
      description="当前还没有收到闭塞分区、车站和线路剖面快照，因此无法展示区段占用、按站筛选和异常状态过滤结果。"
      next-step="请确认后端已经推送 sections 与 stations 字段；如果线路图已有内容但表格为空，也可以先检查区段合并映射是否完成。"
    />

    <template v-else>
      <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatusCard label="线路总长" :value="store.totalLength" unit="m" />
        <StatusCard label="闭塞分区" :value="store.trackSegments.length" unit="个" />
        <StatusCard label="车站数量" :value="store.stations.length" unit="座" />
        <StatusCard
          label="占用分区"
          :value="occupiedCount"
          unit="个"
        />
        <StatusCard label="锁闭分区" :value="lockedCount" unit="个" />
      </div>

      <div class="app-panel">
        <div class="app-section-head">
          <div>
            <p class="app-section-kicker">Segment Filter</p>
            <h3 class="app-section-title">区段筛选与按站查看</h3>
            <p class="app-section-copy">按异常状态、所属车站和关键词缩小范围，便于在长线路上快速锁定问题区段。</p>
          </div>
          <span class="text-xs text-gray-500">当前结果 {{ filteredSegments.length }} / {{ store.trackSegments.length }}</span>
        </div>

        <div class="mt-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          <label class="rounded-xl bg-gray-950 border border-gray-800 px-4 py-3">
            <span class="text-[11px] text-gray-500">按站查看</span>
            <select
              v-model="stationFilter"
              class="mt-2 w-full rounded-lg border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-200 outline-none"
            >
              <option value="all">全线</option>
              <option v-for="station in store.stations" :key="station.station_id" :value="station.station_id">
                {{ station.name }}
              </option>
            </select>
          </label>

          <label class="rounded-xl bg-gray-950 border border-gray-800 px-4 py-3">
            <span class="text-[11px] text-gray-500">异常状态筛选</span>
            <select
              v-model="statusFilter"
              class="mt-2 w-full rounded-lg border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-200 outline-none"
            >
              <option value="all">全部区段</option>
              <option value="occupied">仅占用区段</option>
              <option value="yellow">仅黄灯区段</option>
              <option value="red">仅红灯区段</option>
              <option value="abnormal">全部异常区段</option>
            </select>
          </label>

          <label class="rounded-xl bg-gray-950 border border-gray-800 px-4 py-3">
            <span class="text-[11px] text-gray-500">区段关键字</span>
            <input
              v-model.trim="segmentKeyword"
              type="text"
              placeholder="如 121 / ST-08 / BWR"
              class="mt-2 w-full rounded-lg border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-200 outline-none placeholder:text-gray-600"
            >
          </label>

          <div class="rounded-xl bg-gray-950 border border-gray-800 px-4 py-3">
            <span class="text-[11px] text-gray-500">筛选摘要</span>
            <div class="mt-2 space-y-2 text-sm">
              <p class="text-gray-200">{{ activeStationLabel }}</p>
              <p class="text-gray-500">{{ statusFilterLabel }}</p>
              <p class="text-gray-500">{{ segmentKeyword ? `关键词：${segmentKeyword}` : '未输入关键词' }}</p>
            </div>
          </div>
        </div>
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
      <div class="app-panel">
        <h3 class="text-sm font-semibold text-gray-300 mb-3">闭塞分区状态</h3>
        <SegmentStatusBar :segments="filteredSegments.length ? filteredSegments : store.trackSegments" />
        <div class="app-table-shell">
          <table class="app-table">
            <thead>
              <tr>
                <th class="text-left">分区</th>
                <th class="text-right">起止里程</th>
                <th class="text-right">所属区域</th>
                <th class="text-right">协议限速</th>
                <th class="text-right">显示</th>
                <th class="text-right">占用</th>
                <th class="text-right">锁闭 / 进路</th>
                <th class="text-right">占用列车</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="seg in filteredSegments"
                :key="seg.segment_id"
              >
                <td class="text-gray-300">{{ seg.segment_id }}</td>
                <td class="text-right text-gray-400">{{ seg.start }} – {{ seg.end }} m</td>
                <td class="text-right text-gray-400">{{ segmentStationName(seg) }}</td>
                <td class="text-right text-gray-400">{{ seg.speed_limit != null ? `${seg.speed_limit} km/h` : '—' }}</td>
                <td class="text-right">
                  <span class="text-xs px-2 py-0.5 rounded-full" :class="aspectBadge(seg)">
                    {{ aspectLabel(seg) }}
                  </span>
                </td>
                <td class="text-right text-gray-400">{{ seg.occupied ? '是' : '否' }}</td>
                <td class="text-right text-gray-400">
                  {{ seg.locked ? '锁闭' : '—' }}
                  <span v-if="seg.locked_by_route_id"> / {{ seg.locked_by_route_id }}</span>
                </td>
                <td class="text-right text-gray-400">{{ seg.occupied_by ?? '—' }}</td>
              </tr>
              <tr v-if="!filteredSegments.length">
                <td colspan="8" class="py-8 text-center text-gray-600">
                  当前筛选条件下没有匹配的区段，请尝试切回“全部区段”或更换车站范围。
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 车站列表 -->
      <div class="app-panel">
        <h3 class="text-sm font-semibold text-gray-300 mb-4">车站与公里标</h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <div
            v-for="st in filteredStations"
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
        <p v-if="!filteredStations.length" class="text-sm text-gray-600 text-center py-4">当前筛选范围内暂无车站数据</p>
      </div>

      <div class="app-panel-compact">
        <OccupancyTimeline
          :occupancy-history="store.occupancyHistory"
          :time-labels="store.timeLabels"
          :total-length="store.totalLength"
          :stations="filteredStations.length ? filteredStations : store.stations"
        />
      </div>

      <div class="app-panel-compact">
        <TrackProfileChart
          :profile="store.slopeProfile"
          :stations="filteredStations.length ? filteredStations : store.stations"
        />
      </div>

      <div class="app-panel-compact">
        <EChartsContainer :option="segmentChartOption" height="280px" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { usePageSimulation } from '@/composables/usePageSimulation'
import PageEmptyState from '@/components/PageEmptyState.vue'
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
const stationFilter = ref('all')
const statusFilter = ref('all')
const segmentKeyword = ref('')

const occupiedCount = computed(() =>
  store.trackSegments.filter((s) => s.occupied).length
)

const lockedCount = computed(() =>
  store.trackSegments.filter((segment) => segment.locked).length
)

const stationNameById = computed(() =>
  new Map(store.stations.map((station) => [station.station_id, station.name]))
)

const stationRanges = computed(() =>
  store.stations.map((station, index) => ({
    ...station,
    start: index === 0 ? 0 : (store.stations[index - 1].position + station.position) / 2,
    end: index === store.stations.length - 1
      ? store.totalLength
      : (station.position + store.stations[index + 1].position) / 2,
  }))
)

const activeStation = computed(() =>
  stationRanges.value.find((station) => station.station_id === stationFilter.value) ?? null
)

const activeStationLabel = computed(() =>
  activeStation.value ? `范围：${activeStation.value.name}` : '范围：全线'
)

const statusFilterLabel = computed(() => {
  if (statusFilter.value === 'occupied') return '仅显示占用区段'
  if (statusFilter.value === 'yellow') return '仅显示黄灯区段'
  if (statusFilter.value === 'red') return '仅显示红灯区段'
  if (statusFilter.value === 'abnormal') return '显示所有异常区段'
  return '显示全部区段'
})

const filteredSegments = computed(() =>
  store.trackSegments.filter((segment) => {
    if (activeStation.value) {
      if (segment.station_id) {
        if (segment.station_id !== activeStation.value.station_id) return false
      } else {
        const center = ((segment.start ?? 0) + (segment.end ?? 0)) / 2
        if (center < activeStation.value.start || center > activeStation.value.end) {
          return false
        }
      }
    }

    if (statusFilter.value === 'occupied' && !segment.occupied) return false
    if (statusFilter.value === 'yellow' && (segment.aspect ?? (segment.occupied ? 'red' : 'green')) !== 'yellow') return false
    if (statusFilter.value === 'red' && (segment.aspect ?? (segment.occupied ? 'red' : 'green')) !== 'red') return false
    if (statusFilter.value === 'abnormal') {
      const aspect = segment.aspect ?? (segment.occupied ? 'red' : 'green')
      if (!segment.occupied && aspect !== 'yellow' && aspect !== 'red') return false
    }

    if (!segmentKeyword.value) return true

    const keyword = segmentKeyword.value.toLowerCase()
    const stationName = segmentStationName(segment).toLowerCase()
    return String(segment.segment_id).toLowerCase().includes(keyword)
      || String(segment.track_seg_id ?? '').toLowerCase().includes(keyword)
      || stationName.includes(keyword)
      || String(segment.occupied_by ?? '').toLowerCase().includes(keyword)
  })
)

const filteredStations = computed(() => {
  if (activeStation.value) return [activeStation.value]
  if (!segmentKeyword.value) return store.stations
  const keyword = segmentKeyword.value.toLowerCase()
  return store.stations.filter((station) =>
    station.name.toLowerCase().includes(keyword)
    || station.station_id.toLowerCase().includes(keyword)
  )
})

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
    data: filteredSegments.value.map((s) => s.segment_id),
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
    data: filteredSegments.value.map((s) => ({
      value: s.end - s.start,
      itemStyle: {
        color: s.occupied ? '#ef4444' : s.aspect === 'yellow' ? '#eab308' : '#10b981',
        opacity: 0.8,
      },
    })),
    barWidth: '60%',
  }],
}))

function segmentStationName(segment) {
  if (segment.station_id) {
    const stationName = stationNameById.value.get(segment.station_id)
    return stationName ? `${stationName} (${segment.station_id})` : segment.station_id
  }
  const center = ((segment.start ?? 0) + (segment.end ?? 0)) / 2
  const station = stationRanges.value.find((item) => center >= item.start && center <= item.end)
  return station?.name ?? '区间'
}
</script>
