<!-- 对标停车剩余距离条（F5.2 / F4.1） -->
<template>
  <div>
    <div class="flex items-center justify-between text-xs mb-2">
      <span class="text-gray-400">对标停车剩余距离</span>
      <span class="font-mono text-gray-200">
        {{ formattedDistance }} <span class="text-gray-500">m</span>
      </span>
    </div>
    <div class="h-3 rounded-full bg-gray-800 overflow-hidden border border-gray-700">
      <div
        class="h-full rounded-full transition-all duration-200"
        :class="barClass"
        :style="{ width: `${progress}%` }"
      />
    </div>
    <div class="flex justify-between text-[10px] text-gray-600 mt-1">
      <span>到站</span>
      <span>{{ stationName || '—' }}</span>
      <span>远</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  distance: { type: Number, default: null },
  stationName: { type: String, default: '' },
  maxDistance: { type: Number, default: 500 },
})

const formattedDistance = computed(() =>
  props.distance != null ? props.distance.toFixed(1) : '--'
)

const progress = computed(() => {
  if (props.distance == null) return 0
  return Math.max(4, Math.min(100, (1 - props.distance / props.maxDistance) * 100))
})

const barClass = computed(() => {
  if (props.distance == null) return 'bg-gray-600'
  if (props.distance < 50) return 'bg-emerald-500'
  if (props.distance < 200) return 'bg-sky-500'
  return 'bg-indigo-600'
})
</script>
