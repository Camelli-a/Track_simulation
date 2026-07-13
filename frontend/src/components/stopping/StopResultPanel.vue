<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Result</p>
        <h3 class="app-section-title">停车结果与异常诊断</h3>
        <p class="app-section-copy">
          这里将汇总停车阶段、停车误差、授权状态、前车影响和一句话诊断结论。
        </p>
      </div>
    </div>

    <template v-if="vehicle">
      <div class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <article class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-4">
          <div class="grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">停车阶段</p>
              <p class="mt-1 text-sm text-slate-200">{{ parkingPhaseText }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">停车误差</p>
              <p class="mt-1 text-sm text-slate-200">{{ stopErrorCm != null ? `${stopErrorCm} cm` : '—' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">运行许可</p>
              <p class="mt-1 text-sm text-slate-200">{{ permissionText }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">信号状态</p>
              <p class="mt-1 text-sm text-slate-200">{{ signalStateText }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">前车影响</p>
              <p class="mt-1 text-sm text-slate-200">{{ vehicle.ma_front_vehicle_id ?? '无前车' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">数据新鲜度</p>
              <p class="mt-1 text-sm text-slate-200">{{ heartbeatText }}</p>
            </div>
          </div>

          <div class="mt-4 rounded-[1rem] border border-cyan-500/20 bg-cyan-500/10 px-4 py-4">
            <p class="text-[11px] uppercase tracking-[0.22em] text-cyan-200/70">Quick Diagnosis</p>
            <h4 class="mt-2 text-lg font-semibold text-slate-100">{{ diagnosisTitle }}</h4>
            <p class="mt-3 text-sm leading-6 text-slate-200">{{ diagnosisSummary }}</p>
          </div>
        </article>

        <article class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <p class="text-sm font-semibold text-slate-100">最近控制指令历史</p>
              <p class="mt-1 text-xs text-slate-500">保留这辆车最近 6 条控制动作，用来回看是谁在控车、是否执行成功。</p>
            </div>
            <span class="app-chip">{{ recentControls.length }} 条</span>
          </div>

          <div
            v-if="!recentControls.length"
            class="mt-4 rounded-[1rem] border border-dashed border-white/10 bg-black/10 px-4 py-6 text-sm text-slate-500"
          >
            当前列车还没有控制指令记录。
          </div>

          <div v-else class="mt-4 space-y-2">
            <div
              v-for="entry in recentControls"
              :key="entry.id"
              class="rounded-xl border px-4 py-3"
              :class="entry.status === 'error'
                ? 'border-red-900/60 bg-red-950/20'
                : entry.status === 'ok'
                  ? 'border-emerald-900/60 bg-emerald-950/20'
                  : 'border-sky-900/60 bg-sky-950/20'"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="text-sm font-medium text-slate-100">{{ entry.label }}</span>
                <span class="text-[11px]" :class="statusClass(entry.status)">
                  {{ statusText(entry.status) }}
                </span>
              </div>
              <p class="mt-1 text-xs text-slate-400">{{ controlSummary(entry) }}</p>
              <p v-if="entry.error" class="mt-2 text-xs text-red-300">{{ entry.error }}</p>
            </div>
          </div>
        </article>
      </div>
    </template>

    <div
      v-else
      class="mt-4 rounded-[1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-sm text-slate-500"
    >
      当前没有关注车辆，停车结果面板暂时无法展开。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useStoppingAnalysis } from '@/composables/useStoppingAnalysis'

const {
  vehicle,
  stopErrorCm,
  parkingPhaseText,
  heartbeatText,
  recentControls,
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

const signalStateText = computed(() => {
  const state = vehicle.value?.ma_signal_state ?? vehicle.value?.signal_state
  if (state === 'red') return '红灯'
  if (state === 'yellow') return '黄灯'
  if (state === 'green') return '绿灯'
  return state ?? '—'
})

const diagnosisTitle = computed(() => {
  if (!vehicle.value) return '等待车辆'
  if (vehicle.value.emergency_brake) return '当前已进入 ATP 紧急停车'
  if (vehicle.value.parking_phase === 'stopped') return '当前已完成停稳'
  if (serviceMargin.value != null && serviceMargin.value < 0) return '当前停车控制已经偏紧'
  return '当前仍处于可控停车流程'
})

const diagnosisSummary = computed(() => {
  if (!vehicle.value) return '—'
  if (vehicle.value.emergency_brake) {
    return '这一轮停车已经进入 ATP 兜底结果阶段，建议结合上方 ATP 面板和场景事件摘要回看触发原因。'
  }
  if (vehicle.value.parking_phase === 'stopped') {
    return `车辆已经停稳${stopErrorCm.value != null ? `，当前停车误差约 ${stopErrorCm.value} cm。` : '。'}`
  }
  if (serviceMargin.value != null && serviceMargin.value < 0) {
    return '按当前速度和 MA 裕量推断，常用制动空间已经偏小，下一步要重点看是否继续降速或转入 ATP 保护。'
  }
  if (emergencyMargin.value != null && emergencyMargin.value < 0) {
    return '当前连紧急制动裕量都已经不足，这种状态应被视为高风险演示状态。'
  }
  return '当前速度、停车阶段和控制回显基本处于同一条主链路里，可以继续把这辆车当作当前展示主车。'
})

function statusText(status) {
  if (status === 'ok') return '已执行'
  if (status === 'error') return '失败'
  return '发送中'
}

function statusClass(status) {
  if (status === 'ok') return 'text-emerald-300'
  if (status === 'error') return 'text-red-300'
  return 'text-sky-300'
}

function controlSummary(entry) {
  const parts = [entry.vehicleId]
  if (entry.command === 'ato') {
    parts.push(entry.target_speed != null ? `目标 ${entry.target_speed} km/h` : null)
    parts.push(entry.target_position != null ? `位置 ${Math.round(entry.target_position)} m` : null)
    parts.push(`T${entry.traction_level ?? 0}`)
    parts.push(`B${entry.brake_level ?? 0}`)
  } else {
    parts.push(`level ${entry.level ?? 1}`)
    parts.push(directionText(entry.direction))
  }
  parts.push(formatTime(entry.at))
  return parts.filter(Boolean).join(' · ')
}

function directionText(direction) {
  if (direction === 'forward') return '前进'
  if (direction === 'backward' || direction === 'reverse') return '后退'
  if (direction === 'neutral') return '空挡'
  return direction ?? '—'
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
</script>
