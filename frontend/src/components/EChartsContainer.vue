<!-- ECharts 通用容器：按需加载以减小首屏体积 -->
<template>
  <div ref="chartRef" :style="{ width: '100%', height: height }" />
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '300px' },
})

const chartRef = ref(null)
let chart = null
let echarts = null

onMounted(async () => {
  const mod = await import('echarts')
  echarts = mod.default ?? mod
  chart = echarts.init(chartRef.value, 'dark')
  chart.setOption(props.option)
  window.addEventListener('resize', resize)
})

watch(() => props.option, (opt) => chart?.setOption(opt, { notMerge: false }), { deep: true })

function resize() { chart?.resize() }

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
})
</script>
