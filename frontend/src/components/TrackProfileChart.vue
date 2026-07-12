<!-- 线路纵断面：使用老师提供的坡度表数据 -->
<template>
  <EChartsContainer :option="option" :height="height" />
</template>

<script setup>
import { computed } from 'vue'
import EChartsContainer from '@/components/EChartsContainer.vue'

const props = defineProps({
  profile: { type: Array, default: () => [] },
  stations: { type: Array, default: () => [] },
  height: { type: String, default: '260px' },
})

const option = computed(() => {
  const positions = props.profile.map((p) => p.position)
  const slopes = props.profile.map((p) => p.slope)

  return {
    title: {
      text: props.profile.length ? '线路纵断面 · 老师坡度数据' : '线路纵断面',
      textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      formatter(params) {
        const p = params[0]
        return `里程 ${p.name} m<br/>坡度 ${p.value} ‰`
      },
    },
    grid: { left: 52, right: 24, top: 48, bottom: 40 },
    xAxis: {
      type: 'category',
      name: '里程 m',
      data: positions,
      axisLabel: { color: '#6b7280', fontSize: 10, interval: Math.floor(positions.length / 12) || 0 },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    yAxis: {
      type: 'value',
      name: '坡度 ‰',
      nameTextStyle: { color: '#6b7280' },
      axisLabel: { color: '#6b7280' },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    series: [{
      type: 'line',
      step: 'end',
      showSymbol: false,
      lineStyle: { color: '#38bdf8', width: 2 },
      areaStyle: { color: 'rgba(56,189,248,0.12)' },
      data: slopes,
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { color: '#64748b', type: 'dashed' },
        data: props.stations.map((st) => ({
          xAxis: String(nearestPos(st.position)),
          label: { formatter: st.name, color: '#94a3b8', fontSize: 10 },
        })),
      },
    }],
  }
})

function nearestPos(target) {
  if (!props.profile.length) return String(target)
  return String(
    props.profile.reduce(
      (best, p) => (Math.abs(p.position - target) < Math.abs(best - target) ? p.position : best),
      props.profile[0].position,
    )
  )
}
</script>
