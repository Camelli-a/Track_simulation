<template>
  <div class="rounded-2xl border border-white/10 bg-slate-950/90 px-4 py-3 shadow-[0_12px_30px_rgba(2,6,23,0.45)] backdrop-blur">
    <div class="flex flex-wrap items-center gap-2 text-xs">
      <ConnectionBadge
        :connected="connected"
        :connecting="connecting"
        :data-stale="dataStale"
      />
      <span class="app-chip">更新时间 {{ freshnessLabel }}</span>
      <span v-if="messageTimeLabel" class="app-chip">链路时间 {{ messageTimeLabel }}</span>
      <span class="app-chip" :class="accessStatusClass">接入状态 {{ accessStatusLabel }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ConnectionBadge from '@/components/ConnectionBadge.vue'

const props = defineProps({
  connected: { type: Boolean, default: false },
  connecting: { type: Boolean, default: false },
  dataStale: { type: Boolean, default: false },
  freshnessLabel: { type: String, default: '等待首帧数据' },
  messageTimeLabel: { type: String, default: null },
  accessStatusLabel: { type: String, default: '未识别' },
  accessStatusTone: { type: String, default: 'neutral' },
})

const accessStatusClass = computed(() => {
  if (props.accessStatusTone === 'hardware') {
    return 'border-emerald-400/30 bg-emerald-400/12 text-emerald-100'
  }
  if (props.accessStatusTone === 'mock') {
    return 'border-sky-400/30 bg-sky-400/12 text-sky-100'
  }
  if (props.accessStatusTone === 'warning') {
    return 'border-amber-400/30 bg-amber-400/12 text-amber-100'
  }
  return ''
})
</script>
