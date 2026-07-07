<template>
  <div>
    <h2 class="text-xl font-semibold mb-6">车辆仿真</h2>

    <div v-if="store.loading" class="text-gray-400">加载中...</div>

    <template v-else-if="store.status">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatusCard label="车辆编号" :value="store.status.vehicle_id" />
        <StatusCard label="速度"     :value="store.status.speed"     unit="km/h" />
        <StatusCard label="里程位置" :value="store.status.position"  unit="m"   />
        <StatusCard label="加速度"   :value="store.status.acceleration" unit="m/s²" />
      </div>

      <!-- TODO: 速度-时间图表 -->
      <EChartsContainer :option="chartOption" height="320px" />
    </template>
  </div>
</template>

<script setup>
import { onMounted, computed } from 'vue'
import { useVehicleStore } from '@/stores/vehicle'
import StatusCard from '@/components/StatusCard.vue'
import EChartsContainer from '@/components/EChartsContainer.vue'

const store = useVehicleStore()
onMounted(() => store.fetchStatus())

const chartOption = computed(() => ({
  title: { text: '速度-时间曲线（占位）', textStyle: { color: '#9ca3af', fontSize: 13 } },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: [] },
  yAxis: { type: 'value' },
  series: [],
}))
</script>
