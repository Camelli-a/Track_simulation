<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Vehicle Management</p>
        <h3 class="app-section-title">车辆实例管理</h3>
        <p class="app-section-copy">
          这里复用后端车辆管理接口，可在停车控制页直接添加车辆、删除当前关注车辆，并刷新管理列表。
        </p>
      </div>
      <span class="app-chip">{{ managementModeText }}</span>
    </div>

    <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-5">
      <div class="app-metric-tile">
        <p class="app-metric-label">管理车辆</p>
        <p class="app-metric-value">{{ store.managedTrains.length }}</p>
        <p class="mt-2 text-xs text-slate-500">来自 /vehicle/trains。</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">仿真进程</p>
        <p class="app-metric-value">{{ processRunningCount }}</p>
        <p class="mt-2 text-xs text-slate-500">后端已拉起的车辆子进程。</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">实时上屏</p>
        <p class="app-metric-value">{{ store.vehicles.length }}</p>
        <p class="mt-2 text-xs text-slate-500">来自 dashboard_snapshot。</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">当前关注</p>
        <p class="mt-1 text-sm text-slate-200">{{ focusedVehicleIdText }}</p>
        <p class="mt-2 text-xs text-slate-500">删除按钮默认作用于这辆车。</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">下一辆建议</p>
        <p class="mt-1 text-sm text-slate-200">{{ nextVehicleId }}</p>
        <p class="mt-2 text-xs text-slate-500">添加时自动使用该编号。</p>
      </div>
    </div>

    <div class="mt-4 flex flex-wrap gap-2">
      <button
        type="button"
        class="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-200 transition hover:border-white/20 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="store.managedTrainsLoading"
        @click="refreshManagedTrains"
      >
        {{ store.managedTrainsLoading ? '刷新中...' : '刷新车辆列表' }}
      </button>

      <button
        type="button"
        class="rounded-xl border border-emerald-400/40 bg-emerald-400/10 px-3 py-2 text-xs text-emerald-100 transition hover:border-emerald-300/60 hover:bg-emerald-400/15 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="store.managedTrainsLoading || !canManageVehicles"
        @click="addNextTrain"
      >
        添加下一辆车
      </button>

      <button
        type="button"
        class="rounded-xl border border-red-400/40 bg-red-400/10 px-3 py-2 text-xs text-red-100 transition hover:border-red-300/60 hover:bg-red-400/15 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="store.managedTrainsLoading || !canManageVehicles || !focusedVehicleId"
        @click="requestRemoveFocusedTrain"
      >
        删除当前关注车辆
      </button>
    </div>

    <p v-if="store.managedTrainsError" class="mt-3 rounded-xl border border-red-900/50 bg-red-950/20 px-3 py-2 text-xs text-red-200">
      {{ store.managedTrainsError }}
    </p>
    <p v-else-if="store.lastManageAction" class="mt-3 text-xs text-slate-500">
      最近操作：{{ manageActionLabel(store.lastManageAction.type) }} ·
      {{ store.lastManageAction.ok ? '成功' : '失败' }}
      <span v-if="store.lastManageAction.reason"> · {{ store.lastManageAction.reason }}</span>
    </p>
  </section>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useSimulationStore } from '@/stores/simulation'
import { useUiStore } from '@/stores/ui'

const store = useSimulationStore()
const ui = useUiStore()

const canManageVehicles = computed(() => store.vehicleManagementMode === 'full')

const focusedVehicleId = computed(() => store.selectedVehicleId ?? store.selectedVehicle?.vehicle_id ?? null)

const focusedVehicleIdText = computed(() => focusedVehicleId.value ?? '未选择')

const processRunningCount = computed(() =>
  store.managedTrains.filter((train) => train.process_running).length
)

const managementModeText = computed(() => {
  if (store.vehicleManagementMode === 'full') return '可增删车辆'
  if (store.vehicleManagementMode === 'status_fallback') return '只读兼容'
  if (store.vehicleManagementMode === 'unavailable') return '接口不可用'
  return '检测中'
})

const nextTrainIndex = computed(() => {
  const used = new Set(
    [...store.managedTrains, ...store.vehicles]
      .map((train) => Number(train.train_index ?? parseTrainIndex(train.vehicle_id)))
      .filter(Number.isFinite),
  )
  let index = 1
  while (used.has(index)) index += 1
  return index
})

const nextVehicleId = computed(() => `TRAIN-${String(nextTrainIndex.value).padStart(3, '0')}`)

onMounted(() => {
  store.hydrateManagedTrains({ silent: true }).catch(() => {})
})

async function refreshManagedTrains() {
  await store.hydrateManagedTrains()
}

async function addNextTrain() {
  if (!canManageVehicles.value) {
    showMissingManageEndpoint()
    return
  }
  const payload = {
    type: 'add_train',
    vehicle_id: nextVehicleId.value,
    train_index: nextTrainIndex.value,
    line_id: 'LINE-1',
    position: 0,
  }
  const response = await store.submitVehicleManage(payload)
  if (response?.ok) {
    store.selectVehicle(payload.vehicle_id)
    await store.hydrateManagedTrains({ silent: true }).catch(() => {})
  }
}

function requestRemoveFocusedTrain() {
  if (!canManageVehicles.value) {
    showMissingManageEndpoint()
    return
  }
  const vehicleId = focusedVehicleId.value
  if (!vehicleId) return

  ui.requestConfirm({
    title: `确认删除 ${vehicleId}？`,
    message: '该操作会从后端车辆管理器中移除当前关注车辆，并同步发布 remove_train 管理消息。',
    confirmLabel: '确认删除',
    cancelLabel: '取消',
    destructive: true,
    onConfirm: async () => {
      const response = await store.submitVehicleManage({ type: 'remove_train', vehicle_id: vehicleId })
      if (response?.ok) {
        const nextId = store.vehicles.find((vehicle) => vehicle.vehicle_id !== vehicleId)?.vehicle_id
          ?? store.managedTrains.find((train) => train.vehicle_id !== vehicleId)?.vehicle_id
          ?? null
        store.selectVehicle(nextId)
        await store.hydrateManagedTrains({ silent: true }).catch(() => {})
      }
    },
  })
}

function showMissingManageEndpoint() {
  ui.showToast({
    type: 'warning',
    title: '车辆管理接口不可用',
    message: '当前后端没有进入完整车辆管理模式，暂时不能在前端增删车辆。',
    duration: 3600,
  })
}

function parseTrainIndex(vehicleId) {
  const match = String(vehicleId ?? '').match(/(\d+)$/)
  return match ? Number(match[1]) : null
}

function manageActionLabel(type) {
  return {
    add_train: '添加车辆',
    remove_train: '删除车辆',
    clear_trains: '清空车辆',
    reset_trains: '重置车辆',
  }[type] ?? type ?? '未知操作'
}
</script>
