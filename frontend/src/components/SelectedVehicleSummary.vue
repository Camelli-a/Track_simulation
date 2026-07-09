<template>
  <div class="app-panel" :class="selected ? 'border-sky-800/70 bg-sky-950/16' : ''">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">
          当前关注列车
        </p>
        <h3 class="mt-2 text-lg font-semibold text-white">
          {{ selected ? selected.vehicle_id : '尚未选中列车' }}
        </h3>
        <p class="app-section-copy">
          {{ description }}
        </p>
      </div>

      <span
        v-if="selected"
        class="rounded-full px-3 py-1 text-xs font-medium"
        :style="badgeStyle"
      >
        {{ modeText }}
      </span>
    </div>

    <div v-if="selected" class="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
      <div class="app-metric-tile">
        <p class="app-metric-label">位置</p>
        <p class="mt-1 text-sm font-medium text-gray-100">{{ Math.round(selected.position) }} m</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">速度</p>
        <p class="mt-1 text-sm font-medium text-gray-100">{{ Math.round(selected.speed) }} km/h</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">MA 剩余</p>
        <p class="mt-1 text-sm font-medium" :class="maRemainingClass">
          {{ maRemainingText }}
        </p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">状态</p>
        <p class="mt-1 text-sm font-medium" :class="selected.emergency_brake ? 'text-red-300' : 'text-emerald-300'">
          {{ selected.emergency_brake ? '紧急制动中' : '运行中' }}
        </p>
      </div>
    </div>

    <div v-if="selected && insight" class="mt-5 rounded-[1rem] border border-white/8 bg-white/[0.03] px-4 py-3 text-sm leading-6 text-gray-300">
      {{ insight }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { modeLabel } from '@/adapters/simulation'

const props = defineProps({
  vehicle: { type: Object, default: null },
  color: { type: Function, required: true },
  description: { type: String, default: '点击沙盘、时间线或其他页面中的列车后，这里会同步显示它的关键状态。' },
  insight: { type: String, default: '' },
})

const selected = computed(() => props.vehicle)

const modeText = computed(() => modeLabel(selected.value?.mode))

const badgeStyle = computed(() => {
  if (!selected.value) return {}
  const color = props.color(selected.value.vehicle_id)
  return {
    color,
    backgroundColor: `${color}22`,
    border: `1px solid ${color}44`,
  }
})

const maRemaining = computed(() => {
  if (!selected.value || selected.value.ma_limit == null) return null
  return selected.value.ma_limit - selected.value.position
})

const maRemainingText = computed(() => {
  if (maRemaining.value == null) return '—'
  return `${Math.max(0, maRemaining.value).toFixed(1)} m`
})

const maRemainingClass = computed(() => {
  if (maRemaining.value == null) return 'text-gray-200'
  if (maRemaining.value < 120) return 'text-amber-300'
  return 'text-sky-300'
})
</script>
