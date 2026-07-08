<!-- 后端告警列表（dashboard_snapshot.alarms） -->
<template>
  <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-gray-300">系统告警</h3>
      <span class="text-xs text-gray-500">{{ alarms.length }} 条</span>
    </div>

    <div v-if="!alarms.length" class="text-sm text-gray-600 text-center py-8">
      暂无告警
    </div>

    <div v-else class="space-y-2 max-h-48 overflow-y-auto">
      <div
        v-for="a in alarms"
        :key="a.alarm_id"
        class="flex items-start gap-3 px-3 py-2 rounded-lg border text-sm"
        :class="rowClass(a.level)"
      >
        <span class="text-xs font-mono text-gray-500 shrink-0 mt-0.5">{{ a.alarm_id }}</span>
        <div class="flex-1 min-w-0">
          <p class="text-gray-200">{{ a.message }}</p>
          <p class="text-[10px] text-gray-500 mt-0.5">
            {{ a.source }}
            <template v-if="a.vehicle_id"> · {{ a.vehicle_id }}</template>
            <template v-if="a.timestamp"> · {{ formatTime(a.timestamp) }}</template>
          </p>
        </div>
        <span class="text-[10px] uppercase shrink-0" :class="levelTextClass(a.level)">
          {{ a.level }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  alarms: { type: Array, default: () => [] },
})

function rowClass(level) {
  if (level === 'critical') return 'border-red-900/60 bg-red-950/30'
  if (level === 'warning') return 'border-amber-900/60 bg-amber-950/20'
  return 'border-gray-800 bg-gray-950/50'
}

function levelTextClass(level) {
  if (level === 'critical') return 'text-red-400'
  if (level === 'warning') return 'text-amber-400'
  return 'text-sky-400'
}

function formatTime(ts) {
  return new Date(ts * 1000).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
</script>
