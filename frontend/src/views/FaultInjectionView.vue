<template>
  <div class="space-y-5">
    <header class="app-panel">
      <div class="app-section-head">
        <div>
          <p class="app-section-kicker">Fault Injection</p>
          <h2 class="text-xl font-semibold text-slate-100">故障注入与演示控制</h2>
          <p class="app-section-copy">
            这一页聚焦异常触发、恢复和结果确认，不再承担场景手动切换的语义。
          </p>
        </div>
      </div>
    </header>

    <FaultControlHeader />
    <QuickInjectionPanel />

    <section class="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <ActiveEventsList />
      <ImpactSummaryPanel />
    </section>
  </div>
</template>

<script setup>
import ActiveEventsList from '@/components/fault/ActiveEventsList.vue'
import FaultControlHeader from '@/components/fault/FaultControlHeader.vue'
import ImpactSummaryPanel from '@/components/fault/ImpactSummaryPanel.vue'
import QuickInjectionPanel from '@/components/fault/QuickInjectionPanel.vue'
</script>
