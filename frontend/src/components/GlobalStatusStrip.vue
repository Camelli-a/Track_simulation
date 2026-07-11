<template>
  <div class="rounded-2xl border border-white/10 bg-slate-950/90 px-4 py-3 shadow-[0_12px_30px_rgba(2,6,23,0.45)] backdrop-blur">
    <div class="flex flex-wrap items-center gap-2 text-xs">
      <ConnectionBadge
        :connected="connected"
        :connecting="connecting"
        :data-stale="dataStale"
      />
      <span class="app-chip">更新时间 {{ freshnessLabel }}</span>
      <span v-if="messageTimeLabel" class="app-chip">链路时间 {{ messageTimeLabel }}</span>
      <span class="app-chip">当前场景 {{ sceneLabel }}</span>
      <span class="app-chip">系统模式 {{ modeLabel }}</span>
      <span v-if="dataSource" class="app-chip">数据源 {{ dataSource }}</span>
      <span v-if="zmqConnected != null" class="app-chip">ZMQ {{ zmqConnected ? '已连接' : '未连接' }}</span>
      <span v-if="websocketClients != null" class="app-chip">WS 客户端 {{ websocketClients }}</span>
      <span v-if="latencyLabel" class="app-chip">链路延迟 {{ latencyLabel }}</span>
      <span v-if="protocolVersion" class="app-chip">协议 v{{ protocolVersion }}</span>
    </div>
  </div>
</template>

<script setup>
import ConnectionBadge from '@/components/ConnectionBadge.vue'

defineProps({
  connected: { type: Boolean, default: false },
  connecting: { type: Boolean, default: false },
  dataStale: { type: Boolean, default: false },
  freshnessLabel: { type: String, default: '等待首帧数据' },
  messageTimeLabel: { type: String, default: null },
  sceneLabel: { type: String, default: '全局总览' },
  modeLabel: { type: String, default: '正常运行' },
  dataSource: { type: String, default: null },
  zmqConnected: { type: Boolean, default: null },
  websocketClients: { type: Number, default: null },
  latencyLabel: { type: String, default: null },
  protocolVersion: { type: String, default: null },
})
</script>
