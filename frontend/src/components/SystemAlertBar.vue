<!-- 系统级告警条：后端 alarms + 连接/供电状态 -->
<template>
  <div v-if="allAlerts.length" class="space-y-2">
    <div
      v-for="(alert, i) in allAlerts"
      :key="alert.key ?? i"
      class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm border"
      :class="alertClass(alert.level)"
    >
      <span class="text-base shrink-0">{{ alert.icon }}</span>
      <span v-if="alert.source" class="text-[10px] uppercase tracking-wide opacity-60 shrink-0">
        {{ alert.source }}
      </span>
      <span class="flex-1">{{ alert.message }}</span>
      <span v-if="alert.detail" class="text-xs opacity-70 shrink-0">{{ alert.detail }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  connected: { type: Boolean, default: false },
  dataStale: { type: Boolean, default: false },
  systemMode: { type: String, default: 'normal' },
  powerFault: { type: Boolean, default: false },
  lastError: { type: String, default: null },
  alarms: { type: Array, default: () => [] },
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
      source: a.source,
      message: a.vehicle_id ? `[${a.vehicle_id}] ${a.message}` : a.message,
    })
  }

  if (!props.connected) {
    list.push({
      key: 'ws-disconnect',
      level: 'error',
      icon: '🔴',
      message: 'WebSocket 已断开，数据停止刷新',
      detail: props.lastError,
    })
  } else if (props.dataStale) {
    list.push({
      key: 'ws-stale',
      level: 'warn',
      icon: '⚠️',
      message: '数据超过 2s 未更新，显示可能滞后',
    })
  }

  if (props.systemMode === 'emergency') {
    list.push({ key: 'sys-emergency', level: 'error', icon: '🚨', message: '系统处于紧急模式' })
  } else if (props.systemMode === 'degraded') {
    list.push({ key: 'sys-degraded', level: 'warn', icon: '⚠️', message: '系统处于降级运行模式' })
  }

  if (props.powerFault) {
    list.push({ key: 'power-fault', level: 'error', icon: '⚡', message: '接触网供电故障' })
  }

  return list
})

function mapAlarmLevel(level) {
  if (level === 'critical') return 'error'
  if (level === 'warning') return 'warn'
  return 'info'
}

function alertClass(level) {
  if (level === 'error') return 'border-red-800 bg-red-950/80 text-red-300'
  if (level === 'warn') return 'border-amber-800 bg-amber-950/60 text-amber-300'
  return 'border-sky-800 bg-sky-950/50 text-sky-300'
}
</script>
