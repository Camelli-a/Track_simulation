<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Driver Desk Link</p>
        <h3 class="app-section-title">司机台链路与输入</h3>
        <p class="app-section-copy">
          直接展示后端 `communication` 与 `driver_inputs`，用于判断司机台前端/外部硬件发来的数据是否进入后端快照。
        </p>
      </div>
      <span class="rounded-full px-3 py-1 text-xs" :class="linkClass">
        {{ linkLabel }}
      </span>
    </div>

    <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
      <div class="app-metric-tile">
        <p class="app-metric-label">司机台连接</p>
        <p class="app-metric-value">{{ communication?.driver_console_connected ? '在线' : '离线' }}</p>
        <p class="mt-2 text-xs text-slate-500">source={{ communication?.source ?? '—' }}</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">ZMQ / UDP</p>
        <p class="app-metric-value">{{ communication?.zmq_connected ? 'ZMQ通' : 'ZMQ断' }}</p>
        <p class="mt-2 text-xs text-slate-500">UDP {{ communication?.udp_connected ? '在线' : '离线' }}</p>
      </div>
      <div class="app-metric-tile">
        <p class="app-metric-label">最后消息</p>
        <p class="app-metric-value">{{ lastMessageText }}</p>
        <p class="mt-2 text-xs text-slate-500">输入帧 {{ store.driverInputs.length }} 条</p>
      </div>
    </div>

    <div v-if="driverInput" class="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
      <StatusTile label="钥匙" :value="driverInput.key_switch ? '合' : '断'" />
      <StatusTile label="门关好灯" :value="driverInput.door_closed_light ? '亮' : '灭'" />
      <StatusTile label="ATO启动按钮" :value="driverInput.ato_start_btn ? '按下' : '未按'" />
      <StatusTile label="ATO激活" :value="driverInput.ato_active ? '激活' : '未激活'" />
      <StatusTile label="方向" :value="directionLabel(driverInput.direction)" />
      <StatusTile label="主控手柄" :value="handleLabel(driverInput.main_handle_raw)" />
      <StatusTile label="牵引级位" :value="levelText(driverInput.traction_level)" />
      <StatusTile label="制动级位" :value="levelText(driverInput.brake_level)" />
      <StatusTile label="紧急按钮" :value="driverInput.emergency_button ? '触发' : '未触发'" />
      <StatusTile label="紧急命令" :value="driverInput.emergency_cmd ? '触发' : '未触发'" />
      <StatusTile label="停放施加" :value="driverInput.parking_apply ? '施加' : '未施加'" />
      <StatusTile label="停放缓解" :value="driverInput.parking_release ? '缓解' : '未缓解'" />
    </div>

    <div
      v-else
      class="mt-4 rounded-[1.1rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500"
    >
      后端快照里还没有当前车辆的 driver_input。点击司机台按钮或推动手柄后，这里应立即出现对应字段。
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import StatusTile from '@/components/overview/StatusTile.vue'
import { useFocusedVehicle } from '@/composables/useFocusedVehicle'
import { usePageSimulation } from '@/composables/usePageSimulation'

const store = usePageSimulation()
const { focusedVehicle } = useFocusedVehicle()

const communication = computed(() => store.communication ?? null)
const driverInput = computed(() => {
  const vehicleId = focusedVehicle.value?.vehicle_id ?? store.selectedVehicleId
  return store.driverInputs.find((input) => input.vehicle_id === vehicleId) ?? store.driverInputs[0] ?? null
})

const linkLabel = computed(() =>
  communication.value?.driver_console_connected ? '后端已收到司机台状态' : '等待司机台状态'
)

const linkClass = computed(() =>
  communication.value?.driver_console_connected
    ? 'bg-emerald-400/10 text-emerald-200'
    : 'bg-amber-400/10 text-amber-200'
)

const lastMessageText = computed(() => {
  const timestamp = communication.value?.last_message_at ?? driverInput.value?.updated_at
  if (timestamp == null) return '—'
  const ms = Number(timestamp) > 1e12 ? Number(timestamp) : Number(timestamp) * 1000
  if (!Number.isFinite(ms)) return '—'
  return new Date(ms).toLocaleTimeString('zh-CN', { hour12: false })
})

function directionLabel(direction) {
  if (direction === 'forward') return '前进'
  if (direction === 'reverse') return '后退'
  if (direction === 'neutral') return '零位'
  return direction ?? '—'
}

function handleLabel(value) {
  if (value == null) return '—'
  const map = {
    0: '零位',
    1: '牵引',
    2: '常用制动',
    3: '快速制动',
    4: '紧急制动',
  }
  return map[Number(value)] ?? String(value)
}

function levelText(value) {
  return value == null ? '—' : String(value)
}
</script>
