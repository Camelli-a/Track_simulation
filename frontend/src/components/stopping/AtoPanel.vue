<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">ATO</p>
        <h3 class="app-section-title">ATO 面板</h3>
        <p class="app-section-copy">
          这里将展示目标速度、目标位置、ATO 输出级位、停车阶段和停车误差。
        </p>
      </div>
      <span class="app-chip">{{ chipLabel }}</span>
    </div>

    <template v-if="vehicle">
      <div class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[0.72fr_1fr]">
        <article class="rounded-[1.05rem] border border-cyan-500/20 bg-cyan-500/10 px-4 py-4">
          <p class="text-[11px] uppercase tracking-[0.22em] text-cyan-200/70">ATO Summary</p>
          <h4 class="mt-2 text-lg font-semibold text-slate-100">{{ parkingPhaseText }}</h4>
          <p class="mt-3 text-sm leading-6 text-slate-200">{{ atoSummary }}</p>

          <div class="mt-4 grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">目标速度</p>
              <p class="mt-1 text-sm text-slate-200">{{ targetSpeed != null ? `${Math.round(targetSpeed)} km/h` : '—' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">停车误差</p>
              <p class="mt-1 text-sm text-slate-200">{{ stopErrorCm != null ? `${stopErrorCm} cm` : '—' }}</p>
            </div>
          </div>
        </article>

        <article class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-4">
          <div v-if="latestAtoCommand" class="grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">目标速度</p>
              <p class="mt-1 text-sm text-slate-200">{{ Math.round(latestAtoCommand.target_speed ?? 0) }} km/h</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">目标位置</p>
              <p class="mt-1 text-sm text-slate-200">{{ latestAtoCommand.target_position != null ? `${Math.round(latestAtoCommand.target_position)} m` : '—' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">牵引级位</p>
              <p class="mt-1 text-sm text-slate-200">T{{ latestAtoCommand.traction_level ?? 0 }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">制动级位</p>
              <p class="mt-1 text-sm text-slate-200">B{{ latestAtoCommand.brake_level ?? 0 }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">控制模式</p>
              <p class="mt-1 text-sm text-slate-200">{{ latestAtoCommand.control_mode ?? 'ato' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">更新时间</p>
              <p class="mt-1 text-sm text-slate-200">{{ atoUpdatedAtText }}</p>
            </div>
            <div class="app-metric-tile col-span-2">
              <p class="app-metric-label">下发原因</p>
              <p class="mt-1 text-sm text-slate-200">{{ latestAtoCommand.reason ?? '—' }}</p>
            </div>
          </div>

          <div
            v-else
            class="rounded-[1rem] border border-dashed border-white/10 bg-black/10 px-4 py-6 text-sm text-slate-500"
          >
            当前还没有收到这辆车的 ATO 命令回显。若这辆车处于自动模式，建议先核对后端是否已把 `ato_commands` 推入 dashboard 快照。
          </div>
        </article>
      </div>
    </template>

    <div
      v-else
      class="mt-4 rounded-[1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-sm text-slate-500"
    >
      当前没有关注车辆，ATO 面板暂时无法展开。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useStoppingAnalysis } from '@/composables/useStoppingAnalysis'

const {
  vehicle,
  latestAtoCommand,
  targetSpeed,
  stopErrorCm,
  parkingPhaseText,
} = useStoppingAnalysis()

const chipLabel = computed(() => latestAtoCommand.value ? '已有 ATO 回显' : '等待 ATO 回显')

const atoSummary = computed(() => {
  if (!vehicle.value) return '—'
  if (vehicle.value.mode === 'manual') {
    return '当前车辆仍以手动驾驶为主，ATO 更像参考目标或后台计算输出，重点看目标速度和停车阶段是否合理。'
  }
  if (vehicle.value.emergency_brake) {
    return '当前 ATP 已经抢权，ATO 输出仅供追溯，不再是当前的主导控制来源。'
  }
  return '当前车辆可按 ATO 目标继续观察进站、减速、对标和停稳过程。'
})

const atoUpdatedAtText = computed(() => {
  if (!latestAtoCommand.value?.updated_at) return '等待回显'
  const raw = latestAtoCommand.value.updated_at
  const numeric = Number(raw)
  const timestamp = Number.isFinite(numeric) ? (numeric > 1e12 ? numeric : numeric * 1000) : Date.parse(raw)
  if (!Number.isFinite(timestamp)) return '等待回显'
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
})
</script>
