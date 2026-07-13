<template>
  <div
    class="inline-flex items-center gap-1 rounded-full border border-white/10 bg-slate-950/60 px-1.5 py-1 shadow-[0_8px_20px_rgba(15,23,42,0.22)] backdrop-blur"
  >
    <span
      v-for="item in statusItems"
      :key="item.key"
      class="rounded-full px-2 py-0.5 text-[11px] font-medium tracking-wide transition-colors"
      :class="item.active ? item.activeClass : 'text-slate-500'"
    >
      {{ item.label }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  connected: { type: Boolean, default: false },
  connecting: { type: Boolean, default: false },
  dataStale: { type: Boolean, default: false },
})

const currentStatus = computed(() => {
  if (props.connecting) return 'connecting'
  if (!props.connected) return 'disconnected'
  if (props.dataStale) return 'stale'
  return 'realtime'
})

const statusItems = computed(() => {
  const active = currentStatus.value

  return [
    {
      key: 'disconnected',
      label: '断开',
      active: active === 'disconnected',
      activeClass: 'bg-red-500/16 text-red-200',
    },
    {
      key: 'connecting',
      label: '连接中',
      active: active === 'connecting',
      activeClass: 'bg-cyan-500/16 text-cyan-200',
    },
    {
      key: 'stale',
      label: '滞后',
      active: active === 'stale',
      activeClass: 'bg-amber-500/16 text-amber-200',
    },
    {
      key: 'realtime',
      label: '实时',
      active: active === 'realtime',
      activeClass: 'bg-emerald-500/16 text-emerald-200',
    },
  ]
})
</script>
