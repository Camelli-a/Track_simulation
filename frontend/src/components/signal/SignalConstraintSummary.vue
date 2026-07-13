<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Constraint Summary</p>
        <h3 class="app-section-title">当前关注车辆的信号约束摘要</h3>
        <p class="app-section-copy">
          这里将展示信号状态、许可状态、MA、距离 MA、原因和前车信息。
        </p>
      </div>
    </div>

    <div
      v-if="vehicle"
      class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3"
    >
      <article
        v-for="item in summaryCards"
        :key="item.label"
        class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-4"
      >
        <p class="app-metric-label">{{ item.label }}</p>
        <p class="mt-2 text-lg font-semibold text-slate-100">{{ item.value }}</p>
        <p class="mt-2 text-xs leading-5 text-slate-500">{{ item.hint }}</p>
      </article>
    </div>

    <div
      v-else
      class="mt-4 rounded-[1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-sm text-slate-500"
    >
      当前没有关注车辆，信号约束摘要暂时无法展开。
    </div>
  </section>
</template>

<script setup>
import { useSignalConstraint } from '@/composables/useSignalConstraint'

const { vehicle, summaryCards } = useSignalConstraint()
</script>
