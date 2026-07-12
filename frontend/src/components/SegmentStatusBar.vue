<!-- 闭塞分区状态条：轨道/信号页复用 -->
<template>
  <div class="rounded-xl border border-gray-800 overflow-hidden">
    <div class="flex h-10">
      <div
        v-for="seg in segments"
        :key="seg.segment_id"
        class="flex-1 border-r border-gray-900/80 last:border-r-0 flex items-end justify-center pb-0.5 transition-colors duration-300"
        :class="segmentClass(seg)"
        :title="`${seg.segment_id} ${seg.start}-${seg.end}m`"
      >
        <span class="text-[8px] text-gray-500/70 truncate px-0.5">{{ seg.segment_id }}</span>
      </div>
    </div>
    <div v-if="showLabels" class="flex text-[9px] text-gray-600 px-1 py-1 gap-1">
      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-sm bg-emerald-900/60" />空闲</span>
      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-sm bg-yellow-900/50" />接近</span>
      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-sm bg-red-900/70" />占用</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  segments: { type: Array, default: () => [] },
  showLabels: { type: Boolean, default: true },
})

function segmentClass(seg) {
  const aspect = seg.aspect ?? (seg.occupied ? 'red' : 'green')
  if (aspect === 'red' || seg.occupied) return 'bg-red-900/70'
  if (aspect === 'yellow') return 'bg-yellow-900/50'
  return 'bg-emerald-900/40'
}
</script>
