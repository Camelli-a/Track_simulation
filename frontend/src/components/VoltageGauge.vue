<!-- 网压表（F5.2）：标称 1500V 直流接触网 -->
<template>
  <div class="flex flex-col items-center">
    <svg viewBox="0 0 220 140" class="w-full max-w-[220px]">
      <path
        d="M 30 120 A 80 80 0 0 1 190 120"
        fill="none"
        stroke="#374151"
        stroke-width="10"
        stroke-linecap="round"
      />
      <path
        d="M 30 120 A 80 80 0 0 1 190 120"
        fill="none"
        :stroke="statusColor"
        stroke-width="10"
        stroke-linecap="round"
        :stroke-dasharray="`${voltageArc} 999`"
        class="transition-all duration-200"
      />
      <line
        x1="110" y1="120"
        :x2="needle.x" :y2="needle.y"
        :stroke="statusColor"
        stroke-width="3.5"
        stroke-linecap="round"
        class="transition-all duration-200"
      />
      <circle cx="110" cy="120" r="5" fill="#1f2937" stroke="#6b7280" stroke-width="1.5" />
      <text x="110" y="132" text-anchor="middle" class="text-[9px] fill-gray-500">1500V</text>
    </svg>
    <div class="text-center -mt-2">
      <p class="text-2xl font-bold tabular-nums" :class="statusTextClass">
        {{ voltage.toFixed(1) }}
        <span class="text-sm font-normal text-gray-500">V</span>
      </p>
      <p class="text-xs text-gray-500 mt-0.5">{{ statusLabel }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  voltage: { type: Number, default: 1500 },
  isFault: { type: Boolean, default: false },
  min: { type: Number, default: 1300 },
  max: { type: Number, default: 1700 },
})

const arcLength = 251.2

const normalized = computed(() =>
  Math.max(0, Math.min(1, (props.voltage - props.min) / (props.max - props.min)))
)

const voltageArc = computed(() => normalized.value * arcLength)

const needle = computed(() => {
  const angle = Math.PI + normalized.value * Math.PI
  const r = 62
  return { x: 110 + r * Math.cos(angle), y: 120 + r * Math.sin(angle) }
})

const statusColor = computed(() => {
  if (props.isFault || props.voltage < 1400 || props.voltage > 1600) return '#ef4444'
  if (props.voltage < 1450 || props.voltage > 1550) return '#f59e0b'
  return '#38bdf8'
})

const statusTextClass = computed(() => {
  if (props.isFault || props.voltage < 1400 || props.voltage > 1600) return 'text-red-400'
  if (props.voltage < 1450 || props.voltage > 1550) return 'text-amber-400'
  return 'text-sky-300'
})

const statusLabel = computed(() => {
  if (props.isFault) return '供电故障'
  if (props.voltage < 1400) return '严重欠压'
  if (props.voltage > 1600) return '过压告警'
  if (props.voltage < 1450) return '电压偏低'
  if (props.voltage > 1550) return '电压偏高'
  return '网压正常'
})
</script>
