<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Primary Chart</p>
        <h3 class="app-section-title">速度-距离主图</h3>
        <p class="app-section-copy">
          这里将叠加实际速度、目标速度、MA 边界、停车点和 ATP 风险边界。
        </p>
      </div>
    </div>

    <template v-if="vehicle">
      <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
        <article
          v-for="item in summaryCards"
          :key="item.label"
          class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-4"
        >
          <p class="app-metric-label">{{ item.label }}</p>
          <p class="mt-2 text-lg font-semibold text-slate-100">{{ item.value }}</p>
          <p class="mt-2 text-xs leading-5 text-slate-500">{{ item.hint }}</p>
        </article>
      </div>

      <div class="mt-4 rounded-[1.1rem] border border-white/10 bg-black/10 px-3 py-3">
        <EChartsContainer :option="chartOption" height="360px" />
      </div>
    </template>

    <div
      v-else
      class="mt-4 rounded-[1.1rem] border border-dashed border-white/10 bg-black/10 px-4 py-12 text-sm text-slate-500"
    >
      当前还没有关注车辆，速度-距离主图暂时无法展开。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import EChartsContainer from '@/components/EChartsContainer.vue'
import { useStoppingAnalysis } from '@/composables/useStoppingAnalysis'

const {
  vehicle,
  targetSpeed,
  distanceToMa,
  serviceMargin,
  emergencyMargin,
  chartOption,
} = useStoppingAnalysis()

const summaryCards = computed(() => {
  if (!vehicle.value) return []
  return [
    {
      label: '当前速度',
      value: `${Math.round(vehicle.value.speed ?? 0)} km/h`,
      hint: '主图的实际起点速度',
    },
    {
      label: '目标速度',
      value: targetSpeed.value != null ? `${Math.round(targetSpeed.value)} km/h` : '—',
      hint: '用于判断当前是否偏离停车控制目标',
    },
    {
      label: '常用制动裕量',
      value: serviceMargin.value != null ? `${serviceMargin.value.toFixed(1)} m` : '—',
      hint: '距离 MA 减去常用制动停车距离后的余量',
    },
    {
      label: '紧急制动裕量',
      value: emergencyMargin.value != null ? `${emergencyMargin.value.toFixed(1)} m` : '—',
      hint: distanceToMa.value != null ? '用于判断 ATP 兜底是否仍来得及' : '当前尚未拿到 MA 距离',
    },
  ]
})
</script>
