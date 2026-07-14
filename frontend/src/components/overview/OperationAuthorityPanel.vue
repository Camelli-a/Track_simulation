<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">ATO / ATP / MA</p>
        <h3 class="app-section-title">自动驾驶与安全许可</h3>
        <p class="app-section-copy">
          集中展示当前关注车辆的 train_state、ATO 输出、ATP 介入和 MA 许可，方便验证“按 ATO 后车能不能跑、为什么不能跑”。
        </p>
      </div>
      <span class="rounded-full px-3 py-1 text-xs" :class="statusClass">
        {{ statusLabel }}
      </span>
    </div>

    <div v-if="vehicle" class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
      <div class="app-metric-tile">
        <p class="app-metric-label">当前速度</p>
        <p class="app-metric-value">{{ kmh(vehicle.speed_kmh ?? vehicle.speed) }}</p>
        <p class="mt-2 text-xs text-slate-500">位置 {{ meters(vehicle.position) }}</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">控制来源</p>
        <p class="app-metric-value">{{ vehicle.control_source ?? vehicle.mode ?? '—' }}</p>
        <p class="mt-2 text-xs text-slate-500">驾驶模式 {{ vehicle.driving_mode ?? '—' }}</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">后端输出级位</p>
        <p class="app-metric-value">
          T{{ nullable(vehicle.commanded_traction_level) }} / B{{ nullable(vehicle.commanded_brake_level) }}
        </p>
        <p class="mt-2 text-xs text-slate-500">来自 train_state.commanded_*</p>
      </div>
    </div>

    <div v-if="vehicle" class="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
      <StatusTile label="ATO可用" :value="vehicle.ato_capable ? '可用' : '不可用'" />
      <StatusTile label="ATO激活" :value="vehicle.ato_active ? '激活' : '未激活'" />
      <StatusTile label="ATO状态" :value="vehicle.ato_state ?? '—'" />
      <StatusTile label="ATO目标速度" :value="kmh(vehicle.ato_target_speed_kmh)" />
      <StatusTile label="推荐速度" :value="kmh(vehicle.recommended_speed_kmh)" />
      <StatusTile label="ATP介入" :value="vehicle.atp_intervention || vehicle.atp_intervened ? '已介入' : '未介入'" />
      <StatusTile label="MA许可" :value="permissionLabel(vehicle.permission)" />
      <StatusTile label="信号状态" :value="signalLabel(vehicle.signal_state)" />
      <StatusTile label="MA边界" :value="meters(vehicle.ma_limit)" />
      <StatusTile label="距离MA" :value="meters(vehicle.distance_to_ma)" />
      <StatusTile label="限速" :value="kmh(vehicle.speed_limit)" />
      <StatusTile label="目标速度" :value="kmh(vehicle.target_speed)" />
    </div>

    <div
      v-else
      class="mt-4 rounded-[1.1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500"
    >
      当前没有车辆快照。后端收到 train_state 后，这里会显示速度、位置、ATO/ATP 和 MA 状态。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import StatusTile from '@/components/overview/StatusTile.vue'
import { useFocusedVehicle } from '@/composables/useFocusedVehicle'

const { focusedVehicle: vehicle } = useFocusedVehicle()

const statusLabel = computed(() => {
  const current = vehicle.value
  if (!current) return '等待车辆状态'
  if (current.emergency_brake || current.atp_intervention || current.atp_intervened) return 'ATP / 紧急制动'
  if (current.permission === 'stop') return 'MA停车'
  if (current.ato_active && current.ato_state) return `ATO ${current.ato_state}`
  if (current.ato_active) return 'ATO已激活'
  return '监督中'
})

const statusClass = computed(() => {
  const current = vehicle.value
  if (!current) return 'bg-slate-400/10 text-slate-300'
  if (current.emergency_brake || current.atp_intervention || current.atp_intervened) return 'bg-red-400/10 text-red-200'
  if (current.permission === 'stop') return 'bg-amber-400/10 text-amber-200'
  if (current.ato_active) return 'bg-cyan-400/10 text-cyan-200'
  return 'bg-emerald-400/10 text-emerald-200'
})

function kmh(value) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return `${Number(value).toFixed(1)} km/h`
}

function meters(value) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return `${Number(value).toFixed(1)} m`
}

function nullable(value) {
  return value == null ? '—' : value
}

function permissionLabel(permission) {
  if (permission === 'allow') return '允许'
  if (permission === 'restricted') return '受限'
  if (permission === 'stop') return '停车'
  return permission ?? '—'
}

function signalLabel(signal) {
  if (signal === 'green') return '绿灯'
  if (signal === 'yellow') return '黄灯'
  if (signal === 'red') return '红灯'
  return signal ?? '—'
}
</script>
