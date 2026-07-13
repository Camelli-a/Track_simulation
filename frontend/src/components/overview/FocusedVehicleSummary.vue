<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Focused Vehicle</p>
        <h3 class="app-section-title">当前关注车辆</h3>
        <p class="app-section-copy">
          这里将承接总览页点车后的单车快照，并作为第二页停车控制的入口。
        </p>
      </div>
    </div>

    <SelectedVehicleSummary
      class="mt-4"
      :vehicle="vehicle"
      :color="store.vehicleColor"
      :description="description"
      :insight="insight"
    />

    <div v-if="vehicle" class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
      <div class="app-metric-tile">
        <p class="app-metric-label">当前场景</p>
        <p class="mt-1 text-sm text-slate-200">{{ sceneSummary }}</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">停车阶段</p>
        <p class="mt-1 text-sm text-slate-200">{{ parkingPhaseLabel(vehicle.parking_phase) }}</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">目标速度 / 停车点</p>
        <p class="mt-1 text-sm text-slate-200">
          {{ vehicle.target_speed != null ? `${Math.round(vehicle.target_speed)} km/h` : '—' }}
          <span class="text-slate-500"> / {{ stopDistanceText }}</span>
        </p>
      </div>
    </div>

    <div v-if="vehicle" class="mt-4 flex flex-wrap gap-2">
      <RouterLink
        to="/cab"
        class="rounded-xl border border-cyan-400/40 bg-cyan-400/10 px-3 py-2 text-xs text-cyan-100 transition hover:border-cyan-300/60 hover:bg-cyan-400/15"
      >
        进入停车控制页
      </RouterLink>
      <button
        type="button"
        class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:bg-white/10"
        @click="store.selectVehicle(vehicle.vehicle_id)"
      >
        保持当前关注车辆
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import SelectedVehicleSummary from '@/components/SelectedVehicleSummary.vue'
import { useFocusedVehicle } from '@/composables/useFocusedVehicle'
import { usePageSimulation } from '@/composables/usePageSimulation'

const store = usePageSimulation()
const { focusedVehicle: vehicle } = useFocusedVehicle()

const description = computed(() =>
  vehicle.value
    ? '先在总览页锁定重点列车，再进入停车控制页深挖 ATO / ATP 和停车结果。'
    : '点击线路主视图中的列车后，这里会同步显示它的关键状态，并作为第二页停车控制的入口。'
)

const insight = computed(() => {
  const current = vehicle.value
  if (!current) return ''
  if (current.emergency_brake) {
    return `${current.vehicle_id} 当前已进入紧急制动，建议优先切到停车控制页核对 ATP 触发原因和距离 MA 的剩余空间。`
  }
  if (current.permission === 'stop') {
    return `${current.vehicle_id} 当前已收到停车许可约束，建议继续核对前方信号状态和停车点剩余距离。`
  }
  if (current.distance_to_ma != null && current.distance_to_ma < 120) {
    return `${current.vehicle_id} 距离 MA 边界仅剩 ${current.distance_to_ma.toFixed(1)} m，建议重点关注制动曲线和当前控制来源。`
  }
  return `${current.vehicle_id} 当前运行状态稳定，可继续观察其停车阶段、目标速度和线路前方约束。`
})

const sceneSummary = computed(() => {
  const current = vehicle.value
  if (!current) return '待选车'
  if (current.emergency_brake) return 'ATP 介入'
  if (current.permission === 'stop') return '停车等待'
  if (current.permission === 'restricted') return 'MA 受限运行'
  if (current.parking_phase === 'approaching') return '正常进站接近'
  if (current.parking_phase === 'braking') return '停车制动中'
  if (current.parking_phase === 'docking') return '对标停车'
  if (current.parking_phase === 'stopped') return '已停稳'
  return '正常巡航'
})

const stopDistanceText = computed(() => {
  if (!vehicle.value || vehicle.value.stop_distance == null) return '剩余距离 —'
  return `剩余 ${Math.max(0, vehicle.value.stop_distance).toFixed(1)} m`
})

function parkingPhaseLabel(phase) {
  return {
    cruising: '巡航',
    approaching: '进站接近',
    braking: '制动中',
    docking: '对标中',
    stopped: '已停稳',
  }[phase] ?? phase ?? '—'
}
</script>
