<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Scene Events</p>
        <h3 class="app-section-title">当前场景事件摘要</h3>
        <p class="app-section-copy">
          这里根据当前场景的 `highlightEvents` 自动从最近事件时间线和告警里提炼关键信号；点车后优先看该车。
        </p>
      </div>
      <span class="app-chip">{{ activeOverviewScene.scenario_id }}</span>
    </div>

    <div
      v-if="activeOverviewSceneEventCards.length"
      class="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2"
    >
      <article
        v-for="event in activeOverviewSceneEventCards"
        :key="event.key"
        class="rounded-[1.05rem] border px-4 py-4"
        :class="eventCardClass(event)"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p class="text-sm font-medium text-slate-100">{{ event.label }}</p>
            <p class="mt-1 text-[11px] text-slate-500">{{ event.key }}</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <span class="app-chip app-chip-subtle">{{ event.sourceLabel }}</span>
            <span
              class="rounded-full px-3 py-1 text-[11px]"
              :class="event.matched ? 'bg-emerald-950 text-emerald-300' : 'bg-slate-900 text-slate-400'"
            >
              {{ event.matched ? '已捕获' : '待出现' }}
            </span>
          </div>
        </div>

        <p class="mt-3 text-sm text-slate-200">{{ event.title }}</p>
        <p class="mt-2 text-xs leading-5 text-slate-400">{{ event.detail }}</p>
        <p class="mt-3 text-[11px] text-slate-500">时间：{{ event.atLabel }}</p>
      </article>
    </div>

    <div
      v-else
      class="mt-4 rounded-[1.1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500"
    >
      当前场景还没有配置 `highlightEvents`。
    </div>
  </section>
</template>

<script setup>
import { useOverviewScene } from '@/composables/useOverviewScene'

const { activeOverviewScene, activeOverviewSceneEventCards } = useOverviewScene()

function eventCardClass(event) {
  if (!event.matched) return 'border-white/10 bg-white/[0.02]'
  if (event.level === 'error') return 'border-red-900/50 bg-red-950/20'
  if (event.level === 'warn') return 'border-amber-900/50 bg-amber-950/20'
  return 'border-emerald-900/40 bg-emerald-950/10'
}
</script>
