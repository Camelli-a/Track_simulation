<template>
  <span
    class="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium tracking-wide shadow-[0_8px_20px_rgba(15,23,42,0.28)]"
    :class="badgeClass"
  >
    <span class="w-2 h-2 rounded-full" :class="dotClass" />
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  connected: { type: Boolean, default: false },
  connecting: { type: Boolean, default: false },
  dataStale: { type: Boolean, default: false },
})

const label = computed(() => {
  if (props.connecting) return '正在连接'
  if (!props.connected) return '连接断开'
  if (props.dataStale) return '数据滞后'
  return '实时同步'
})

const badgeClass = computed(() => {
  if (props.connecting) return 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200'
  if (!props.connected) return 'border-red-500/25 bg-red-500/10 text-red-200'
  if (props.dataStale) return 'border-amber-500/25 bg-amber-500/10 text-amber-200'
  return 'border-emerald-400/25 bg-emerald-400/10 text-emerald-100'
})

const dotClass = computed(() => {
  if (props.connecting) return 'bg-cyan-300 animate-pulse'
  if (!props.connected) return 'bg-red-400'
  if (props.dataStale) return 'bg-amber-300'
  return 'bg-emerald-300 animate-pulse'
})
</script>
