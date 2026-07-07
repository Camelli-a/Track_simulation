<template>
  <span
    class="inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-full border"
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
  dataStale: { type: Boolean, default: false },
})

const label = computed(() => {
  if (!props.connected) return '连接中...'
  if (props.dataStale) return '数据滞后'
  return '实时数据'
})

const badgeClass = computed(() => {
  if (!props.connected) return 'border-red-800 bg-red-950 text-red-400'
  if (props.dataStale) return 'border-amber-800 bg-amber-950 text-amber-400'
  return 'border-emerald-700 bg-emerald-950 text-emerald-400'
})

const dotClass = computed(() => {
  if (!props.connected) return 'bg-red-500'
  if (props.dataStale) return 'bg-amber-400'
  return 'bg-emerald-400 animate-pulse'
})
</script>
