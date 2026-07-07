<template>
  <div>
    <h2 class="text-xl font-semibold mb-6">轨道仿真</h2>

    <div v-if="store.loading" class="text-gray-400">加载中...</div>

    <template v-else-if="store.status">
      <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
        <StatusCard label="总长度"   :value="store.status.total_length" unit="m" />
        <StatusCard label="分段数"   :value="store.status.segments?.length" />
        <StatusCard label="故障段数" :value="store.status.fault_count" />
      </div>

      <!-- TODO: 轨道分段状态可视化 -->
      <EChartsContainer :option="chartOption" height="320px" />
    </template>
  </div>
</template>

<script setup>
import { onMounted, computed } from 'vue'
import { useTrackStore } from '@/stores/track'
import StatusCard from '@/components/StatusCard.vue'
import EChartsContainer from '@/components/EChartsContainer.vue'

const store = useTrackStore()
onMounted(() => store.fetchStatus())

const chartOption = computed(() => ({
  title: { text: '轨道分段状态（占位）', textStyle: { color: '#9ca3af', fontSize: 13 } },
  tooltip: {},
  xAxis: { type: 'category', data: [] },
  yAxis: { type: 'value' },
  series: [],
}))
</script>
