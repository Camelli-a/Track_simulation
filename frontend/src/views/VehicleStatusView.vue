<template>
  <div class="space-y-5">
    <!-- 页头 -->
    <header class="app-panel">
      <div class="app-section-head">
        <div>
          <p class="app-section-kicker">Vehicle Status</p>
          <h2 class="text-xl font-semibold text-slate-100">车辆状况</h2>
          <p class="app-section-copy">
            汇总列车实时运行状态：速度曲线、司机台输入状态。
          </p>
        </div>
        <!-- 车辆选择：有实时快照时显示 -->
        <div v-if="simStore.vehicles.length" class="flex flex-wrap gap-2">
          <button
            v-for="vehicle in simStore.vehicles"
            :key="vehicle.vehicle_id"
            type="button"
            class="rounded-xl border px-3 py-1.5 text-xs transition-all"
            :class="selectedVehicleId === vehicle.vehicle_id
              ? 'border-cyan-400/60 bg-cyan-400/10 text-cyan-100'
              : 'border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-slate-200'"
            @click="selectedVehicleId = vehicle.vehicle_id"
          >
            {{ vehicle.vehicle_id }}
          </button>
        </div>
      </div>
    </header>

    <!-- 速度曲线 -->
    <SpeedCurvePanel />

    <!-- 司机台状态：vehicleId 为 null 时组件内部取第一条 -->
    <DriverDeskPanel :vehicle-id="selectedVehicleId" />
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import SpeedCurvePanel from '@/components/vehicle/SpeedCurvePanel.vue'
import DriverDeskPanel from '@/components/vehicle/DriverDeskPanel.vue'
import { useSpeedCurveStore } from '@/stores/speedCurve'
import { useSimulationStore } from '@/stores/simulation'

const speedCurveStore = useSpeedCurveStore()
const simStore = useSimulationStore()

// 本地选中的车辆 ID，驱动司机台面板的查询
// 初始跟随 simStore.selectedVehicleId，用户可在这里单独切换
const selectedVehicleId = ref(simStore.selectedVehicleId ?? null)

onMounted(() => {
  speedCurveStore.startAll()
})

onBeforeUnmount(() => {
  speedCurveStore.stopAll()
})
</script>
