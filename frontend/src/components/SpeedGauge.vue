<!-- 双指针速度表：实际车速 + 目标限速（F5.2） -->
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
        :stroke="overspeed ? '#ef4444' : '#10b981'"
        stroke-width="10"
        stroke-linecap="round"
        :stroke-dasharray="`${speedArc} 999`"
        class="transition-all duration-200"
      />
      <!-- 目标限速指针（短针，琥珀色） -->
      <line
        x1="110" y1="120"
        :x2="limitNeedle.x" :y2="limitNeedle.y"
        stroke="#f59e0b"
        stroke-width="3"
        stroke-linecap="round"
        opacity="0.9"
      />
      <circle cx="110" cy="120" r="5" fill="#1f2937" stroke="#6b7280" stroke-width="1.5" />
      <!-- 实际速度指针（长针，白色） -->
      <line
        x1="110" y1="120"
        :x2="speedNeedle.x" :y2="speedNeedle.y"
        :stroke="overspeed ? '#ef4444' : '#f3f4f6'"
        stroke-width="3.5"
        stroke-linecap="round"
        class="transition-all duration-200"
      />
      <!-- 刻度 -->
      <text
        v-for="tick in ticks"
        :key="tick.value"
        :x="tick.x" :y="tick.y"
        text-anchor="middle"
        class="text-[9px] fill-gray-500"
      >{{ tick.value }}</text>
    </svg>
    <div class="text-center -mt-2">
      <p class="text-2xl font-bold tabular-nums" :class="overspeed ? 'text-red-400' : 'text-gray-100'">
        {{ speed.toFixed(1) }}
        <span class="text-sm font-normal text-gray-500">km/h</span>
      </p>
      <p class="text-xs text-gray-500 mt-0.5">
        限速 <span class="text-amber-400">{{ limit.toFixed(1) }}</span> km/h
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  speed: { type: Number, default: 0 },
  limit: { type: Number, default: 80 },
  max: { type: Number, default: 120 },
})

const overspeed = computed(() => props.speed > props.limit + 0.5)

const arcLength = 251.2 // ≈ π * 80

const speedArc = computed(() => (Math.min(props.speed, props.max) / props.max) * arcLength)

function needleCoords(value) {
  const angle = Math.PI + (Math.min(value, props.max) / props.max) * Math.PI
  const r = 62
  return {
    x: 110 + r * Math.cos(angle),
    y: 120 + r * Math.sin(angle),
  }
}

const speedNeedle = computed(() => needleCoords(props.speed))
const limitNeedle = computed(() => needleCoords(props.limit))

const ticks = computed(() =>
  [0, 30, 60, 90, 120].map((value) => {
    const angle = Math.PI + (value / props.max) * Math.PI
    const r = 72
    return {
      value,
      x: 110 + r * Math.cos(angle),
      y: 120 + r * Math.sin(angle) + 4,
    }
  })
)
</script>
