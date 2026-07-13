<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Impact</p>
        <h3 class="app-section-title">受影响车辆摘要</h3>
        <p class="app-section-copy">
          基于实时 train_state、ma_state、atp_state、signal_state 汇总受限、停车等待、ATP 介入和接近 MA 边界的车辆。
        </p>
      </div>
    </div>

    <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
      <div class="app-metric-tile">
        <p class="app-metric-label">受影响车辆</p>
        <p class="app-metric-value">{{ affectedVehicles.length }}</p>
        <p class="mt-2 text-xs text-slate-500">由真实车辆状态、MA 权限、信号状态和 ATP 状态触发。</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">ATP / 紧急制动</p>
        <p class="app-metric-value">{{ emergencyCount }}</p>
        <p class="mt-2 text-xs text-slate-500">包含 emergency_brake 或 atp_intervention 的车辆。</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">停车等待</p>
        <p class="app-metric-value">{{ stopCount }}</p>
        <p class="mt-2 text-xs text-slate-500">permission=stop 或处于对标/停稳阶段的车辆。</p>
      </div>
    </div>

    <div v-if="affectedVehicles.length" class="mt-4 space-y-3">
      <article
        v-for="vehicle in affectedVehicles"
        :key="vehicle.vehicle_id"
        class="rounded-[1.05rem] border border-white/10 bg-white/[0.02] px-4 py-4"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-2">
            <span
              class="h-2.5 w-2.5 rounded-full"
              :style="{ backgroundColor: store.vehicleColor(vehicle.vehicle_id) }"
            />
            <div>
              <p class="text-sm font-medium text-slate-100">{{ vehicle.vehicle_id }}</p>
              <p class="text-xs text-slate-500">
                {{ vehicle.station_name ?? vehicle.current_section_id ?? vehicle.section_id ?? '区间运行' }} · {{ modeLabel(vehicle.mode) }}
              </p>
            </div>
          </div>
          <span class="rounded-full px-3 py-1 text-[11px]" :class="statusClass(vehicle)">
            {{ statusLabel(vehicle) }}
          </span>
        </div>

        <div class="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          <div class="app-metric-tile">
            <p class="app-metric-label">当前速度</p>
            <p class="mt-1 text-sm text-slate-200">{{ speedText(vehicle) }}</p>
          </div>
          <div class="app-metric-tile">
            <p class="app-metric-label">距离 MA</p>
            <p class="mt-1 text-sm text-slate-200">{{ distanceToMaText(vehicle) }}</p>
          </div>
          <div class="app-metric-tile">
            <p class="app-metric-label">许可状态</p>
            <p class="mt-1 text-sm text-slate-200">{{ permissionLabel(vehicle.permission) }}</p>
          </div>
          <div class="app-metric-tile">
            <p class="app-metric-label">停车阶段</p>
            <p class="mt-1 text-sm text-slate-200">{{ parkingPhaseLabel(vehicle.parking_phase) }}</p>
          </div>
        </div>
      </article>
    </div>

    <div
      v-else
      class="mt-4 rounded-[1.1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500"
    >
      当前没有车辆触发 MA 收缩、信号受限、停车等待或 ATP 介入条件。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { modeLabel, parkingPhaseLabel } from '@/adapters/simulation'
import { useOverviewScene } from '@/composables/useOverviewScene'
import { usePageSimulation } from '@/composables/usePageSimulation'

const store = usePageSimulation()
const { affectedVehicles: overviewAffectedVehicles } = useOverviewScene()

const affectedVehicles = computed(() => overviewAffectedVehicles.value.slice(0, 6))

const emergencyCount = computed(() =>
  affectedVehicles.value.filter((vehicle) => vehicle.emergency_brake || vehicle.atp_intervention).length
)

const stopCount = computed(() =>
  affectedVehicles.value.filter((vehicle) =>
    vehicle.permission === 'stop' || ['docking', 'stopped'].includes(vehicle.parking_phase)
  ).length
)

function speedText(vehicle) {
  const speed = vehicle.speed ?? vehicle.speed_kmh
  return speed == null ? '—' : `${Math.round(speed)} km/h`
}

function distanceToMaText(vehicle) {
  if (vehicle.distance_to_ma == null) return '—'
  return `${Math.max(0, vehicle.distance_to_ma).toFixed(1)} m`
}

function permissionLabel(permission) {
  if (permission === 'allow') return '允许通过'
  if (permission === 'restricted') return '受限通过'
  if (permission === 'stop') return '停车'
  return permission ?? '—'
}

function statusLabel(vehicle) {
  if (vehicle.emergency_brake || vehicle.atp_intervention) return 'ATP 介入'
  if (vehicle.permission === 'stop') return '停车等待'
  if (vehicle.permission === 'restricted') return 'MA 受限'
  if (vehicle.signal_state === 'red' || vehicle.signal_state === 'yellow') return '信号受限'
  if (vehicle.distance_to_ma != null && vehicle.distance_to_ma < 120) return '接近 MA'
  if (vehicle.parking_phase === 'docking') return '对标停车'
  if (vehicle.parking_phase === 'stopped') return '已停稳'
  return '受关注'
}

function statusClass(vehicle) {
  if (vehicle.emergency_brake || vehicle.atp_intervention) return 'bg-red-950 text-red-300'
  if (vehicle.permission === 'stop' || vehicle.signal_state === 'red') return 'bg-amber-950 text-amber-300'
  if (vehicle.permission === 'restricted' || vehicle.signal_state === 'yellow') return 'bg-cyan-950 text-cyan-300'
  return 'bg-slate-900 text-slate-300'
}
</script>
