<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Constraint Chain</p>
        <h3 class="app-section-title">前方线路约束链</h3>
        <p class="app-section-copy">
          这里将按照“当前车 -> 区段 -> 信号机 -> 道岔 -> 进路 -> MA结果”的顺序解释约束来源。
        </p>
      </div>
    </div>

    <div
      v-if="constraintChain.length"
      class="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2"
    >
      <article
        v-for="node in constraintChain"
        :key="node.key"
        class="rounded-[1.05rem] border px-4 py-4"
        :class="nodeClass(node.level)"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p class="text-sm font-medium text-slate-100">{{ node.title }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ node.value }}</p>
          </div>
          <span class="rounded-full px-3 py-1 text-[11px]" :class="badgeClass(node.level)">
            {{ levelLabel(node.level) }}
          </span>
        </div>
        <p class="mt-3 text-sm leading-6 text-slate-300">{{ node.detail }}</p>
      </article>
    </div>

    <div
      v-else
      class="mt-4 rounded-[1.1rem] border border-dashed border-white/10 bg-black/10 px-4 py-10 text-sm text-slate-500"
    >
      当前没有可讲解的前方约束链。
    </div>
  </section>
</template>

<script setup>
import { useSignalConstraint } from '@/composables/useSignalConstraint'

const { constraintChain } = useSignalConstraint()

function nodeClass(level) {
  if (level === 'error') return 'border-red-900/50 bg-red-950/20'
  if (level === 'warn') return 'border-amber-900/50 bg-amber-950/20'
  return 'border-white/10 bg-white/[0.03]'
}

function badgeClass(level) {
  if (level === 'error') return 'bg-red-950 text-red-300'
  if (level === 'warn') return 'bg-amber-950 text-amber-300'
  return 'bg-sky-950 text-sky-300'
}

function levelLabel(level) {
  if (level === 'error') return '高风险'
  if (level === 'warn') return '需关注'
  return '正常'
}
</script>
