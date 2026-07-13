<template>
  <section class="app-panel">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p class="app-section-kicker">Station Yard</p>
        <h3 class="app-section-title">站场图</h3>
      </div>

      <div class="flex flex-wrap gap-2 text-xs">
        <span class="app-chip">全长 {{ (store.totalLength / 1000).toFixed(1) }} km</span>
        <span class="app-chip">{{ sortedStations.length }} 座车站</span>
        <span class="app-chip">{{ store.vehicles.length }} 列上屏</span>
        <span class="app-chip">{{ managedProcessCount }} 个仿真进程</span>
        <span class="app-chip">{{ store.managedTrains.length }} 列已注册</span>
        <span class="app-chip">{{ runningVehicleCount }} 列在运行</span>
        <span class="app-chip">{{ occupiedCount }} 个占用分区</span>
        <span class="app-chip">{{ deniedRouteCount }} 项进路未通过</span>
      </div>
    </div>

    <PageEmptyState
      v-if="!store.trackSegments.length && !sortedStations.length"
      class="mt-4"
      title="等待站场数据接入"
      description="当前还没有收到车站、区段和站场拓扑快照，因此无法展示站场图。"
      next-step="请确认后端已推送 stations、sections 和 /dashboard/stations/yards；如果后端暂未提供，会回退使用本地线路底座。"
    />

    <template v-else>
      <div class="mt-5 rounded-[1.2rem] border border-white/10 bg-[#050908] px-3 py-3">
        <div class="overflow-x-auto pb-1">
          <div class="flex min-w-max items-center gap-2">
            <button
              v-for="station in stationRanges"
              :key="station.station_id"
              type="button"
              class="group relative rounded-none border px-4 py-2 text-sm font-semibold tracking-[0.18em] transition"
              :class="station.station_id === selectedStationId
                ? 'border-[#65ff65] bg-[#10240f] text-[#8dff8d] shadow-[0_0_18px_rgba(81,255,91,0.18)]'
                : 'border-[#24352f] bg-[#07100d] text-[#6fae73] hover:border-[#4fdc5a] hover:text-[#9dff9d]'"
              @click="selectStation(station.station_id)"
            >
              {{ station.name }}
              <span
                class="absolute -bottom-[9px] left-1/2 h-2 w-px -translate-x-1/2 transition"
                :class="station.station_id === selectedStationId ? 'bg-[#65ff65]' : 'bg-[#24352f]'"
              />
            </button>
          </div>
        </div>
      </div>

      <StationYardPanel
        v-if="selectedStationRange"
        class="mt-4"
        :station="selectedStationRange"
        :range="selectedStationRange"
        :stations="store.stations"
        :segments="store.trackSegments"
        :signals="store.signals"
        :turnouts="store.turnouts"
        :vehicles="store.vehicles"
        :color="store.vehicleColor"
      />
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import PageEmptyState from '@/components/PageEmptyState.vue'
import StationYardPanel from '@/components/StationYardPanel.vue'
import { usePageSimulation } from '@/composables/usePageSimulation'

const store = usePageSimulation()
const selectedStationId = ref(null)

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
  stationRanges.value.find((station) => station.station_id === selectedStationId.value)
  ?? stationRanges.value[0]
  ?? null
)

const runningVehicleCount = computed(() =>
  store.vehicles.filter((vehicle) =>
    vehicle.is_running
    || Number(vehicle.speed ?? 0) > 0
    || vehicle.emergency_brake
  ).length
)

const occupiedCount = computed(() =>
  store.trackSegments.filter((segment) => segment.occupied).length
)

const deniedRouteCount = computed(() =>
  store.routeResults.filter((result) => !result.allowed).length
)

const managedProcessCount = computed(() =>
  store.managedTrains.filter((train) => train.process_running).length
)

watch(
  sortedStations,
  (stations) => {
    if (!stations.length) {
      selectedStationId.value = null
      return
    }

    if (!stations.some((station) => station.station_id === selectedStationId.value)) {
      selectedStationId.value = stations[0].station_id
    }
  },
  { immediate: true },
)

function selectStation(stationId) {
  selectedStationId.value = stationId
}
</script>
