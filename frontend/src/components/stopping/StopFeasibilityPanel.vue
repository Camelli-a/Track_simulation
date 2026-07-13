<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Stop Feasibility</p>
        <h3 class="app-section-title">停车可达性判断</h3>
        <p class="app-section-copy">
          这里直接回答：这辆车按当前速度、MA 和制动能力，还能不能安全停住。
        </p>
      </div>
    </div>

    <div
      v-if="vehicle"
      class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3"
    >
      <article
        v-for="item in metrics"
        :key="item.label"
        class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-4"
      >
        <p class="app-metric-label">{{ item.label }}</p>
        <p class="mt-2 text-lg font-semibold text-slate-100">{{ item.value }}</p>
        <p class="mt-2 text-xs leading-5 text-slate-500">{{ item.hint }}</p>
      </article>
    </div>

    <div
      v-else
      class="mt-4 rounded-[1.1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500"
    >
      当前没有可分析的车辆，停车可达性判断暂时无法展开。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useFocusedVehicle } from '@/composables/useFocusedVehicle'

const { focusedVehicle: vehicle } = useFocusedVehicle()

const metrics = computed(() => {
  const current = vehicle.value
  if (!current) return []

  return [
    {
      label: '当前速度',
      value: `${Math.round(current.speed ?? 0)} km/h`,
      hint: '当前车辆实时速度',
    },
    {
      label: '目标速度',
      value: current.target_speed != null ? `${Math.round(current.target_speed)} km/h` : '—',
      hint: '来自当前控制目标速度',
    },
    {
      label: '距离停车点',
      value: current.stop_distance != null ? `${Math.max(0, current.stop_distance).toFixed(1)} m` : '—',
      hint: '用于判断是否进入停车流程',
    },
    {
      label: '距离 MA',
      value: current.distance_to_ma != null ? `${Math.max(0, current.distance_to_ma).toFixed(1)} m` : '—',
      hint: '当前授权边界剩余距离',
    },
    {
      label: '常用制动停车距离',
      value: current.required_stop_distance != null ? `${current.required_stop_distance.toFixed(1)} m` : '—',
      hint: '用于判断 ATO 是否还在可控区',
    },
    {
      label: '紧急制动停车距离',
      value: current.emergency_stop_distance != null ? `${current.emergency_stop_distance.toFixed(1)} m` : '—',
      hint: '用于判断 ATP 兜底是否还来得及',
    },
  ]
})
</script>
