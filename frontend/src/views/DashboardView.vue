<template>
  <div class="space-y-5">
    <!-- 顶栏 -->
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-2xl font-bold tracking-tight">OCC 调度中心</h2>
        <p class="text-sm text-gray-500 mt-1">
          轨道交通 CBTC 仿真系统 · HMI 可视化监控（F5）
        </p>
      </div>
      <div class="flex items-center gap-3">
        <span
          class="inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-full border"
          :class="store.connected
            ? 'border-emerald-700 bg-emerald-950 text-emerald-400'
            : 'border-red-800 bg-red-950 text-red-400'"
        >
          <span
            class="w-2 h-2 rounded-full"
            :class="store.connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'"
          />
          {{ store.connected ? '实时连接 ≤100ms' : '连接中...' }}
        </span>
        <span class="text-xs text-gray-600">系统 {{ store.systemMode }}</span>
        <span v-if="store.dataSource" class="text-xs text-gray-600">· {{ store.dataSource }}</span>
      </div>
    </header>

    <!-- F5.1 全局调度沙盘 -->
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

    <!-- F5.2 受控车数字座舱 -->
    <VehicleCockpit
      :vehicle="store.selectedVehicle"
      :power="store.power"
      :color="store.vehicleColor"
      :stop-error-cm="store.currentStopErrorCm"
      :parking-records="store.parkingRecords"
      :last-control-command="store.lastControlCommand"
    />

    <!-- 全线供电概览 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatusCard label="在线车辆" :value="store.vehicles.length" unit="列" />
      <StatusCard label="接触网电压" :value="store.power?.voltage ?? '--'" unit="V" />
      <StatusCard label="总电流" :value="store.power?.current ?? '--'" unit="A" />
      <StatusCard label="牵引功率" :value="store.power?.power ?? '--'" unit="kW" />
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <AlarmList :alarms="store.alarms" />
      <EventTimeline
        :events="store.eventTimeline"
        :selected-vehicle-id="store.selectedVehicleId"
        :color="store.vehicleColor"
        @select="store.selectVehicle"
      />
    </div>

    <!-- 趋势图表 -->
    <div class="rounded-2xl bg-gray-900 border border-gray-800 p-4">
      <OccupancyTimeline
        :occupancy-history="store.occupancyHistory"
        :time-labels="store.timeLabels"
        :total-length="store.totalLength"
        :stations="store.stations"
      />
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div class="rounded-2xl bg-gray-900 border border-gray-800 p-4">
        <MultiVehicleChart
          :vehicle-history="store.vehicleHistory"
          :time-labels="store.timeLabels"
          :color-fn="store.vehicleColor"
        />
      </div>
      <div class="rounded-2xl bg-gray-900 border border-gray-800 p-4">
        <VoltageChart
          :voltage-history="store.voltageHistory"
          :time-labels="store.timeLabels"
        />
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div class="lg:col-span-1">
        <EnergyTable :vehicles="store.vehicles" :color="store.vehicleColor" />
      </div>
      <div class="lg:col-span-2 rounded-2xl bg-gray-900 border border-gray-800 p-4">
        <PositionChart
          :vehicle-history="store.vehicleHistory"
          :time-labels="store.timeLabels"
          :color-fn="store.vehicleColor"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useSimulationStore } from '@/stores/simulation'
import TrackSandbox from '@/components/TrackSandbox.vue'
import TrackGraphSandbox from '@/components/TrackGraphSandbox.vue'
import TrackLineSchematic from '@/components/TrackLineSchematic.vue'
import VehicleCockpit from '@/components/VehicleCockpit.vue'
import MultiVehicleChart from '@/components/MultiVehicleChart.vue'
import VoltageChart from '@/components/VoltageChart.vue'
import EnergyTable from '@/components/EnergyTable.vue'
import PositionChart from '@/components/PositionChart.vue'
import OccupancyTimeline from '@/components/OccupancyTimeline.vue'
import StatusCard from '@/components/StatusCard.vue'
import AlarmList from '@/components/AlarmList.vue'
import EventTimeline from '@/components/EventTimeline.vue'

const store = useSimulationStore()
const sandboxMode = ref('occ')
</script>
