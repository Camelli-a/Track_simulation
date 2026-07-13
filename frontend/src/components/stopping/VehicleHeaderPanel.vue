<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Focused Vehicle</p>
        <h3 class="app-section-title">当前关注车辆头部</h3>
        <p class="app-section-copy">
          这里承接车辆编号、站名、站台、模式、停车阶段和当前关注车辆场景。
        </p>
      </div>
    </div>

    <div
      v-if="vehicle"
      class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[1.1fr_0.9fr]"
    >
      <article class="rounded-[1.1rem] border border-white/10 bg-white/[0.03] px-4 py-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p class="text-[11px] uppercase tracking-[0.24em] text-slate-500">Vehicle</p>
            <h4 class="mt-2 text-lg font-semibold text-slate-100">{{ vehicle.vehicle_id }}</h4>
            <p class="mt-2 text-sm text-slate-400">
              {{ vehicle.station_name ?? '未知站' }}<span v-if="vehicle.platform_id"> · {{ vehicle.platform_id }}</span>
            </p>
          </div>
          <div class="flex flex-wrap gap-2 text-[11px]">
            <span class="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-slate-200">
              {{ modeLabel(vehicle.mode) }}
            </span>
            <span
              class="rounded-full px-3 py-1"
              :class="vehicle.emergency_brake ? 'bg-red-950 text-red-300' : 'bg-emerald-950 text-emerald-300'"
            >
              {{ vehicle.emergency_brake ? '紧急制动' : parkingPhaseLabel(vehicle.parking_phase) }}
            </span>
          </div>
        </div>

        <div class="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <div class="app-metric-tile">
            <p class="app-metric-label">当前位置</p>
            <p class="mt-1 text-sm text-slate-200">{{ Math.round(vehicle.position ?? 0) }} m</p>
          </div>
          <div class="app-metric-tile">
            <p class="app-metric-label">当前速度</p>
            <p class="mt-1 text-sm text-slate-200">{{ Math.round(vehicle.speed ?? 0) }} km/h</p>
          </div>
          <div class="app-metric-tile">
            <p class="app-metric-label">目标速度</p>
            <p class="mt-1 text-sm text-slate-200">{{ vehicle.target_speed != null ? `${Math.round(vehicle.target_speed)} km/h` : '—' }}</p>
          </div>
          <div class="app-metric-tile">
            <p class="app-metric-label">更新时间</p>
            <p class="mt-1 text-sm text-slate-200">{{ updatedAtText }}</p>
          </div>
        </div>
      </article>

      <article class="rounded-[1.1rem] border border-cyan-500/20 bg-cyan-500/10 px-4 py-4">
        <p class="text-[11px] uppercase tracking-[0.24em] text-cyan-200/70">Focused Scene</p>
        <template v-if="scene">
          <h4 class="mt-2 text-lg font-semibold text-slate-100">{{ scene.label }}</h4>
          <p class="mt-1 text-sm text-slate-400">{{ scene.scenario_id }}</p>
          <p class="mt-3 text-sm leading-6 text-slate-200">{{ scene.summary }}</p>
          <div class="mt-4 flex flex-wrap gap-2">
            <span class="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-[11px] text-cyan-100">
              {{ scene.scope === 'vehicle' ? '车辆级' : '全线级' }}
            </span>
            <span
              v-if="scene.targetVehicleId"
              class="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-[11px] text-slate-200"
            >
              {{ scene.targetVehicleId }}
            </span>
          </div>
        </template>
        <div
          v-else
          class="mt-3 rounded-[1rem] border border-dashed border-white/10 bg-black/10 px-4 py-6 text-sm text-slate-500"
        >
          当前还没有识别到关注车辆场景。
        </div>
      </article>
    </div>

    <div
      v-else
      class="mt-4 rounded-[1.1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500"
    >
      当前还没有选中车辆。请先在运行总览页点击列车，或等待系统自动选中第一辆在线车。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { modeLabel, parkingPhaseLabel } from '@/adapters/simulation'
import { useFocusedVehicle } from '@/composables/useFocusedVehicle'
import { useOverviewScene } from '@/composables/useOverviewScene'

const { focusedVehicle: vehicle } = useFocusedVehicle()
const { focusedVehicleScene: scene } = useOverviewScene()

const updatedAtText = computed(() => {
  if (!vehicle.value?.updated_at) return '—'
  const numeric = Number(vehicle.value.updated_at)
  const timestamp = Number.isFinite(numeric) ? (numeric > 1e12 ? numeric : numeric * 1000) : Date.parse(vehicle.value.updated_at)
  if (!Number.isFinite(timestamp)) return '—'
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
})
</script>
