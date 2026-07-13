<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Active Events</p>
        <h3 class="app-section-title">当前已注入事件列表</h3>
        <p class="app-section-copy">
          这里将展示事件编号、目标对象、生效时间、状态和恢复按钮。
        </p>
      </div>
      <span class="app-chip">{{ activeSystemEvents.length }} 条</span>
    </div>

    <div v-if="activeSystemEvents.length" class="mt-4 space-y-3">
      <article
        v-for="event in activeSystemEvents"
        :key="event.id"
        class="rounded-[1.05rem] border px-4 py-4"
        :class="event.level === 'error'
          ? 'border-red-900/60 bg-red-950/20'
          : event.level === 'warn'
            ? 'border-amber-900/60 bg-amber-950/20'
            : 'border-white/10 bg-white/[0.03]'"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p class="text-sm font-medium text-slate-100">{{ event.title }}</p>
            <p class="mt-2 text-sm leading-6 text-slate-300">{{ event.detail }}</p>
          </div>
          <div class="flex flex-wrap gap-2 text-[11px]">
            <span class="rounded-full px-3 py-1" :class="badgeClass(event.level)">{{ levelLabel(event.level) }}</span>
            <span class="rounded-full border border-white/10 px-3 py-1 text-slate-400">{{ event.source }}</span>
          </div>
        </div>

        <div class="mt-3 flex flex-wrap items-center justify-between gap-3 text-[11px] text-slate-500">
          <div class="flex flex-wrap items-center gap-3">
            <span>时间 {{ formatTime(event.at) }}</span>
            <span v-if="event.vehicleId">目标车辆 {{ event.vehicleId }}</span>
          </div>
          <button
            v-if="event.vehicleId"
            type="button"
            class="rounded-lg border border-white/10 px-2.5 py-1 text-slate-300 transition hover:border-white/20 hover:bg-white/5"
            @click="simulation.selectVehicle(event.vehicleId)"
          >
            聚焦该车
          </button>
        </div>

        <p v-if="event.actionHint" class="mt-3 text-xs leading-5 text-slate-400">{{ event.actionHint }}</p>
      </article>
    </div>

    <div
      v-else
      class="mt-4 rounded-[1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-sm text-slate-500"
    >
      当前没有活动异常，系统处于稳定运行态。
    </div>

    <div class="mt-4 rounded-[1rem] border border-white/10 bg-black/10 px-4 py-4">
      <div class="flex items-center justify-between gap-3">
        <p class="text-sm font-medium text-slate-100">最近演示操作</p>
        <span class="text-[11px] text-slate-500">{{ operatorActions.length }} 条</span>
      </div>

      <div v-if="operatorActions.length" class="mt-3 space-y-2">
        <div
          v-for="item in operatorActions.slice(0, 5)"
          :key="item.id"
          class="rounded-xl border px-3 py-3"
          :class="item.status === 'error'
            ? 'border-red-900/60 bg-red-950/20'
            : item.status === 'ok'
              ? 'border-emerald-900/60 bg-emerald-950/20'
              : 'border-sky-900/60 bg-sky-950/20'"
        >
          <div class="flex items-center justify-between gap-3">
            <span class="text-sm text-slate-100">{{ item.title }}</span>
            <span class="text-[11px]" :class="statusClass(item.status)">{{ statusText(item.status) }}</span>
          </div>
          <p class="mt-1 text-xs text-slate-400">{{ item.detail }}</p>
          <p class="mt-2 text-[11px] text-slate-500">{{ formatTime(item.at) }}</p>
          <p v-if="item.error" class="mt-1 text-[11px] text-red-300">{{ item.error }}</p>
        </div>
      </div>

      <p v-else class="mt-3 text-sm text-slate-500">当前还没有演示操作记录。</p>
    </div>
  </section>
</template>

<script setup>
import { useFaultWorkbench } from '@/composables/useFaultWorkbench'

const { simulation, activeSystemEvents, operatorActions } = useFaultWorkbench()

function formatTime(timestamp) {
  return new Date(Number(timestamp)).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function badgeClass(level) {
  if (level === 'error') return 'bg-red-950 text-red-300'
  if (level === 'warn') return 'bg-amber-950 text-amber-300'
  return 'bg-sky-950 text-sky-300'
}

function levelLabel(level) {
  if (level === 'error') return '严重'
  if (level === 'warn') return '提醒'
  return '信息'
}

function statusText(status) {
  if (status === 'ok') return '已执行'
  if (status === 'error') return '失败'
  return '发送中'
}

function statusClass(status) {
  if (status === 'ok') return 'text-emerald-300'
  if (status === 'error') return 'text-red-300'
  return 'text-sky-300'
}
</script>
