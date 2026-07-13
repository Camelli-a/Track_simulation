<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Scene Events</p>
        <h3 class="app-section-title">场景事件摘要</h3>
        <p class="app-section-copy">
          这里跟随当前关注车辆场景提取 highlightEvents，重点看这辆车的场景推进过程。
        </p>
      </div>
      <span class="app-chip">{{ sceneId }}</span>
    </div>

    <div
      v-if="eventCards.length"
      class="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2"
    >
      <article
        v-for="event in eventCards"
        :key="event.key"
        class="rounded-[1.05rem] border px-4 py-4"
        :class="eventCardClass(event)"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p class="text-sm font-medium text-slate-100">{{ event.label }}</p>
            <p class="mt-1 text-[11px] text-slate-500">{{ event.key }}</p>
          </div>
          <span
            class="rounded-full px-3 py-1 text-[11px]"
            :class="event.matched ? 'bg-emerald-950 text-emerald-300' : 'bg-slate-900 text-slate-400'"
          >
            {{ event.matched ? '已捕获' : '待出现' }}
          </span>
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
      当前关注车辆场景还没有配置 `highlightEvents`。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useOverviewScene } from '@/composables/useOverviewScene'

const { focusedVehicleScene, focusedVehicleSceneEventCards } = useOverviewScene()

const sceneId = computed(() => focusedVehicleScene.value?.scenario_id ?? 'line_run')
const eventCards = computed(() => focusedVehicleSceneEventCards.value)

function eventCardClass(event) {
  if (!event.matched) return 'border-white/10 bg-white/[0.02]'
  if (event.level === 'error') return 'border-red-900/50 bg-red-950/20'
  if (event.level === 'warn') return 'border-amber-900/50 bg-amber-950/20'
  return 'border-emerald-900/40 bg-emerald-950/10'
}
</script>
