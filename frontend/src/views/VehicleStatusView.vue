<template>
  <div class="space-y-5">
    <!-- 页头 -->
    <header class="app-panel">
      <div class="app-section-head">
        <div>
          <p class="app-section-kicker">Vehicle Status</p>
          <h2 class="text-xl font-semibold text-slate-100">车辆状况</h2>
          <p class="app-section-copy">
            汇总列车实时运行状态，当前展示速度曲线；后续将扩展更多车辆诊断组件。
          </p>
        </div>
      </div>
    </header>

    <!-- 速度曲线 -->
    <SpeedCurvePanel />

    <!-- 后续可在此追加更多组件，例如：
    <BrakeStatusPanel />
    <TractionProfilePanel />
    -->
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount } from 'vue'
import SpeedCurvePanel from '@/components/vehicle/SpeedCurvePanel.vue'
import { useSpeedCurveStore } from '@/stores/speedCurve'

const speedCurveStore = useSpeedCurveStore()

onMounted(() => {
  speedCurveStore.startAll()
})

onBeforeUnmount(() => {
  speedCurveStore.stopAll()
})
</script>
