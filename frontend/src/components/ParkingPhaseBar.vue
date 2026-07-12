<!-- 进站阶段指示（ATO/ATP 停车流程） -->
<template>
  <div>
    <div class="flex items-center justify-between text-xs mb-2">
      <span class="text-gray-400">进站阶段</span>
      <span class="font-medium" :class="phaseTextClass">{{ phaseLabel(phase) }}</span>
    </div>
    <div class="flex gap-1">
      <div
        v-for="step in steps"
        :key="step.id"
        class="flex-1 h-1.5 rounded-full transition-colors duration-300"
        :class="stepClass(step.id)"
        :title="phaseLabel(step.id)"
      />
    </div>
    <div class="flex justify-between text-[10px] text-gray-600 mt-1">
      <span v-for="step in steps" :key="`lbl-${step.id}`" class="flex-1 text-center truncate px-0.5">
        {{ step.short }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { parkingPhaseLabel } from '@/adapters/simulation'

const props = defineProps({
  phase: { type: String, default: 'cruising' },
})

const steps = [
  { id: 'cruising', short: '运行' },
  { id: 'approaching', short: '接近' },
  { id: 'braking', short: '制动' },
  { id: 'docking', short: '对标' },
  { id: 'stopped', short: '停稳' },
]

const phaseIndex = computed(() =>
  steps.findIndex((s) => s.id === props.phase)
)

function stepClass(stepId) {
  const idx = steps.findIndex((s) => s.id === stepId)
  const current = phaseIndex.value
  if (idx < 0) return 'bg-gray-800'
  if (idx < current) return 'bg-emerald-500'
  if (idx === current) return 'bg-sky-400 animate-pulse'
  return 'bg-gray-800'
}

function phaseLabel(phase) {
  return parkingPhaseLabel(phase)
}

const phaseTextClass = computed(() => {
  if (props.phase === 'stopped') return 'text-emerald-400'
  if (props.phase === 'docking') return 'text-sky-400'
  if (props.phase === 'braking') return 'text-amber-400'
  return 'text-gray-400'
})
</script>
