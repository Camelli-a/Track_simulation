<template>
  <section class="app-panel">
    <div class="app-section-head">
      <h3 class="app-section-title">当前场景</h3>
    </div>

    <article class="mt-4 rounded-[1.15rem] border border-cyan-500/20 bg-cyan-500/10 px-4 py-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p class="text-[11px] uppercase tracking-[0.26em] text-cyan-200/70">Current Scene</p>
          <h4 class="mt-2 text-lg font-semibold text-slate-100">{{ activeScene.label }}</h4>
        </div>
        <div class="flex flex-wrap gap-2 text-[11px]">
          <span
            v-if="sceneVehicle?.vehicle_id"
            class="rounded-full border border-white/10 bg-white/[0.06] px-3 py-1 text-slate-200"
          >
            {{ sceneVehicle.vehicle_id }}
          </span>
          <span class="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-cyan-100">
            {{ sceneTypeLabel }}
          </span>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useFocusedVehicle } from '@/composables/useFocusedVehicle'
import { useOverviewScene } from '@/composables/useOverviewScene'

const {
  activeOverviewScene: activeScene,
  vehicles,
} = useOverviewScene()
const { focusedVehicle: selectedVehicle } = useFocusedVehicle()

const sceneVehicle = computed(() =>
  selectedVehicle.value
  || (activeScene.value.targetVehicleId
    ? vehicles.value.find((vehicle) => vehicle.vehicle_id === activeScene.value.targetVehicleId) ?? null
    : null)
)

const sceneTypeLabel = computed(() => {
  const code = activeScene.value.code
  if (code === 'manual_overspeed_atp') return '安全防护'
  if (code === 'ma_shrink') return '授权变化'
  if (code === 'section_block_stop') return '线路约束'
  if (code === 'red_signal_stop') return '信号约束'
  if (code === 'normal_stop') return '正常停车'
  return '运行监视'
})
</script>
