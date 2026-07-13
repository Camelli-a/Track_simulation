<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">MA Reason</p>
        <h3 class="app-section-title">MA 来源解释</h3>
        <p class="app-section-copy">
          这里将把 MA 值、限速、制动边界和前车保护信息翻译成可讲解结论。
        </p>
      </div>
    </div>

    <template v-if="vehicle && maReasonSummary">
      <div class="mt-4 rounded-[1.05rem] border border-cyan-500/20 bg-cyan-500/10 px-4 py-4">
        <p class="text-[11px] uppercase tracking-[0.22em] text-cyan-200/70">Reason Summary</p>
        <h4 class="mt-2 text-lg font-semibold text-slate-100">{{ maReasonSummary.title }}</h4>
        <p class="mt-3 text-sm leading-6 text-slate-200">{{ maReasonSummary.detail }}</p>
      </div>

      <div class="mt-4 grid grid-cols-1 gap-3">
        <article
          v-for="item in details"
          :key="item.label"
          class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-4"
        >
          <p class="app-metric-label">{{ item.label }}</p>
          <p class="mt-2 text-lg font-semibold text-slate-100">{{ item.value }}</p>
          <p class="mt-2 text-xs leading-5 text-slate-500">{{ item.hint }}</p>
        </article>
      </div>

      <div class="mt-4 rounded-[1rem] border border-white/10 bg-black/10 px-4 py-4">
        <p class="text-sm font-medium text-slate-100">可直接讲解的三句话</p>
        <ul class="mt-3 space-y-2 text-sm leading-6 text-slate-300">
          <li v-for="bullet in maReasonSummary.bullets" :key="bullet">- {{ bullet }}</li>
        </ul>
      </div>
    </template>

    <div
      v-else
      class="mt-4 rounded-[1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-sm text-slate-500"
    >
      当前没有关注车辆，MA 来源解释暂时无法展开。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useSignalConstraint } from '@/composables/useSignalConstraint'

const { vehicle, authority, maReasonSummary } = useSignalConstraint()

const details = computed(() => {
  if (!vehicle.value) return []
  return [
    {
      label: 'MA 边界',
      value: vehicle.value.ma_limit != null ? `${Math.round(vehicle.value.ma_limit)} m` : '—',
      hint: '当前移动授权的直接终点',
    },
    {
      label: '距离 MA',
      value: vehicle.value.distance_to_ma != null ? `${Math.max(0, vehicle.value.distance_to_ma).toFixed(1)} m` : '—',
      hint: '判断列车还能向前跑多远',
    },
    {
      label: '限速',
      value: authority.value?.speed_limit != null
        ? `${Math.round(authority.value.speed_limit)} km/h`
        : (vehicle.value.ma_speed_limit != null ? `${Math.round(vehicle.value.ma_speed_limit)} km/h` : '—'),
      hint: '若后端已上报 authority.speed_limit，这里优先使用 authority',
    },
    {
      label: '常用制动距离',
      value: authority.value?.required_stop_distance != null
        ? `${authority.value.required_stop_distance.toFixed(1)} m`
        : (vehicle.value.ma_required_stop_distance != null ? `${vehicle.value.ma_required_stop_distance.toFixed(1)} m` : '—'),
      hint: '反映 ATO 当前理论停车能力',
    },
    {
      label: '紧急制动距离',
      value: authority.value?.emergency_stop_distance != null
        ? `${authority.value.emergency_stop_distance.toFixed(1)} m`
        : (vehicle.value.ma_emergency_stop_distance != null ? `${vehicle.value.ma_emergency_stop_distance.toFixed(1)} m` : '—'),
      hint: '反映 ATP 最后兜底能力',
    },
    {
      label: '前车 / 安全间距',
      value: vehicle.value.ma_front_vehicle_id ?? '无前车',
      hint: vehicle.value.ma_safe_distance != null ? `安全间距 ${vehicle.value.ma_safe_distance} m` : '当前未上报安全间距',
    },
  ]
})
</script>
