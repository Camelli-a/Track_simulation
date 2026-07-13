<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Focused Vehicle</p>
        <h3 class="app-section-title">当前关注车辆</h3>
        <p class="app-section-copy">
          展示当前选中车辆的实时 train_state、MA、ATO/ATP 和停车状态；作为停车控制页面的入口。
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
          {{ targetSpeedText }}
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
import { parkingPhaseLabel } from '@/adapters/simulation'
import { useFocusedVehicle } from '@/composables/useFocusedVehicle'
import { usePageSimulation } from '@/composables/usePageSimulation'

const store = usePageSimulation()
const { focusedVehicle: vehicle } = useFocusedVehicle()

const description = computed(() =>
  vehicle.value
    ? '当前车辆来自后端实时状态，可继续查看其 MA 余量、控制来源、停车阶段和 ATO/ATP 结果。'
    : '点击线路主视图或车辆列表中的列车后，这里会同步显示该车的关键状态。'
)

const insight = computed(() => {
  const current = vehicle.value
  if (!current) return ''
  if (current.emergency_brake || current.atp_intervention) {
    return `${current.vehicle_id} 已进入 ATP/紧急制动状态，应优先核对触发原因、通信状态和距离 MA 的剩余空间。`
  }
  if (current.permission === 'stop') {
    return `${current.vehicle_id} 当前收到停车许可约束，应关注前方信号状态、停车点和当前制动级位。`
  }
  if (current.distance_to_ma != null && current.distance_to_ma < 120) {
    return `${current.vehicle_id} 距离 MA 边界仅剩 ${current.distance_to_ma.toFixed(1)} m，应关注制动曲线和当前控制来源。`
  }
  return `${current.vehicle_id} 当前未触发强约束，可继续观察停车阶段、目标速度和线路前方约束。`
})

const sceneSummary = computed(() => {
  const current = vehicle.value
  if (!current) return '待选车'
  if (current.emergency_brake || current.atp_intervention) return 'ATP 介入'
  if (current.permission === 'stop') return '停车等待'
  if (current.permission === 'restricted') return 'MA 受限运行'
  if (current.signal_state === 'red' || current.signal_state === 'yellow') return '信号受限'
  if (current.parking_phase === 'approaching') return '进站接近'
  if (current.parking_phase === 'braking') return '停车制动中'
  if (current.parking_phase === 'docking') return '对标停车'
  if (current.parking_phase === 'stopped') return '已停稳'
  return '正常巡航'
})

const targetSpeedText = computed(() => {
  if (!vehicle.value || vehicle.value.target_speed == null) return '—'
  return `${Math.round(vehicle.value.target_speed)} km/h`
})

const stopDistanceText = computed(() => {
  if (!vehicle.value || vehicle.value.stop_distance == null) return '剩余距离 —'
  return `剩余 ${Math.max(0, vehicle.value.stop_distance).toFixed(1)} m`
})
</script>
