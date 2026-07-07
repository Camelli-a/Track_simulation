<!-- ECharts 通用容器：传入 option 即可渲染图表 -->
<template>
  <div ref="chartRef" :style="{ width: '100%', height: height }" />
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '300px' },
})

const chartRef = ref(null)
let chart = null

onMounted(() => {
  chart = echarts.init(chartRef.value, 'dark')
  chart.setOption(props.option)
  window.addEventListener('resize', resize)
})

watch(() => props.option, (opt) => chart?.setOption(opt), { deep: true })

function resize() { chart?.resize() }

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
})
</script>
