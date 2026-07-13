<template>
  <div class="space-y-5">
    <LineOverviewPanel />

    <CurrentScenePanel />
    <SceneKeyMetricsPanel />
    <SceneEventSummaryPanel />

    <section class="grid grid-cols-1 gap-4 xl:grid-cols-[1.15fr_0.85fr]">
      <AffectedVehiclesPanel />
      <FocusedVehicleSummary />
    </section>
  </div>
</template>

<script setup>
import AffectedVehiclesPanel from '@/components/overview/AffectedVehiclesPanel.vue'
import CurrentScenePanel from '@/components/overview/CurrentScenePanel.vue'
import FocusedVehicleSummary from '@/components/overview/FocusedVehicleSummary.vue'
import LineOverviewPanel from '@/components/overview/LineOverviewPanel.vue'
import SceneEventSummaryPanel from '@/components/overview/SceneEventSummaryPanel.vue'
import SceneKeyMetricsPanel from '@/components/overview/SceneKeyMetricsPanel.vue'
</script>
