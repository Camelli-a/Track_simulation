<template>
  <div class="rounded-2xl border border-white/10 bg-slate-950/90 px-4 py-3 shadow-[0_12px_30px_rgba(2,6,23,0.45)] backdrop-blur">
    <div class="flex flex-wrap items-center gap-2 text-xs">
      <ConnectionBadge
        :connected="connected"
        :connecting="connecting"
        :data-stale="dataStale"
      />
      <span class="app-chip">更新时间 {{ freshnessLabel }}</span>
      <span class="app-chip">当前场景 {{ sceneLabel }}</span>
      <span class="app-chip">系统模式 {{ modeLabel }}</span>
      <span v-if="dataSource" class="app-chip">数据源 {{ dataSource }}</span>
    </div>
  </div>
</template>

<script setup>
import ConnectionBadge from '@/components/ConnectionBadge.vue'

defineProps({
  connected: { type: Boolean, default: false },
  connecting: { type: Boolean, default: false },
  dataStale: { type: Boolean, default: false },
  freshnessLabel: { type: String, default: '等待首帧数据' },
  sceneLabel: { type: String, default: '全局总览' },
  modeLabel: { type: String, default: '正常运行' },
  dataSource: { type: String, default: null },
})
</script>
