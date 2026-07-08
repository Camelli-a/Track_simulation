<template>
  <div
    class="app-shell"
    :class="{ 'presentation-mode': ui.presentationMode, 'mode-emergency': isEmergency }"
  >
    <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.18),transparent_28%),radial-gradient(circle_at_80%_20%,rgba(56,189,248,0.12),transparent_22%),linear-gradient(180deg,rgba(15,23,42,0.85),rgba(2,6,23,0.96))]" />

    <div
      v-if="!ui.presentationMode && ui.navOpen"
      class="fixed inset-0 z-30 bg-slate-950/65 backdrop-blur-sm lg:hidden"
      @click="ui.closeNav()"
    />

    <aside
      v-show="!ui.presentationMode"
      class="app-sidebar"
      :class="ui.navOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'"
    >
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="text-[11px] font-semibold uppercase tracking-[0.32em] text-cyan-200/70">
            OCC Console
          </p>
          <h1 class="mt-2 text-xl font-semibold tracking-[0.08em] text-white">
            轨道仿真系统
          </h1>
          <p class="mt-2 max-w-[16rem] text-xs leading-5 text-slate-400">
            调度、供电、车辆、线路与信号的统一可视化监控台。
          </p>
        </div>
        <button
          type="button"
          class="rounded-xl border border-white/10 px-2.5 py-1 text-xs text-slate-400 lg:hidden"
          @click="ui.closeNav()"
        >
          关闭
        </button>
      </div>

      <div class="mt-6 grid grid-cols-2 gap-3">
        <div class="app-side-stat">
          <span class="app-side-stat-label">系统</span>
          <strong class="app-side-stat-value">{{ modeLabel }}</strong>
        </div>
        <div class="app-side-stat">
          <span class="app-side-stat-label">列车</span>
          <strong class="app-side-stat-value">{{ sim.vehicles.length }}</strong>
        </div>
      </div>

      <nav class="mt-6 space-y-3">
        <NavItem to="/dashboard" label="OCC 大屏" icon="◫" hint="全局态势与告警总览" />
        <NavItem to="/power" label="供电仿真" icon="⌁" hint="网压、电流与功率波动" />
        <NavItem to="/vehicle" label="车辆仿真" icon="▣" hint="列车状态、停车精度与控车" />
        <NavItem to="/track" label="轨道仿真" icon="≋" hint="线路区段、车站与剖面" />
        <NavItem to="/signal" label="信号系统" icon="◎" hint="闭塞、道岔与移动授权" />
      </nav>

      <div class="mt-auto space-y-3">
        <div class="app-side-panel">
          <p class="app-side-kicker">当前页面</p>
          <h2 class="mt-1 text-sm font-semibold text-white">{{ route.meta.section ?? route.meta.title }}</h2>
          <p class="mt-2 text-xs leading-5 text-slate-400">
            {{ route.meta.subtitle }}
          </p>
        </div>

        <div class="app-side-panel">
          <p class="app-side-kicker">操作提示</p>
          <p class="mt-2 text-xs leading-5 text-slate-300">
            {{ route.meta.opsHint }}
          </p>
          <p class="mt-3 text-[11px] leading-5 text-slate-500">
            {{ keyboardHint }}
          </p>
        </div>

        <div class="flex items-center gap-3">
          <PresentationToggle />
          <ConnectionBadge
            :connected="sim.connected"
            :connecting="sim.connecting"
            :data-stale="sim.dataStale"
          />
        </div>
      </div>
    </aside>

    <main class="relative z-10 min-w-0 flex-1 overflow-auto">
      <div v-if="ui.presentationMode" class="fixed right-4 top-4 z-50 flex gap-2">
        <PresentationToggle />
      </div>

      <div class="flex min-h-screen w-full flex-col px-4 py-4 sm:px-6 lg:px-8 lg:py-6">
        <header v-if="!ui.presentationMode" class="mb-5">
          <div class="app-topbar">
            <div class="flex items-start gap-3">
              <button
                type="button"
                class="mt-1 rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-300 lg:hidden"
                @click="ui.toggleNav()"
              >
                菜单
              </button>
              <div>
                <p class="text-[11px] font-semibold uppercase tracking-[0.28em] text-cyan-200/70">
                  {{ route.meta.section ?? 'System View' }}
                </p>
                <h2 class="mt-2 text-2xl font-semibold tracking-[0.04em] text-white">
                  {{ route.meta.title ?? '轨道仿真系统' }}
                </h2>
                <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                  {{ route.meta.subtitle }}
                </p>
              </div>
            </div>

            <div class="flex flex-wrap items-center justify-end gap-2">
              <ConnectionBadge
                :connected="sim.connected"
                :connecting="sim.connecting"
                :data-stale="sim.dataStale"
              />
              <span class="app-chip">{{ modeLabel }}</span>
              <span v-if="sim.dataSource" class="app-chip">{{ sim.dataSource }}</span>
              <span class="app-chip">{{ freshnessLabel }}</span>
              <span class="app-chip">{{ clockLabel }}</span>
            </div>
          </div>
        </header>

        <div class="sticky top-3 z-40 mb-4">
          <GlobalStatusStrip
            :connected="sim.connected"
            :connecting="sim.connecting"
            :data-stale="sim.dataStale"
            :freshness-label="freshnessLabel"
            :scene-label="ui.sceneLabel"
            :mode-label="modeLabel"
            :data-source="sim.dataSource"
          />
        </div>

        <SystemAlertBar
          class="mb-4"
          :connected="sim.connected"
          :connecting="sim.connecting"
          :data-stale="sim.dataStale"
          :system-mode="sim.systemMode"
          :power-fault="sim.power?.is_fault ?? false"
          :last-error="sim.lastError"
          :alarms="sim.alarms"
        />

        <div class="flex-1">
          <RouterView />
        </div>
      </div>
    </main>

    <AppToastStack :toasts="ui.toasts" @dismiss="ui.dismissToast" />
    <ConfirmActionDialog
      :dialog="ui.confirmDialog"
      @confirm="ui.confirmPending"
      @cancel="ui.cancelConfirm"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppToastStack from '@/components/AppToastStack.vue'
import { RouterView, useRoute } from 'vue-router'
import ConnectionBadge from '@/components/ConnectionBadge.vue'
import ConfirmActionDialog from '@/components/ConfirmActionDialog.vue'
import GlobalStatusStrip from '@/components/GlobalStatusStrip.vue'
import NavItem from '@/components/NavItem.vue'
import PresentationToggle from '@/components/PresentationToggle.vue'
import SystemAlertBar from '@/components/SystemAlertBar.vue'
import { useLayoutSimulation } from '@/composables/usePageSimulation'
import { useKeyboardControl } from '@/composables/useKeyboardControl'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const sim = useLayoutSimulation()
const route = useRoute()
useKeyboardControl(sim)

const isEmergency = computed(() => sim.systemMode === 'emergency')
const currentTime = ref(Date.now())
const clockLabel = computed(() => formatClock(currentTime.value))

const modeLabel = computed(() => {
  if (sim.systemMode === 'emergency') return '紧急模式'
  if (sim.systemMode === 'degraded') return '降级运行'
  if (sim.systemMode === 'offline') return '离线待机'
  return '正常运行'
})

const freshnessLabel = computed(() => {
  if (sim.connecting) return '正在接入数据'
  if (!sim.connected || !sim.lastTickAt) return '等待首帧数据'
  const diff = Math.max(0, currentTime.value - sim.lastTickAt)
  if (diff < 1000) return '刚刚更新'
  return `${Math.floor(diff / 1000)} 秒前更新`
})

const keyboardHint = computed(() => {
  if (route.path === '/vehicle') {
    return '手动模式车辆可使用 ↑ 牵引、↓ 制动、Space 紧急制动。'
  }
  return '当前页以监视为主；若需控车，请切换到“车辆仿真”页面。'
})

let clockTimer = null

onMounted(() => {
  clockTimer = window.setInterval(() => {
    currentTime.value = Date.now()
  }, 1000)
})

onBeforeUnmount(() => {
  if (clockTimer) window.clearInterval(clockTimer)
})

watch(
  () => route.path,
  () => {
    ui.closeNav()
    ui.setSceneLabel(route.meta.title ?? '全局总览')
  },
  { immediate: true },
)

function formatClock(ts) {
  return new Date(ts).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
</script>
