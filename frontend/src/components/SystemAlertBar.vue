<!-- 系统级告警条：后端 alarms + 连接/供电状态 -->
<template>
  <div v-if="allAlerts.length" class="space-y-2">
    <div
      v-for="(alert, i) in allAlerts"
      :key="alert.key ?? i"
      class="flex flex-wrap items-center gap-3 rounded-2xl border px-4 py-3 text-sm shadow-[0_12px_24px_rgba(2,6,23,0.22)] backdrop-blur"
      :class="alertClass(alert.level)"
    >
      <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-current/20 bg-black/10 text-base">
        {{ alert.icon }}
      </span>
      <span v-if="alert.source" class="shrink-0 rounded-full border border-current/15 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] opacity-70">
        {{ alert.source }}
      </span>
      <span class="flex-1 font-medium">{{ alert.message }}</span>
      <span v-if="alert.action" class="text-xs opacity-80">{{ alert.action }}</span>
      <span v-if="alert.detail" class="shrink-0 text-xs opacity-60">{{ alert.detail }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  connected: { type: Boolean, default: false },
  connecting: { type: Boolean, default: false },
  dataStale: { type: Boolean, default: false },
  systemMode: { type: String, default: 'normal' },
  powerFault: { type: Boolean, default: false },
  lastError: { type: String, default: null },
  alarms: { type: Array, default: () => [] },
  commState: { type: Object, default: null },
  routeResults: { type: Array, default: () => [] },
})

const LEVEL_ICON = {
  critical: '🚨',
  warning: '⚠️',
  info: 'ℹ️',
}

const allAlerts = computed(() => {
  const list = []

  for (const a of props.alarms.slice(0, 5)) {
    list.push({
      key: a.alarm_id,
      level: mapAlarmLevel(a.level),
      icon: LEVEL_ICON[a.level] ?? '⚠️',
      source: a.source_label ?? a.source,
      message: a.vehicle_id ? `[${a.vehicle_id}] ${a.message}` : a.message,
      action: a.level === 'critical' ? '请优先检查当前故障链路' : '建议结合对应页面继续定位',
    })
  }

  if (props.connecting) {
    list.push({
      key: 'ws-connecting',
      level: 'info',
      icon: '🛰️',
      message: '实时链路正在建立，系统将自动接入最新仿真数据',
      action: '若长时间停留，请检查后端服务与网络',
    })
  } else if (!props.connected) {
    list.push({
      key: 'ws-disconnect',
      level: 'error',
      icon: '🔴',
      message: 'WebSocket 已断开，数据停止刷新',
      action: '请检查后端进程与接口地址',
      detail: props.lastError,
    })
  } else if (props.dataStale) {
    list.push({
      key: 'ws-stale',
      level: 'warn',
      icon: '⚠️',
      message: '数据超过 2s 未更新，显示可能滞后',
      action: '可稍候观察下一帧数据是否恢复',
    })
  }

  const deniedRoutes = props.routeResults.filter((result) => !result.allowed)
  if (deniedRoutes.length) {
    const first = deniedRoutes[0]
    list.push({
      key: 'route-conflicts',
      level: 'warn',
      icon: '⛔',
      source: 'SIGNAL',
      message: `${deniedRoutes.length} 项进路申请未通过联锁校验`,
      action: first?.required_switch_id ? `优先核对道岔 ${first.required_switch_id}` : '请在全线态势页查看详情',
      detail: first?.reason ?? null,
    })
  }

  if (props.commState?.last_message_at) {
    const ageMs = Date.now() - toEpochMs(props.commState.last_message_at)
    if (ageMs > 5000) {
      list.push({
        key: 'comm-stale',
        level: 'warn',
        icon: '📡',
        source: 'COMM',
        message: '协议链路最近一条消息已超 5s 未刷新',
        action: '请检查上游仿真数据发布是否停滞',
        detail: `${Math.floor(ageMs / 1000)}s`,
      })
    }
  }

  if (props.systemMode === 'emergency') {
    list.push({ key: 'sys-emergency', level: 'error', icon: '🚨', message: '系统处于紧急模式', action: '请优先确认列车与供电安全状态' })
  } else if (props.systemMode === 'degraded') {
    list.push({ key: 'sys-degraded', level: 'warn', icon: '⚠️', message: '系统处于降级运行模式', action: '建议复核信号、MA 与速度约束' })
  }

  if (props.powerFault) {
    list.push({ key: 'power-fault', level: 'error', icon: '⚡', message: '接触网供电故障', action: '请切换到供电页确认故障影响范围' })
  }

  return list
})

function mapAlarmLevel(level) {
  if (level === 'critical') return 'error'
  if (level === 'warning') return 'warn'
  return 'info'
}

function alertClass(level) {
  if (level === 'error') return 'border-red-400/20 bg-red-500/10 text-red-100'
  if (level === 'warn') return 'border-amber-400/20 bg-amber-500/10 text-amber-100'
  return 'border-cyan-400/20 bg-cyan-500/10 text-cyan-100'
}

function toEpochMs(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return Date.now()
  return numeric > 1e12 ? numeric : numeric * 1000
}
</script>
