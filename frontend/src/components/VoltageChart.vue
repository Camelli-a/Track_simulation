<!-- 实时网压 / 电流波动图 -->
<template>
  <EChartsContainer :option="option" height="280px" />
</template>

<script setup>
import { computed } from 'vue'
import EChartsContainer from '@/components/EChartsContainer.vue'

const props = defineProps({
  voltageHistory: { type: Array, default: () => [] },
  timeLabels: { type: Array, default: () => [] },
})

const option = computed(() => ({
  title: {
    text: '接触网电压 / 电流',
    textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
  },
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#1f2937',
    borderColor: '#374151',
    textStyle: { color: '#e5e7eb' },
  },
  legend: {
    data: ['电压 (V)', '电流 (A)'],
    textStyle: { color: '#9ca3af' },
    top: 4,
    right: 0,
  },
  grid: { left: 48, right: 48, top: 48, bottom: 32 },
  xAxis: {
    type: 'category',
    data: props.timeLabels,
    axisLabel: { color: '#6b7280', fontSize: 10 },
    axisLine: { lineStyle: { color: '#374151' } },
  },
  yAxis: [
    {
      type: 'value',
      name: 'V',
      nameTextStyle: { color: '#6b7280' },
      axisLabel: { color: '#6b7280' },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    {
      type: 'value',
      name: 'A',
      nameTextStyle: { color: '#6b7280' },
      axisLabel: { color: '#6b7280' },
      splitLine: { show: false },
    },
  ],
  series: [
    {
      name: '电压 (V)',
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: { color: '#38bdf8' },
      itemStyle: { color: '#38bdf8' },
      data: props.voltageHistory.map((p) => p.voltage),
    },
    {
      name: '电流 (A)',
      type: 'line',
      smooth: true,
      showSymbol: false,
      yAxisIndex: 1,
      lineStyle: { color: '#fb923c' },
      itemStyle: { color: '#fb923c' },
      data: props.voltageHistory.map((p) => p.current),
    },
  ],
}))
</script>
