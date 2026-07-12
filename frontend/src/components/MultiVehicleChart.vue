<!-- 多车速度-位置追踪曲线 -->
<template>
  <EChartsContainer :option="option" height="280px" />
</template>

<script setup>
import { computed } from 'vue'
import EChartsContainer from '@/components/EChartsContainer.vue'

const props = defineProps({
  vehicleHistory: { type: Object, default: () => ({}) },
  timeLabels: { type: Array, default: () => [] },
  colorFn: { type: Function, required: true },
})

const option = computed(() => {
  const series = Object.entries(props.vehicleHistory).map(([id, points]) => ({
    name: id,
    type: 'line',
    smooth: true,
    showSymbol: false,
    lineStyle: { width: 2, color: props.colorFn(id) },
    itemStyle: { color: props.colorFn(id) },
    data: points.map((p) => p.speed),
  }))

  return {
    title: {
      text: '多车速度追踪',
      textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
    },
    legend: {
      data: Object.keys(props.vehicleHistory),
      textStyle: { color: '#9ca3af' },
      top: 4,
      right: 0,
    },
    grid: { left: 48, right: 16, top: 48, bottom: 32 },
    xAxis: {
      type: 'category',
      data: props.timeLabels,
      axisLabel: { color: '#6b7280', fontSize: 10 },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    yAxis: {
      type: 'value',
      name: 'km/h',
      nameTextStyle: { color: '#6b7280' },
      axisLabel: { color: '#6b7280' },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    series,
  }
})
</script>
