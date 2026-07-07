<!-- 受控车数字座舱（F5.2 + F3.1 · 按 mode 分支） -->
<template>
  <div
    class="rounded-2xl bg-gray-900 border p-5 transition-colors"
    :class="cockpitBorderClass"
  >
    <div class="flex flex-wrap items-center justify-between gap-3 mb-5">
      <div>
        <h3 class="text-sm font-semibold text-gray-300">数字座舱 · 受控车辆</h3>
        <p class="text-xs text-gray-500 mt-0.5">{{ modeHint }}</p>
      </div>
      <div v-if="vehicle" class="flex flex-wrap items-center gap-2">
        <span class="w-3 h-3 rounded-full" :style="{ backgroundColor: color(vehicle.vehicle_id) }" />
        <span class="text-lg font-bold">{{ vehicle.vehicle_id }}</span>
        <span class="text-xs px-2 py-0.5 rounded-full border" :class="modeBadgeClass">
          {{ modeLabel(vehicle.mode) }}
        </span>
        <span
          v-if="vehicle.emergency_brake"
          class="text-xs px-2 py-0.5 rounded-full bg-red-900 text-red-300 animate-pulse"
        >ATP 紧急制动</span>
      </div>
    </div>

    <!-- 控车指令反馈（仅手动模式） -->
    <div
      v-if="controlFeedback && isManualMode(vehicle?.mode)"
      class="mb-4 px-3 py-2 rounded-lg text-xs border"
      :class="controlFeedback.status === 'error'
        ? 'bg-red-950/50 border-red-800 text-red-300'
        : 'bg-sky-950/50 border-sky-800 text-sky-300'"
    >
      <template v-if="controlFeedback.status === 'ok'">
        ✓ 已发送 <strong>{{ controlFeedback.label }}</strong> → {{ controlFeedback.vehicleId }}
      </template>
      <template v-else-if="controlFeedback.status === 'error'">
        ✗ 指令发送失败：{{ controlFeedback.error ?? '后端未响应' }}
      </template>
      <template v-else>
        … 正在发送 <strong>{{ controlFeedback.label }}</strong>
      </template>
    </div>

    <!-- ATO / ATP 提示条 -->
    <div
      v-if="vehicle && isAutomatedParking(vehicle.mode)"
      class="mb-4 px-3 py-2 rounded-lg text-xs border"
      :class="vehicle.mode === 'ato'
        ? 'bg-sky-950/40 border-sky-800 text-sky-300'
        : 'bg-amber-950/30 border-amber-800/60 text-amber-200'"
    >
      <template v-if="vehicle.mode === 'ato'">
        ATO 自动控制中 · 系统负责减速与对标，驾驶员监控即可
      </template>
      <template v-else>
        ATP 监督模式 · 请确认不超过 MA 与目标限速，必要时可人工干预
      </template>
    </div>

    <!-- ATP 超速 / 接近 MA 警告 -->
    <div
      v-if="vehicle && vehicle.mode === 'atp' && atpWarning"
      class="mb-4 px-3 py-2 rounded-lg bg-amber-950/50 border border-amber-700 text-xs text-amber-200"
    >
      ⚠️ {{ atpWarning }}
    </div>

    <div v-if="vehicle" class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="rounded-xl bg-gray-950/60 border border-gray-800 p-4 flex flex-col items-center">
        <p class="text-xs text-gray-500 mb-2 self-start">
          速度表
          <span v-if="vehicle.mode === 'atp'" class="text-amber-500/80"> · ATP 限速</span>
        </p>
        <SpeedGauge
          :speed="vehicle.speed"
          :limit="vehicle.target_speed ?? 80"
        />
      </div>

      <div class="rounded-xl bg-gray-950/60 border border-gray-800 p-4 flex flex-col items-center">
        <p class="text-xs text-gray-500 mb-2 self-start">接触网电压</p>
        <VoltageGauge :voltage="power?.voltage ?? 1500" :is-fault="power?.is_fault ?? false" />
      </div>

      <div class="rounded-xl bg-gray-950/60 border border-gray-800 p-4 flex flex-col justify-between gap-3">
        <div>
          <p class="text-xs text-gray-500 mb-2">前方站台</p>
          <p class="text-xl font-semibold text-gray-100">{{ vehicle.station_name || '—' }}</p>
          <p class="text-xs text-gray-500 mt-1 font-mono">
            {{ Math.round(vehicle.position) }} m
            <template v-if="vehicle.ma_limit != null"> · MA {{ Math.round(vehicle.ma_limit) }} m</template>
          </p>
        </div>

        <ParkingPhaseBar
          v-if="isAutomatedParking(vehicle.mode) || vehicle.parking_phase !== 'cruising'"
          :phase="vehicle.parking_phase"
        />

        <StopDistanceBar
          :distance="vehicle.stop_distance"
          :station-name="vehicle.station_name"
        />
      </div>

      <ParkingPrecision :current-error="stopErrorCm" :records="parkingRecords" />
    </div>

    <div
      v-else
      class="flex items-center justify-center h-40 text-sm text-gray-600 border border-dashed border-gray-800 rounded-xl"
    >
      请在上方沙盘点击一列列车，进入受控车数字座舱视图
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  modeLabel,
  isManualMode,
  isAutomatedParking,
} from '@/adapters/simulation'
import SpeedGauge from '@/components/SpeedGauge.vue'
import VoltageGauge from '@/components/VoltageGauge.vue'
import StopDistanceBar from '@/components/StopDistanceBar.vue'
import ParkingPrecision from '@/components/ParkingPrecision.vue'
import ParkingPhaseBar from '@/components/ParkingPhaseBar.vue'

const props = defineProps({
  vehicle: { type: Object, default: null },
  power: { type: Object, default: null },
  color: { type: Function, required: true },
  stopErrorCm: { type: Number, default: null },
  parkingRecords: { type: Array, default: () => [] },
  lastControlCommand: { type: Object, default: null },
})

const modeHint = computed(() => {
  const m = props.vehicle?.mode
  if (m === 'manual') return '手动模式 · ↑ 牵引  ↓ 制动  Space 紧急制动'
  if (m === 'atp') return 'ATP 监督 · 关注 MA 与限速，必要时人工介入'
  if (m === 'ato') return 'ATO 自动 · 系统自动进站对标'
  return '点击沙盘切换受控车'
})

const modeBadgeClass = computed(() => {
  const m = props.vehicle?.mode
  if (m === 'ato') return 'border-sky-700 text-sky-400 bg-sky-950'
  if (m === 'atp') return 'border-amber-700 text-amber-400 bg-amber-950'
  if (m === 'manual') return 'border-orange-700 text-orange-300 bg-orange-950/50'
  return 'border-gray-600 text-gray-400 bg-gray-800'
})

const cockpitBorderClass = computed(() => {
  const m = props.vehicle?.mode
  if (m === 'ato') return 'border-sky-900/60'
  if (m === 'atp') return 'border-amber-900/50'
  if (m === 'manual') return 'border-orange-900/40'
  return 'border-gray-800'
})

const atpWarning = computed(() => {
  const v = props.vehicle
  if (!v || v.mode !== 'atp') return null
  const limit = v.target_speed ?? 80
  if (v.speed > limit + 2) return `超速 ${v.speed} km/h，目标限速 ${limit} km/h`
  if (v.ma_limit != null && v.ma_limit - v.position < 100) {
    return `接近 MA 边界，剩余 ${Math.round(v.ma_limit - v.position)} m`
  }
  return null
})

const controlFeedback = computed(() => {
  if (!props.lastControlCommand) return null
  if (Date.now() - props.lastControlCommand.at > 4000) return null
  return props.lastControlCommand
})
</script>
