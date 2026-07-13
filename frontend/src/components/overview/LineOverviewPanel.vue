<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Line Overview</p>
        <h3 class="app-section-title">线路主视图</h3>
        <p class="app-section-copy">
          电子地图看全线，站序图看列车与车站分布，并可点击站名下钻站场图。
        </p>
      </div>

      <div class="flex flex-wrap gap-2">
        <button
          v-for="mode in sandboxModes"
          :key="mode.value"
          type="button"
          class="rounded-xl border px-3 py-2 text-xs transition-colors"
          :class="sandboxMode === mode.value
            ? 'border-cyan-400/60 bg-cyan-400/10 text-cyan-100'
            : 'border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-slate-200'"
          @click="setSandboxMode(mode.value)"
        >
          {{ mode.label }}
        </button>
      </div>
    </div>

    <div class="mt-4 flex flex-wrap gap-2 text-xs">
      <span class="app-chip">全长 {{ (store.totalLength / 1000).toFixed(1) }} km</span>
      <span class="app-chip">{{ store.stations.length }} 座车站</span>
      <span class="app-chip">{{ runningVehicleCount }} 列在运行 / {{ store.vehicles.length }} 列已注册</span>
      <span class="app-chip">{{ occupiedCount }} 个占用分区</span>
      <span class="app-chip">{{ deniedRouteCount }} 项进路未通过</span>
      <button
        type="button"
        class="rounded-full border px-3 py-1 transition-colors"
        :class="showAllVehicles
          ? 'border-cyan-400/50 bg-cyan-400/10 text-cyan-100'
          : 'border-white/10 bg-white/[0.03] text-slate-300 hover:border-white/20 hover:bg-white/10'"
        @click="showAllVehicles = !showAllVehicles"
      >
        {{ showAllVehicles ? '仅看运行车辆' : '显示全部注册车辆' }}
      </button>
    </div>

    <PageEmptyState
      v-if="!store.trackSegments.length && !store.stations.length"
      class="mt-4"
      title="等待线路底座数据接入"
      description="当前还没有收到区段、车站和线路拓扑快照，因此无法展示线路主视图和站场下钻。"
      next-step="请确认后端已推送 sections、stations 和线路静态布局；如果连接已建立但这里仍为空，请先检查 line-layout 与实时快照的区段映射。"
    />

    <template v-else>
      <div class="mt-4">
        <TrackGraphSandbox
          v-if="sandboxMode === 'occ'"
          :graph="store.graph"
          :blocks="store.rawBlocks"
          :segments="store.trackSegments"
          :stations="store.stations"
          :turnouts="store.turnouts"
          :signals="store.signals"
          :vehicles="renderedVehicles"
          :selected-id="store.selectedVehicleId"
          :total-length="store.totalLength"
          :motion-paused="store.dataStale"
          :color="store.vehicleColor"
          :line-label="lineLabel"
          @select="store.selectVehicle"
        />

        <TrackLineSchematic
          v-else-if="sandboxMode === 'schematic'"
          :stations="store.stations"
          :segments="store.trackSegments"
          :vehicles="renderedVehicles"
          :total-length="store.totalLength"
          :motion-paused="store.dataStale"
          :selected-id="store.selectedVehicleId"
          :selected-station-id="selectedStationId"
          :color="store.vehicleColor"
          :line-label="lineLabel"
          @select="store.selectVehicle"
          @select-station="toggleStation"
        />

      </div>

      <div
        v-if="sandboxMode === 'schematic'"
        class="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-[1rem] border border-white/10 bg-white/[0.03] px-4 py-3 text-xs"
      >
        <p class="text-slate-400">
          点击站名即可在当前页展开站场，快速核对该站的区段、信号机、道岔和当前列车。
        </p>
        <button
          v-if="selectedStationRange"
          type="button"
          class="rounded-full border border-white/10 px-3 py-1 text-slate-300 transition hover:border-white/20 hover:bg-white/5"
          @click="selectedStationId = null"
        >
          收起 {{ selectedStationRange.name }}
        </button>
      </div>

      <StationYardPanel
        v-if="sandboxMode === 'schematic' && selectedStationRange"
        class="mt-4"
        :station="selectedStationRange"
        :range="selectedStationRange"
        :stations="store.stations"
        :segments="store.trackSegments"
        :signals="store.signals"
        :turnouts="store.turnouts"
        :vehicles="store.vehicles"
        :color="store.vehicleColor"
        @close="selectedStationId = null"
      />
    </template>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import PageEmptyState from '@/components/PageEmptyState.vue'
import StationYardPanel from '@/components/StationYardPanel.vue'
import TrackGraphSandbox from '@/components/TrackGraphSandbox.vue'
import TrackLineSchematic from '@/components/TrackLineSchematic.vue'
import { usePageSimulation } from '@/composables/usePageSimulation'
import { useUiStore } from '@/stores/ui'

const store = usePageSimulation()
const ui = useUiStore()

const sandboxMode = ref('occ')
const selectedStationId = ref(null)
const showAllVehicles = ref(false)

const sandboxModes = [
  { value: 'occ', label: '电子地图' },
  { value: 'schematic', label: '站序图' },
]

const occupiedCount = computed(() =>
  store.trackSegments.filter((segment) => segment.occupied).length
)

const deniedRouteCount = computed(() =>
  store.routeResults.filter((result) => !result.allowed).length
)

const runningVehicles = computed(() =>
  store.vehicles.filter((vehicle) =>
    vehicle.is_running
    || Number(vehicle.speed ?? 0) > 0
    || vehicle.emergency_brake
    || vehicle.vehicle_id === store.selectedVehicleId
  )
)

const renderedVehicles = computed(() =>
  showAllVehicles.value ? store.vehicles : runningVehicles.value
)

const runningVehicleCount = computed(() => runningVehicles.value.length)

const lineLabel = computed(() => store.lineId ?? '线路')

const sortedStations = computed(() =>
  [...store.stations].sort((a, b) => (a.position ?? 0) - (b.position ?? 0))
)

const stationRanges = computed(() =>
  sortedStations.value.map((station, index) => ({
    ...station,
    start: index === 0 ? 0 : ((sortedStations.value[index - 1].position ?? 0) + (station.position ?? 0)) / 2,
    end: index === sortedStations.value.length - 1
      ? store.totalLength
      : ((station.position ?? 0) + (sortedStations.value[index + 1].position ?? store.totalLength)) / 2,
  }))
)

const selectedStationRange = computed(() =>
  stationRanges.value.find((station) => station.station_id === selectedStationId.value) ?? null
)

function toggleStation(stationId) {
  selectedStationId.value = selectedStationId.value === stationId ? null : stationId
}

function setSandboxMode(mode) {
  if (sandboxMode.value === mode) return
  sandboxMode.value = mode
  const label = sandboxModes.find((item) => item.value === mode)?.label ?? mode
  ui.showToast({
    type: 'info',
    title: `已切换到${label}`,
    message: mode === 'schematic'
      ? '此模式下可点击站名查看站场展开。'
      : '当前视角已切换，可继续核对线路态势。',
    duration: 1800,
  })
}
</script>
