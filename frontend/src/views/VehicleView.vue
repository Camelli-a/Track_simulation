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

    <div v-if="!store.vehicles.length" class="text-gray-500">等待车辆数据...</div>

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
        <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
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

        <div class="lg:col-span-2 grid grid-cols-2 md:grid-cols-3 gap-3 content-start">
          <StatusCard label="速度" :value="active.speed" unit="km/h" />
          <StatusCard label="位置" :value="active.position" unit="m" />
          <StatusCard label="加速度" :value="active.acceleration" unit="m/s²" />
          <StatusCard label="限速" :value="active.target_speed ?? '--'" unit="km/h" />
          <StatusCard label="MA 边界" :value="active.ma_limit ?? '--'" unit="m" />
          <StatusCard label="停车距离" :value="active.stop_distance?.toFixed(1) ?? '--'" unit="m" />
        </div>
      </div>

      <ParkingPrecision
        :current-error="store.currentStopErrorCm"
        :records="store.parkingRecords"
      />

      <!-- 全车队列 -->
      <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
        <h3 class="text-sm font-semibold text-gray-300 mb-4">全车队列状态</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-xs text-gray-500 border-b border-gray-800">
                <th class="text-left py-2 pr-3">车辆</th>
                <th class="text-right py-2 px-2">模式</th>
                <th class="text-right py-2 px-2">速度</th>
                <th class="text-right py-2 px-2">位置</th>
                <th class="text-right py-2 px-2">加速度</th>
                <th class="text-right py-2 px-2">MA</th>
                <th class="text-right py-2 pl-2">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="v in store.vehicles"
                :key="v.vehicle_id"
                class="border-b border-gray-800/50 last:border-0 cursor-pointer hover:bg-gray-800/30"
                :class="store.selectedVehicleId === v.vehicle_id ? 'bg-gray-800/50' : ''"
                @click="store.selectVehicle(v.vehicle_id)"
              >
                <td class="py-2.5 pr-3">
                  <span class="inline-flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: store.vehicleColor(v.vehicle_id) }" />
                    {{ v.vehicle_id }}
                  </span>
                </td>
                <td class="text-right py-2.5 px-2 text-gray-400">{{ modeLabel(v.mode) }}</td>
                <td class="text-right py-2.5 px-2" :class="v.speed > (v.target_speed ?? 80) ? 'text-red-400' : 'text-gray-300'">{{ v.speed }}</td>
                <td class="text-right py-2.5 px-2 text-gray-400">{{ v.position }}</td>
                <td class="text-right py-2.5 px-2 text-gray-400">{{ v.acceleration }}</td>
                <td class="text-right py-2.5 px-2 text-gray-400">{{ v.ma_limit ?? '—' }}</td>
                <td class="text-right py-2.5 pl-2">
                  <span v-if="v.emergency_brake" class="text-red-400 text-xs">EB</span>
                  <span v-else class="text-emerald-500 text-xs">运行</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
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
import StatusCard from '@/components/StatusCard.vue'
import SpeedGauge from '@/components/SpeedGauge.vue'
import MultiVehicleChart from '@/components/MultiVehicleChart.vue'
import PositionChart from '@/components/PositionChart.vue'
import ConnectionBadge from '@/components/ConnectionBadge.vue'
import ParkingPrecision from '@/components/ParkingPrecision.vue'

const store = usePageSimulation()
const active = computed(() => store.selectedVehicle)
</script>
