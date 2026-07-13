<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Demo Control</p>
        <h3 class="app-section-title">演示控制头部</h3>
        <p class="app-section-copy">
          这里将放活动故障数、最近注入时间、当前全局场景和一键恢复入口。
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:bg-white/10"
          @click="focusLatestAnomalyVehicle"
        >
          聚焦异常车辆
        </button>
        <button
          type="button"
          class="rounded-xl border border-cyan-700/40 bg-cyan-950/30 px-3 py-2 text-xs text-cyan-200 transition hover:border-cyan-500"
          @click="publishTrackInfoAction"
        >
          重发线路数据
        </button>
        <button
          type="button"
          class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:bg-white/10"
          @click="clearOperatorActions"
        >
          清空本地记录
        </button>
      </div>
    </div>

    <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
      <article class="app-metric-tile">
        <p class="app-metric-label">活动异常数</p>
        <p class="app-metric-value">{{ activeFaultCount }}</p>
        <p class="mt-2 text-xs text-slate-500">按当前告警、供电故障、ATP 介入和进路未通过综合统计。</p>
      </article>
      <article class="app-metric-tile">
        <p class="app-metric-label">当前场景</p>
        <p class="mt-1 text-sm text-slate-200">{{ globalScene.label }}</p>
        <p class="mt-2 text-xs text-slate-500">{{ globalScene.scenario_id }}</p>
      </article>
      <article class="app-metric-tile">
        <p class="app-metric-label">当前主车</p>
        <p class="mt-1 text-sm text-slate-200">{{ simulation.selectedVehicle?.vehicle_id ?? '未选择' }}</p>
        <p class="mt-2 text-xs text-slate-500">
          {{ simulation.selectedVehicle ? `${Math.round(simulation.selectedVehicle.speed ?? 0)} km/h` : '请先在其他页面点选列车' }}
        </p>
      </article>
      <article class="app-metric-tile">
        <p class="app-metric-label">最近演示动作</p>
        <p class="mt-1 text-sm text-slate-200">{{ latestOperatorAction?.title ?? '尚未执行' }}</p>
        <p class="mt-2 text-xs text-slate-500">{{ latestOperatorAction ? formatTime(latestOperatorAction.at) : '等待操作' }}</p>
      </article>
    </div>
  </section>
</template>

<script setup>
import { useFaultWorkbench } from '@/composables/useFaultWorkbench'

const {
  simulation,
  globalScene,
  latestOperatorAction,
  activeFaultCount,
  focusLatestAnomalyVehicle,
  publishTrackInfoAction,
  clearOperatorActions,
} = useFaultWorkbench()

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
</script>
