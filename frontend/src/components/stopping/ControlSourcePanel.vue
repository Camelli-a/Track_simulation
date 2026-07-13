<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Control Source</p>
        <h3 class="app-section-title">控制来源对照</h3>
        <p class="app-section-copy">
          这里将并排展示司机输入与 ATO 指令，并给出当前主要控制来源标签。
        </p>
      </div>
    </div>

    <div class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[0.55fr_1fr_1fr]">
      <article class="rounded-[1.05rem] border border-cyan-500/20 bg-cyan-500/10 px-4 py-4">
        <p class="text-[11px] uppercase tracking-[0.22em] text-cyan-200/70">Primary Source</p>
        <h4 class="mt-2 text-lg font-semibold text-slate-100">{{ sourceLabel }}</h4>
        <p class="mt-3 text-sm leading-6 text-slate-200">{{ sourceSummary }}</p>
      </article>

      <article class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-4">
        <p class="text-[11px] uppercase tracking-[0.22em] text-slate-500">Driver Input</p>
        <template v-if="latestDriverInput">
          <div class="mt-3 grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">牵引 / 制动</p>
              <p class="mt-1 text-sm text-slate-200">{{ latestDriverInput.traction_level }} / {{ latestDriverInput.brake_level }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">方向 / 模式</p>
              <p class="mt-1 text-sm text-slate-200">{{ latestDriverInput.direction }} / {{ latestDriverInput.control_mode }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">来源</p>
              <p class="mt-1 text-sm text-slate-200">{{ latestDriverInput.source }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">紧急按钮</p>
              <p class="mt-1 text-sm text-slate-200">{{ latestDriverInput.emergency_button ? '按下' : '未按下' }}</p>
            </div>
          </div>
        </template>
        <div
          v-else
          class="mt-3 rounded-[1rem] border border-dashed border-white/10 bg-black/10 px-4 py-6 text-sm text-slate-500"
        >
          当前还没有看到这辆车的司机输入回显。
        </div>
      </article>

      <article class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-4">
        <p class="text-[11px] uppercase tracking-[0.22em] text-slate-500">ATO Command</p>
        <template v-if="latestAtoCommand">
          <div class="mt-3 grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">目标速度</p>
              <p class="mt-1 text-sm text-slate-200">{{ Math.round(latestAtoCommand.target_speed ?? 0) }} km/h</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">目标位置</p>
              <p class="mt-1 text-sm text-slate-200">{{ latestAtoCommand.target_position != null ? `${Math.round(latestAtoCommand.target_position)} m` : '—' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">牵引 / 制动</p>
              <p class="mt-1 text-sm text-slate-200">{{ latestAtoCommand.traction_level }} / {{ latestAtoCommand.brake_level }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">原因</p>
              <p class="mt-1 text-sm text-slate-200">{{ latestAtoCommand.reason ?? '—' }}</p>
            </div>
          </div>
        </template>
        <div
          v-else
          class="mt-3 rounded-[1rem] border border-dashed border-white/10 bg-black/10 px-4 py-6 text-sm text-slate-500"
        >
          当前还没有看到这辆车的 ATO 指令回显。
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useFocusedVehicle } from '@/composables/useFocusedVehicle'
import { usePageSimulation } from '@/composables/usePageSimulation'

const store = usePageSimulation()
const { focusedVehicle: vehicle } = useFocusedVehicle()

const latestDriverInput = computed(() =>
  store.driverInputs.find((input) => input.vehicle_id === vehicle.value?.vehicle_id) ?? null
)

const latestAtoCommand = computed(() =>
  store.atoCommands.find((command) => command.vehicle_id === vehicle.value?.vehicle_id) ?? null
)

const sourceLabel = computed(() => {
  if (vehicle.value?.emergency_brake) return 'ATP 保护'
  if (vehicle.value?.mode === 'ato') return 'ATO 控制'
  if (vehicle.value?.mode === 'manual') return '司机输入'
  return '待识别'
})

const sourceSummary = computed(() => {
  if (vehicle.value?.emergency_brake) {
    return '当前车辆已进入紧急制动，说明 ATP 已经抢权，后续应重点核对触发原因和停车结果。'
  }
  if (vehicle.value?.mode === 'ato') {
    return '当前以 ATO 指令为主导，重点看目标速度、目标位置和停车阶段是否一致。'
  }
  if (vehicle.value?.mode === 'manual') {
    return '当前以司机输入为主导，重点看司机制动是否跟得上线路约束和推荐速度。'
  }
  return '当前还无法明确主导控制来源。'
})
</script>
