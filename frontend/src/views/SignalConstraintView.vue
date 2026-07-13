<template>
  <div class="space-y-5">
    <header class="app-panel">
      <div class="app-section-head">
        <div>
          <p class="app-section-kicker">Signal Constraint</p>
          <h2 class="text-xl font-semibold text-slate-100">信号与联锁</h2>
          <p class="app-section-copy">
            这一页只解释当前关注车辆为什么会收到当前 MA、信号限制和联锁约束。
          </p>
        </div>
      </div>
    </header>

    <SignalConstraintSummary />
    <ForwardConstraintChain />

    <section class="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <InterlockingConflictList />
      <MaReasonPanel />
    </section>
  </div>
</template>

<script setup>
import ForwardConstraintChain from '@/components/signal/ForwardConstraintChain.vue'
import InterlockingConflictList from '@/components/signal/InterlockingConflictList.vue'
import MaReasonPanel from '@/components/signal/MaReasonPanel.vue'
import SignalConstraintSummary from '@/components/signal/SignalConstraintSummary.vue'
</script>
