<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Interlocking</p>
        <h3 class="app-section-title">联锁冲突 / 进路不满足列表</h3>
        <p class="app-section-copy">
          这里将列出进路不满足、道岔位置不符、锁闭冲突和占用冲突。
        </p>
      </div>
      <span class="app-chip">{{ conflictCountLabel }}</span>
    </div>

    <div v-if="interlockingConflicts.length" class="mt-4 space-y-3">
      <article
        v-for="conflict in interlockingConflicts"
        :key="conflict.id"
        class="rounded-[1.05rem] border px-4 py-4"
        :class="conflict.level === 'high'
          ? 'border-red-900/60 bg-red-950/20'
          : 'border-amber-900/60 bg-amber-950/20'"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex flex-wrap items-center gap-2">
            <span
              class="rounded-full px-2 py-0.5 text-[11px]"
              :class="conflict.level === 'high'
                ? 'bg-red-950 text-red-300'
                : 'bg-amber-950 text-amber-300'"
            >
              {{ conflict.level === 'high' ? '高优先级' : '关注' }}
            </span>
            <span class="text-sm font-medium text-slate-100">{{ conflict.title }}</span>
          </div>
          <span class="text-[11px] text-slate-500">{{ conflict.kind }}</span>
        </div>

        <div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
          <div class="app-metric-tile">
            <p class="app-metric-label">道岔</p>
            <p class="mt-1 text-sm text-slate-200">{{ conflict.turnoutLabel }}</p>
          </div>
          <div class="app-metric-tile">
            <p class="app-metric-label">区段</p>
            <p class="mt-1 text-sm text-slate-200">{{ conflict.segmentLabel }}</p>
          </div>
          <div class="app-metric-tile">
            <p class="app-metric-label">信号</p>
            <p class="mt-1 text-sm text-slate-200">{{ conflict.signalLabel }}</p>
          </div>
        </div>

        <p class="mt-3 text-sm leading-6 text-slate-300">{{ conflict.detail }}</p>
      </article>
    </div>

    <div
      v-else
      class="mt-4 rounded-[1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-sm text-slate-500"
    >
      当前未发现明显联锁冲突。系统仍会继续检查“区段占用但信号开放”“道岔解锁占用”“反位分支占用”等条件。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useSignalConstraint } from '@/composables/useSignalConstraint'

const { interlockingConflicts } = useSignalConstraint()

const conflictCountLabel = computed(() =>
  interlockingConflicts.value.length
    ? `${interlockingConflicts.value.length} 项待核查`
    : '未发现冲突'
)
</script>
