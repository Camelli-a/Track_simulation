<template>
  <div>
    <h2 class="text-xl font-semibold mb-6">供电仿真</h2>

    <div v-if="store.loading" class="text-gray-400">加载中...</div>

    <template v-else-if="store.status">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatusCard label="电压"   :value="store.status.voltage"   unit="V"  />
        <StatusCard label="电流"   :value="store.status.current"   unit="A"  />
        <StatusCard label="功率"   :value="store.status.power"     unit="kW" />
        <StatusCard label="变电站" :value="store.status.substation_id" />
      </div>

      <!-- TODO: 供电历史折线图 -->
      <EChartsContainer :option="chartOption" height="320px" />
    </template>
  </div>
</template>

<script setup>
import { onMounted, computed } from 'vue'
import { usePowerStore } from '@/stores/power'
import StatusCard from '@/components/StatusCard.vue'
import EChartsContainer from '@/components/EChartsContainer.vue'

const store = usePowerStore()
onMounted(() => store.fetchStatus())

const chartOption = computed(() => ({
  title: { text: '电压 / 电流趋势（占位）', textStyle: { color: '#9ca3af', fontSize: 13 } },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: [] },
  yAxis: { type: 'value' },
  series: [],
}))
</script>
