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
      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-sm bg-sky-900/70" />空闲区段</span>
      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-sm bg-amber-900/60" />临近占用</span>
      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-sm bg-rose-900/70" />已占用</span>
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
  if (aspect === 'red' || seg.occupied) return 'bg-rose-900/70'
  if (aspect === 'yellow') return 'bg-amber-900/60'
  return 'bg-sky-900/55'
}
</script>
