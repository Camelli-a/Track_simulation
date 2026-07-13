<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Impact Summary</p>
        <h3 class="app-section-title">影响结果摘要</h3>
        <p class="app-section-copy">
          这里将确认受影响车辆、MA 更新、信号变化、ATP 介入和关键事件时间线。
        </p>
      </div>
    </div>

    <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
      <article class="app-metric-tile">
        <p class="app-metric-label">受影响车辆</p>
        <p class="app-metric-value">{{ abnormalVehicles.length }}</p>
        <p class="mt-2 text-xs text-slate-500">按 ATP 介入、停车等待、MA 受限和停车阶段综合识别。</p>
      </article>
      <article class="app-metric-tile">
        <p class="app-metric-label">MA 收缩事件</p>
        <p class="app-metric-value">{{ maShrinkEventCount }}</p>
        <p class="mt-2 text-xs text-slate-500">来自最近时间线中的 MA 收缩记录。</p>
      </article>
      <article class="app-metric-tile">
        <p class="app-metric-label">红灯数量</p>
        <p class="app-metric-value">{{ redSignalCount }}</p>
        <p class="mt-2 text-xs text-slate-500">用于辅助判断是否进入红灯停车场景。</p>
      </article>
      <article class="app-metric-tile">
        <p class="app-metric-label">受限车辆数</p>
        <p class="app-metric-value">{{ restrictedVehicleCount }}</p>
        <p class="mt-2 text-xs text-slate-500">统计当前 `stop / restricted` 许可的车辆。</p>
      </article>
    </div>

    <div class="mt-4 rounded-[1rem] border border-cyan-500/20 bg-cyan-500/10 px-4 py-4">
      <p class="text-[11px] uppercase tracking-[0.22em] text-cyan-200/70">Current Reading</p>
      <h4 class="mt-2 text-lg font-semibold text-slate-100">{{ globalScene.label }}</h4>
      <p class="mt-3 text-sm leading-6 text-slate-200">{{ globalScene.summary }}</p>
    </div>

    <div class="mt-4">
      <EventTimeline
        :events="recentFaultEvents"
        :selected-vehicle-id="simulation.selectedVehicleId"
        :color="simulation.vehicleColor"
        @select="simulation.selectVehicle"
      />
    </div>
  </section>
</template>

<script setup>
import EventTimeline from '@/components/EventTimeline.vue'
import { useFaultWorkbench } from '@/composables/useFaultWorkbench'

const {
  simulation,
  globalScene,
  recentFaultEvents,
  abnormalVehicles,
  maShrinkEventCount,
  redSignalCount,
  restrictedVehicleCount,
} = useFaultWorkbench()
</script>
