<!-- 运行占线时间轴：里程 × 时间热力图（OCC 档3） -->
<template>
  <EChartsContainer :option="option" :height="height" />
</template>

<script setup>
import { computed } from 'vue'
import EChartsContainer from '@/components/EChartsContainer.vue'

const props = defineProps({
  occupancyHistory: { type: Array, default: () => [] },
  timeLabels: { type: Array, default: () => [] },
  totalLength: { type: Number, default: 47500 },
  stations: { type: Array, default: () => [] },
  binCount: { type: Number, default: 48 },
  height: { type: String, default: '280px' },
})

const yLabels = computed(() => {
  const n = props.binCount
  const step = props.totalLength / n
  return Array.from({ length: n }, (_, i) => {
    const km = ((n - 1 - i) * step) / 1000
    return `${km.toFixed(1)}`
  })
})

const option = computed(() => {
  const cols = props.timeLabels.length
  const rows = props.binCount
  const data = []

  props.occupancyHistory.forEach((row, xIdx) => {
    if (!row) return
    row.forEach((val, yIdx) => {
      if (val > 0) data.push([xIdx, yIdx, val])
    })
  })

  const stationMarks = props.stations
    .filter((s) => s.position != null)
    .map((s) => {
      const binIdx = rows - 1 - Math.floor((s.position / props.totalLength) * rows)
      return {
        yAxis: Math.max(0, Math.min(rows - 1, binIdx)),
        name: s.name,
      }
    })

  return {
    title: {
      text: '运行占线时间轴',
      subtext: '纵轴里程 · 横轴时间 · 红=占用 黄=接近 绿=空闲',
      textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
      subtextStyle: { color: '#4b5563', fontSize: 10 },
    },
    tooltip: {
      position: 'top',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 11 },
      formatter(p) {
        if (!p.data) return ''
        const [xIdx, yIdx, val] = p.data
        const km = ((rows - 1 - yIdx) * (props.totalLength / rows) / 1000).toFixed(2)
        const labels = ['空闲', '接近', '占用']
        return `${props.timeLabels[xIdx] ?? ''}<br/>${km} km · ${labels[val] ?? val}`
      },
    },
    grid: { left: 52, right: 12, top: 56, bottom: 28 },
    xAxis: {
      type: 'category',
      data: props.timeLabels,
      splitArea: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 9, interval: Math.max(0, Math.floor(cols / 8) - 1) },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    yAxis: {
      type: 'category',
      data: yLabels.value,
      name: 'km',
      nameTextStyle: { color: '#6b7280', fontSize: 10 },
      axisLabel: { color: '#6b7280', fontSize: 9, interval: Math.max(0, Math.floor(rows / 6) - 1) },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    visualMap: {
      min: 0,
      max: 2,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 12,
      itemHeight: 8,
      text: ['占用', '空闲'],
      textStyle: { color: '#6b7280', fontSize: 10 },
      inRange: {
        color: ['#0f172a', '#854d0e', '#991b1b'],
      },
    },
    series: [
      {
        type: 'heatmap',
        data,
        emphasis: {
          itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.4)' },
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#38bdf8', type: 'dashed', width: 1, opacity: 0.35 },
          label: {
            show: true,
            position: 'insideStartTop',
            color: '#7dd3fc',
            fontSize: 9,
            formatter: '{b}',
          },
          data: stationMarks.map((m) => [{ yAxis: m.yAxis, name: m.name }]),
        },
      },
    ],
  }
})
</script>
