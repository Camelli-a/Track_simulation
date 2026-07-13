<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Scene Metrics</p>
        <h3 class="app-section-title">场景关键指标</h3>
        <p class="app-section-copy">
          这里跟随当前关注车辆场景切换关键指标，不再固定写死一组卡片。
        </p>
      </div>
      <span class="app-chip">{{ sceneId }}</span>
    </div>

    <div
      v-if="metricCards.length"
      class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4"
    >
      <article
        v-for="metric in metricCards"
        :key="metric.key"
        class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-4"
      >
        <p class="app-metric-label">{{ metric.label }}</p>
        <p class="mt-2 text-lg font-semibold text-slate-100">{{ metric.value }}</p>
        <p class="mt-2 text-xs leading-5 text-slate-500">{{ metric.hint }}</p>
      </article>
    </div>

    <div
      v-else
      class="mt-4 rounded-[1.1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500"
    >
      当前关注车辆场景还没有配置 `key_metrics`。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useOverviewScene } from '@/composables/useOverviewScene'

const { focusedVehicleScene, focusedVehicleSceneMetricCards } = useOverviewScene()

const sceneId = computed(() => focusedVehicleScene.value?.scenario_id ?? 'line_run')
const metricCards = computed(() => focusedVehicleSceneMetricCards.value)
</script>
