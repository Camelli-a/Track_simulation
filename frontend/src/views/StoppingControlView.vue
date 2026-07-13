<template>
  <div class="space-y-5">
    <header class="app-panel">
      <div class="app-section-head">
        <div>
          <p class="app-section-kicker">Stopping Control</p>
          <h2 class="text-xl font-semibold text-slate-100">停车控制与单车诊断</h2>
          <p class="app-section-copy">
            这一页围绕单车停车安全展开，只回答谁在控车、还能不能安全停住、ATP 是否介入。
          </p>
        </div>
      </div>
    </header>

    <VehicleManagementPanel />
    <VehicleHeaderPanel />

    <section class="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <SceneKeyMetricsPanel />
      <SceneEventSummaryPanel />
    </section>

    <section class="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <StopFeasibilityPanel />
      <ControlSourcePanel />
    </section>

    <SpeedDistanceChart />

    <section class="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <AtoPanel />
      <AtpPanel />
    </section>

    <ParkingPrecision
      :current-error="store.currentStopErrorCm"
      :records="store.parkingRecords"
    />

    <StopResultPanel />
  </div>
</template>

<script setup>
import AtoPanel from '@/components/stopping/AtoPanel.vue'
import AtpPanel from '@/components/stopping/AtpPanel.vue'
import ControlSourcePanel from '@/components/stopping/ControlSourcePanel.vue'
import ParkingPrecision from '@/components/ParkingPrecision.vue'
import SceneEventSummaryPanel from '@/components/stopping/SceneEventSummaryPanel.vue'
import SceneKeyMetricsPanel from '@/components/stopping/SceneKeyMetricsPanel.vue'
import SpeedDistanceChart from '@/components/stopping/SpeedDistanceChart.vue'
import StopFeasibilityPanel from '@/components/stopping/StopFeasibilityPanel.vue'
import StopResultPanel from '@/components/stopping/StopResultPanel.vue'
import VehicleHeaderPanel from '@/components/stopping/VehicleHeaderPanel.vue'
import VehicleManagementPanel from '@/components/stopping/VehicleManagementPanel.vue'
import { useSimulationStore } from '@/stores/simulation'

const store = useSimulationStore()
</script>
