<template>
  <div
    class="flex h-screen bg-gray-950 text-gray-100"
    :class="{ 'presentation-mode': ui.presentationMode, 'mode-emergency': isEmergency }"
  >
    <!-- 侧边导航 -->
    <aside
      v-show="!ui.presentationMode"
      class="w-48 flex-shrink-0 bg-gray-900 flex flex-col py-6 px-3 gap-2"
    >
      <h1 class="text-sm font-bold text-gray-400 px-3 mb-4 tracking-widest uppercase">
        轨道仿真系统
      </h1>
      <NavItem to="/dashboard" label="🖥️ OCC 大屏" />
      <NavItem to="/power"   label="⚡ 供电仿真" />
      <NavItem to="/vehicle" label="🚆 车辆仿真" />
      <NavItem to="/track"   label="🛤️ 轨道仿真" />
      <NavItem to="/signal"  label="🚦 信号系统" />
      <div class="mt-auto px-2 pt-4 border-t border-gray-800">
        <PresentationToggle />
        <p class="text-[10px] text-gray-600 mt-2 leading-relaxed">
          ↑↓ 牵引/制动 · Space 紧急制动
        </p>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="flex-1 overflow-auto p-6 relative">
      <div
        v-if="ui.presentationMode"
        class="fixed top-3 right-3 z-50 flex gap-2"
      >
        <PresentationToggle />
      </div>
      <SystemAlertBar
        class="mb-4"
        :connected="sim.connected"
        :data-stale="sim.dataStale"
        :system-mode="sim.systemMode"
        :power-fault="sim.power?.is_fault ?? false"
        :last-error="sim.lastError"
        :alarms="sim.alarms"
      />
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { RouterView } from 'vue-router'
import NavItem from '@/components/NavItem.vue'
import PresentationToggle from '@/components/PresentationToggle.vue'
import SystemAlertBar from '@/components/SystemAlertBar.vue'
import { useLayoutSimulation } from '@/composables/usePageSimulation'
import { useKeyboardControl } from '@/composables/useKeyboardControl'
import { useUiStore } from '@/stores/ui'
import { useSimulationStore } from '@/stores/simulation'

const ui = useUiStore()
const sim = useLayoutSimulation()
useKeyboardControl(sim)

const isEmergency = computed(() => sim.systemMode === 'emergency')
</script>
