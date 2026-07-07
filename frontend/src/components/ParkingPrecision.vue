<!-- 停车杯 · 对标停车精度（F4.1） -->
<template>
  <div class="rounded-xl bg-gray-950/60 border border-gray-800 p-4">
    <div class="flex items-center justify-between mb-3">
      <p class="text-xs text-gray-500">对标停车精度</p>
      <span
        v-if="currentError != null"
        class="text-xs px-2 py-0.5 rounded-full"
        :class="gradeClass"
      >{{ gradeLabel }}</span>
    </div>

    <div v-if="currentError != null" class="text-center mb-3">
      <p class="text-3xl font-bold tabular-nums" :class="gradeTextClass">
        ±{{ currentError }}
        <span class="text-sm font-normal text-gray-500">cm</span>
      </p>
      <p class="text-xs text-gray-500 mt-1">当前到站误差估算</p>
    </div>
    <div v-else class="text-center py-4 text-xs text-gray-600">
      列车减速进站后显示厘米级误差
    </div>

    <div v-if="records.length" class="mt-3 border-t border-gray-800 pt-3">
      <p class="text-[10px] text-gray-600 mb-2">历史到站记录</p>
      <div class="space-y-1 max-h-24 overflow-y-auto">
        <div
          v-for="(r, i) in records.slice().reverse().slice(0, 5)"
          :key="i"
          class="flex justify-between text-xs"
        >
          <span class="text-gray-500">{{ r.station }}</span>
          <span :class="r.errorCm <= 10 ? 'text-emerald-400' : r.errorCm <= 30 ? 'text-amber-400' : 'text-red-400'">
            ±{{ r.errorCm }} cm
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  currentError: { type: Number, default: null },
  records: { type: Array, default: () => [] },
})

const gradeLabel = computed(() => {
  if (props.currentError == null) return ''
  if (props.currentError <= 10) return '优秀'
  if (props.currentError <= 30) return '合格'
  return '待改进'
})

const gradeClass = computed(() => {
  if (props.currentError == null) return ''
  if (props.currentError <= 10) return 'bg-emerald-950 text-emerald-400'
  if (props.currentError <= 30) return 'bg-amber-950 text-amber-400'
  return 'bg-red-950 text-red-400'
})

const gradeTextClass = computed(() => {
  if (props.currentError == null) return 'text-gray-400'
  if (props.currentError <= 10) return 'text-emerald-400'
  if (props.currentError <= 30) return 'text-amber-400'
  return 'text-red-400'
})
</script>
