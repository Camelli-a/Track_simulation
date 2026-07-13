<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">ATP</p>
        <h3 class="app-section-title">ATP 面板</h3>
        <p class="app-section-copy">
          这里将展示紧急制动、限速、MA、预警距离、制动曲线限速和 ATP 告警。
        </p>
      </div>
      <span class="app-chip">{{ atpStateLabel }}</span>
    </div>

    <template v-if="vehicle">
      <div class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[1fr_0.9fr]">
        <article class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-4">
          <div class="grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">运行许可</p>
              <p class="mt-1 text-sm" :class="permissionClass">{{ permissionText }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">防护信号</p>
              <p class="mt-1 text-sm text-slate-200">{{ signalStateText }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">距离 MA</p>
              <p class="mt-1 text-sm text-slate-200">{{ distanceToMa != null ? `${distanceToMa.toFixed(1)} m` : '—' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">MA 边界</p>
              <p class="mt-1 text-sm text-slate-200">{{ maLimit != null ? `${Math.round(maLimit)} m` : '—' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">常用制动距离</p>
              <p class="mt-1 text-sm text-slate-200">{{ requiredStopDistance != null ? `${requiredStopDistance.toFixed(1)} m` : '—' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">紧急制动距离</p>
              <p class="mt-1 text-sm text-slate-200">{{ emergencyStopDistance != null ? `${emergencyStopDistance.toFixed(1)} m` : '—' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">ATP 预警距离</p>
              <p class="mt-1 text-sm text-slate-200">{{ warningDistance != null ? `${warningDistance.toFixed(1)} m` : '—' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">曲线限速</p>
              <p class="mt-1 text-sm text-slate-200">{{ brakingCurveLimit != null ? `${Math.round(brakingCurveLimit)} km/h` : '—' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">前车 / 安全间距</p>
              <p class="mt-1 text-sm text-slate-200">
                {{ vehicle.ma_front_vehicle_id ?? '无前车' }}
                <span v-if="vehicle.ma_safe_distance != null" class="text-slate-500"> · {{ vehicle.ma_safe_distance }} m</span>
              </p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">约束原因</p>
              <p class="mt-1 text-sm text-slate-200">{{ reasonText }}</p>
            </div>
          </div>
        </article>

        <article class="rounded-[1.05rem] border border-red-900/30 bg-red-950/10 px-4 py-4">
          <p class="text-[11px] uppercase tracking-[0.22em] text-red-200/70">ATP Diagnosis</p>
          <h4 class="mt-2 text-lg font-semibold text-slate-100">{{ atpStateTitle }}</h4>
          <p class="mt-3 text-sm leading-6 text-slate-200">{{ atpSummary }}</p>

          <div class="mt-4 space-y-2">
            <div
              v-for="alarm in visibleAlarms"
              :key="alarm.alarm_id"
              class="rounded-xl border border-red-900/40 bg-black/20 px-3 py-3"
            >
              <p class="text-sm text-slate-100">{{ alarm.message || alarm.alarm_id }}</p>
              <p class="mt-1 text-[11px] text-slate-500">{{ alarm.source_label ?? alarm.source }} · {{ formatAlarmTime(alarm.timestamp) }}</p>
            </div>
          </div>

          <div
            v-if="!visibleAlarms.length"
            class="mt-4 rounded-[1rem] border border-dashed border-white/10 bg-black/10 px-4 py-6 text-sm text-slate-500"
          >
            当前没有这辆车的 ATP/ATO 相关告警回显。
          </div>
        </article>
      </div>
    </template>

    <div
      v-else
      class="mt-4 rounded-[1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-sm text-slate-500"
    >
      当前没有关注车辆，ATP 面板暂时无法展开。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useStoppingAnalysis } from '@/composables/useStoppingAnalysis'

const {
  vehicle,
  maLimit,
  distanceToMa,
  requiredStopDistance,
  emergencyStopDistance,
  warningDistance,
  brakingCurveLimit,
  relatedAlarms,
  serviceMargin,
  emergencyMargin,
} = useStoppingAnalysis()

const permissionText = computed(() => {
  const permission = vehicle.value?.ma_permission ?? vehicle.value?.permission
  if (permission === 'allow') return '允许通过'
  if (permission === 'restricted') return '受限通过'
  if (permission === 'stop') return '停车'
  return permission ?? '—'
})

const permissionClass = computed(() => {
  const permission = vehicle.value?.ma_permission ?? vehicle.value?.permission
  if (permission === 'stop') return 'text-red-300'
  if (permission === 'restricted') return 'text-amber-300'
  if (permission === 'allow') return 'text-emerald-300'
  return 'text-slate-200'
})

const signalStateText = computed(() => {
  const state = vehicle.value?.ma_signal_state ?? vehicle.value?.signal_state
  if (state === 'red') return '红灯'
  if (state === 'yellow') return '黄灯'
  if (state === 'green') return '绿灯'
  return state ?? '—'
})

const reasonText = computed(() => {
  const reason = vehicle.value?.ma_reason
  if (!reason) return '—'
  return {
    front_vehicle_protection: '前车防护',
    route_end: '进路终点',
    route_locked: '进路已锁闭',
    route_available: '进路可用',
  }[reason] ?? reason
})

const atpStateLabel = computed(() => vehicle.value?.emergency_brake ? 'ATP 已介入' : 'ATP 监督中')

const atpStateTitle = computed(() => {
  if (vehicle.value?.emergency_brake) return 'ATP 已经抢权执行紧急制动'
  if (emergencyMargin.value != null && emergencyMargin.value < 0) return '已逼近 ATP 兜底边界'
  if (serviceMargin.value != null && serviceMargin.value < 0) return '常用制动裕量不足'
  return '当前仍处于 ATP 监督窗口'
})

const atpSummary = computed(() => {
  if (!vehicle.value) return '—'
  if (vehicle.value.emergency_brake) {
    return '当前应重点核对 ATP 触发原因、前方约束、停车结果，以及司机台和后端是否对同一次抢权给出了统一回显。'
  }
  if (emergencyMargin.value != null && emergencyMargin.value < 0) {
    return '按现有可见数据推断，若再不降速，紧急制动停车距离将不足，系统已经接近 ATP 的最后兜底边界。'
  }
  if (serviceMargin.value != null && serviceMargin.value < 0) {
    return '常用制动停车距离已经超过当前 MA 裕量，说明 ATO 或司机制动响应偏晚，需要继续看是否会触发 ATP。'
  }
  return '当前 ATP 主要在持续监督速度、MA 边界和前方约束，尚未看到明确的抢权信号。'
})

const visibleAlarms = computed(() => relatedAlarms.value.slice(0, 3))

function formatAlarmTime(timestamp) {
  if (!timestamp) return '刚刚'
  return new Date(Number(timestamp) * 1000).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
</script>
