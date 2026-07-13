<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Impact</p>
        <h3 class="app-section-title">受影响车辆摘要</h3>
        <p class="app-section-copy">
          这里将汇总限速、停车等待、ATP 介入等受影响车辆状态。
        </p>
      </div>
    </div>

    <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
      <div class="app-metric-tile">
        <p class="app-metric-label">受影响车辆</p>
        <p class="app-metric-value">{{ affectedVehicles.length }}</p>
        <p class="mt-2 text-xs text-slate-500">由 MA 受限、停车等待或 ATP 介入触发。</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">ATP 介入</p>
        <p class="app-metric-value">{{ emergencyCount }}</p>
        <p class="mt-2 text-xs text-slate-500">紧急制动中的车辆会在这里优先提示。</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">停车等待</p>
        <p class="app-metric-value">{{ stopCount }}</p>
        <p class="mt-2 text-xs text-slate-500">permission=stop 或已进入站停阶段的车辆。</p>
      </div>
    </div>

    <div
      v-if="affectedVehicles.length"
      class="mt-4 space-y-3"
    >
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
              <p class="text-xs text-slate-500">{{ vehicle.station_name ?? '区间运行中' }} · {{ modeLabel(vehicle.mode) }}</p>
            </div>
          </div>
          <span
            class="rounded-full px-3 py-1 text-[11px]"
            :class="statusClass(vehicle)"
          >
            {{ statusLabel(vehicle) }}
          </span>
        </div>

        <div class="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          <div class="app-metric-tile">
            <p class="app-metric-label">当前速度</p>
            <p class="mt-1 text-sm text-slate-200">{{ Math.round(vehicle.speed ?? 0) }} km/h</p>
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
      当前没有明显受限车辆，说明全线暂无 MA 收缩、停车等待或 ATP 介入信号。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { modeLabel } from '@/adapters/simulation'
import { usePageSimulation } from '@/composables/usePageSimulation'

const store = usePageSimulation()

const affectedVehicles = computed(() =>
  store.vehicles
    .filter((vehicle) =>
      vehicle.emergency_brake
      || vehicle.permission === 'stop'
      || vehicle.permission === 'restricted'
      || ['braking', 'docking', 'stopped'].includes(vehicle.parking_phase)
    )
    .sort((a, b) => {
      const aPriority = a.emergency_brake ? 0 : a.permission === 'stop' ? 1 : 2
      const bPriority = b.emergency_brake ? 0 : b.permission === 'stop' ? 1 : 2
      if (aPriority !== bPriority) return aPriority - bPriority
      return (a.distance_to_ma ?? Number.POSITIVE_INFINITY) - (b.distance_to_ma ?? Number.POSITIVE_INFINITY)
    })
    .slice(0, 6)
)

const emergencyCount = computed(() =>
  affectedVehicles.value.filter((vehicle) => vehicle.emergency_brake).length
)

const stopCount = computed(() =>
  affectedVehicles.value.filter((vehicle) =>
    vehicle.permission === 'stop' || ['docking', 'stopped'].includes(vehicle.parking_phase)
  ).length
)

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

function parkingPhaseLabel(phase) {
  return {
    cruising: '巡航',
    approaching: '进站接近',
    braking: '制动中',
    docking: '对标中',
    stopped: '已停稳',
  }[phase] ?? phase ?? '—'
}

function statusLabel(vehicle) {
  if (vehicle.emergency_brake) return 'ATP 介入'
  if (vehicle.permission === 'stop') return '停车等待'
  if (vehicle.permission === 'restricted') return 'MA 受限'
  if (vehicle.parking_phase === 'docking') return '对标停车'
  if (vehicle.parking_phase === 'stopped') return '已停稳'
  return '受关注'
}

function statusClass(vehicle) {
  if (vehicle.emergency_brake) return 'bg-red-950 text-red-300'
  if (vehicle.permission === 'stop') return 'bg-amber-950 text-amber-300'
  if (vehicle.permission === 'restricted') return 'bg-cyan-950 text-cyan-300'
  return 'bg-slate-900 text-slate-300'
}
</script>
