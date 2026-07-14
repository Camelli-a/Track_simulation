<template>
  <div class="space-y-5">
    <LineOverviewPanel />

    <CurrentScenePanel />
    <SceneKeyMetricsPanel />

    <section class="grid grid-cols-1 gap-4 xl:grid-cols-[1.15fr_0.85fr]">
      <DriverDeskLinkPanel />
      <OperationAuthorityPanel />
    </section>
  </div>
</template>

<script setup>
import CurrentScenePanel from '@/components/overview/CurrentScenePanel.vue'
import DriverDeskLinkPanel from '@/components/overview/DriverDeskLinkPanel.vue'
import LineOverviewPanel from '@/components/overview/LineOverviewPanel.vue'
import OperationAuthorityPanel from '@/components/overview/OperationAuthorityPanel.vue'
import SceneKeyMetricsPanel from '@/components/overview/SceneKeyMetricsPanel.vue'
</script>
