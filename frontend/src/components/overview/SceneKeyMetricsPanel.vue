<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Scene Metrics</p>
        <h3 class="app-section-title">场景关键指标</h3>
        <p class="app-section-copy">
          指标来自后端实时快照，不再使用固定演示值；选中车辆后优先展示该车的速度、MA、ATO/ATP 和停车数据。
        </p>
      </div>
      <span class="app-chip">{{ activeOverviewScene.scenario_id }}</span>
    </div>

    <div
      v-if="activeOverviewSceneMetricCards.length"
      class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4"
    >
      <article
        v-for="metric in activeOverviewSceneMetricCards"
        :key="metric.key"
        class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-4"
      >
        <div class="flex items-start justify-between gap-3">
          <p class="app-metric-label">{{ metric.label }}</p>
          <span class="app-chip app-chip-subtle">{{ metric.sourceLabel }}</span>
        </div>
        <p class="mt-2 text-lg font-semibold text-slate-100">{{ metric.value }}</p>
        <p class="mt-2 text-xs leading-5 text-slate-500">{{ metric.hint }}</p>
      </article>
    </div>

    <div
      v-else
      class="mt-4 rounded-[1.1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500"
    >
      当前后端快照还没有可展示的关键指标。
    </div>
  </section>
</template>

<script setup>
import { useOverviewScene } from '@/composables/useOverviewScene'

const { activeOverviewScene, activeOverviewSceneMetricCards } = useOverviewScene()
</script>
