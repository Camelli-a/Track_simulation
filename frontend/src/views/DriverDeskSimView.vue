<template>
  <div class="space-y-5">
    <header class="app-panel">
      <div class="app-section-head">
        <div>
          <p class="app-section-kicker">Driver Desk Test Rig</p>
          <h2 class="text-xl font-semibold text-slate-100">司机台协议联调</h2>
          <p class="app-section-copy">
            这个页面不是走旁路 REST 控车，而是驱动一个本地 TCP 协议模拟器，让后端按真实司机台帧格式收发数据。
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            type="button"
            class="rounded-xl border border-emerald-700/50 bg-emerald-950/40 px-4 py-2 text-sm text-emerald-200 transition hover:border-emerald-500"
            @click="startRig"
          >
            启动本地联调
          </button>
          <button
            type="button"
            class="rounded-xl border border-red-700/50 bg-red-950/30 px-4 py-2 text-sm text-red-200 transition hover:border-red-500"
            @click="stopRig"
          >
            停止
          </button>
        </div>
      </div>

      <div class="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-4">
        <div class="app-metric-tile">
          <p class="app-metric-label">协议模拟器</p>
          <p class="mt-1 text-sm text-slate-200">{{ simulator.running ? '已启动' : '未启动' }}</p>
          <p class="mt-2 text-xs text-slate-500">{{ simulator.host ?? '127.0.0.1' }}:{{ simulator.port ?? 18001 }}</p>
        </div>
        <div class="app-metric-tile">
          <p class="app-metric-label">后端桥接</p>
          <p class="mt-1 text-sm text-slate-200">{{ bridge.running ? '已启动' : '未启动' }}</p>
          <p class="mt-2 text-xs text-slate-500">{{ bridge.source_status?.connected ? '已连上协议模拟器' : '尚未连上协议模拟器' }}</p>
        </div>
        <div class="app-metric-tile">
          <p class="app-metric-label">当前测试车辆</p>
          <p class="mt-1 text-sm text-slate-200">{{ bridge.vehicle_id ?? simulator.vehicle_id ?? 'TRAIN-001' }}</p>
          <p class="mt-2 text-xs text-slate-500">建议与车辆仿真进程 `--vehicle-id` 保持一致</p>
        </div>
        <div class="app-metric-tile">
          <p class="app-metric-label">现有前端联动</p>
          <p class="mt-1 text-sm text-slate-200">{{ liveVehicle ? '已检测到列车快照' : '未检测到列车快照' }}</p>
          <p class="mt-2 text-xs text-slate-500">若这里为空，请先确认 Broker、`DATA_SOURCE=zmq` 和车辆进程都已启动</p>
        </div>
      </div>
    </header>

    <section class="grid grid-cols-1 gap-4 xl:grid-cols-[1.25fr_0.95fr]">
      <article class="app-panel">
        <div class="app-section-head">
          <div>
            <p class="app-section-kicker">Desk Input</p>
            <h3 class="app-section-title">司机台输入</h3>
            <p class="app-section-copy">按钮和拉杆会被编码成 46 字节帧，由后端 `DriverDeskSource` 真正接收。</p>
          </div>
          <span class="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-400">
            100 ms 发一帧
          </span>
        </div>

        <div class="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:bg-white/10"
            @click="applyPreset('ato-ready')"
          >
            预置 ATO 起车
          </button>
          <button
            type="button"
            class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:bg-white/10"
            @click="applyPreset('traction-50')"
          >
            预置手动牵引 50%
          </button>
          <button
            type="button"
            class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:bg-white/10"
            @click="applyPreset('brake-40')"
          >
            预置手动制动 40%
          </button>
          <button
            type="button"
            class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:bg-white/10"
            @click="applyPreset('coast')"
          >
            回到惰行
          </button>
        </div>

        <div class="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div class="rounded-[1rem] border border-white/10 bg-black/10 px-4 py-4">
            <h4 class="text-sm font-semibold text-slate-100">方向与主手柄</h4>

            <div class="mt-3 space-y-3">
              <div>
                <p class="text-xs text-slate-500">方向</p>
                <div class="mt-2 flex flex-wrap gap-2">
                  <button
                    v-for="item in directionOptions"
                    :key="item.value"
                    type="button"
                    class="rounded-lg border px-3 py-2 text-xs transition"
                    :class="inputState.direction === item.value
                      ? 'border-cyan-400/60 bg-cyan-400/10 text-cyan-100'
                      : 'border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-slate-200'"
                    @click="setInput({ direction: item.value })"
                  >
                    {{ item.label }}
                  </button>
                </div>
              </div>

              <div>
                <p class="text-xs text-slate-500">主手柄</p>
                <div class="mt-2 flex flex-wrap gap-2">
                  <button
                    v-for="item in handleOptions"
                    :key="item.value"
                    type="button"
                    class="rounded-lg border px-3 py-2 text-xs transition"
                    :class="Number(inputState.main_handle_raw) === item.value
                      ? handleButtonClass(item.value)
                      : 'border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-slate-200'"
                    @click="setHandle(item.value)"
                  >
                    {{ item.label }}
                  </button>
                </div>
              </div>

              <label class="block">
                <span class="text-xs text-slate-500">{{ handlePercentLabel }}</span>
                <input
                  :value="handlePercentValue"
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  class="mt-3 w-full accent-cyan-400"
                  @input="updateHandlePercent($event.target.value)"
                >
                <p class="mt-2 text-sm text-slate-200">{{ handlePercentValue }}%</p>
              </label>
            </div>
          </div>

          <div class="rounded-[1rem] border border-white/10 bg-black/10 px-4 py-4">
            <h4 class="text-sm font-semibold text-slate-100">持续状态位</h4>
            <div class="mt-3 grid grid-cols-2 gap-2 text-sm">
              <button
                v-for="toggle in toggleFields"
                :key="toggle.key"
                type="button"
                class="rounded-lg border px-3 py-2 text-left transition"
                :class="inputState[toggle.key]
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100'
                  : 'border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-slate-200'"
                @click="setInput({ [toggle.key]: !inputState[toggle.key] })"
              >
                {{ toggle.label }}
              </button>
            </div>
          </div>
        </div>

        <div class="mt-4 rounded-[1rem] border border-white/10 bg-black/10 px-4 py-4">
          <h4 class="text-sm font-semibold text-slate-100">瞬时按钮</h4>
          <div class="mt-3 flex flex-wrap gap-2">
            <button
              v-for="pulse in pulseFields"
              :key="pulse.key"
              type="button"
              class="rounded-lg border border-amber-700/50 bg-amber-950/25 px-3 py-2 text-xs text-amber-200 transition hover:border-amber-500"
              @click="pulseField(pulse.key)"
            >
              {{ pulse.label }}
            </button>
          </div>
        </div>

        <div class="mt-4 rounded-[1rem] border border-white/10 bg-black/10 px-4 py-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h4 class="text-sm font-semibold text-slate-100">后端收到的最近驾驶输入</h4>
              <p class="mt-1 text-xs text-slate-500">这部分直接来自现有 dashboard 状态，不是协议模拟器本地自说自话。</p>
            </div>
            <span class="text-[11px] text-slate-500">{{ activeDriverInput ? formatEpochTime(activeDriverInput.updated_at) : '等待回显' }}</span>
          </div>

          <div v-if="activeDriverInput" class="mt-3 grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">来源</p>
              <p class="mt-1 text-sm text-slate-200">{{ activeDriverInput.source }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">控制模式</p>
              <p class="mt-1 text-sm text-slate-200">{{ activeDriverInput.control_mode }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">牵引级位</p>
              <p class="app-metric-value">{{ activeDriverInput.traction_level ?? 0 }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">制动级位</p>
              <p class="app-metric-value">{{ activeDriverInput.brake_level ?? 0 }}</p>
            </div>
          </div>

          <div v-else class="mt-3 rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-5 text-sm text-slate-500">
            还没从后端看到 `driver_input` 回显。若协议模拟器已启动，请先确认 Broker、后端 `DATA_SOURCE=zmq` 和车辆进程是否都已启动。
          </div>
        </div>
      </article>

      <div class="space-y-4">
        <article class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">PLC Uplink</p>
              <h3 class="app-section-title">后端回写给司机台</h3>
              <p class="app-section-copy">这里显示的是后端发回 28 字节上行帧后，协议模拟器解码出来的灯光与速度。</p>
            </div>
            <span class="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-400">
              {{ simulator.last_uplink_received_at ? formatEpochTime(simulator.last_uplink_received_at) : '尚未收到' }}
            </span>
          </div>

          <div class="mt-4 grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">速度回显</p>
              <p class="app-metric-value">{{ feedback.vehicle_speed_kmh ?? 0 }}</p>
              <p class="mt-1 text-xs text-slate-500">km/h</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">连接状态</p>
              <p class="mt-1 text-sm text-slate-200">{{ simulator.client_connected ? '后端已连上' : '后端未连上' }}</p>
            </div>
          </div>

          <div class="mt-4 grid grid-cols-2 gap-2 text-sm">
            <div
              v-for="lamp in feedbackLamps"
              :key="lamp.key"
              class="rounded-lg border px-3 py-2"
              :class="feedback[lamp.key]
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100'
                : 'border-white/10 bg-white/[0.03] text-slate-500'"
            >
              {{ lamp.label }}
            </div>
          </div>
        </article>

        <article class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Live Vehicle</p>
              <h3 class="app-section-title">现有前端联动快照</h3>
              <p class="app-section-copy">这一块复用现有车辆状态数据，用来证明你的司机台操作已经引发车端状态变化。</p>
            </div>
            <RouterLink
              to="/vehicle"
              class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:bg-white/10"
            >
              打开旧版车辆页
            </RouterLink>
          </div>

          <VehicleCockpit
            :vehicle="liveVehicle"
            :power="simStore.power"
            :color="simStore.vehicleColor"
            :stop-error-cm="liveVehicle && simStore.selectedVehicle?.vehicle_id === liveVehicle.vehicle_id ? simStore.currentStopErrorCm : null"
            :parking-records="simStore.parkingRecords"
            :last-control-command="simStore.lastControlCommand"
            class="mt-4"
          />
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import {
  getDriverDeskSimStatus,
  pulseDriverDeskSim,
  startDriverDeskSim,
  stopDriverDeskSim,
  updateDriverDeskSimInput,
} from '@/api/driverDeskSim'
import VehicleCockpit from '@/components/VehicleCockpit.vue'
import { usePageSimulation } from '@/composables/usePageSimulation'
import { useUiStore } from '@/stores/ui'

const simStore = usePageSimulation()
const ui = useUiStore()

const status = ref({
  simulator: {
    running: false,
    listening: false,
    client_connected: false,
    input_state: {},
    feedback_state: {},
  },
  bridge: {
    running: false,
    source_status: null,
  },
})

const simulator = computed(() => status.value.simulator ?? {})
const bridge = computed(() => status.value.bridge ?? {})
const inputState = computed(() => simulator.value.input_state ?? {})
const feedback = computed(() => simulator.value.feedback_state ?? {})
const activeVehicleId = computed(() => bridge.value.vehicle_id ?? simulator.value.vehicle_id ?? 'TRAIN-001')
const liveVehicle = computed(() =>
  simStore.vehicles.find((vehicle) => vehicle.vehicle_id === activeVehicleId.value) ?? null
)
const activeDriverInput = computed(() =>
  simStore.driverInputs.find((item) => item.vehicle_id === activeVehicleId.value) ?? null
)

const directionOptions = [
  { value: 'forward', label: '向前' },
  { value: 'neutral', label: '中立' },
  { value: 'backward', label: '向后' },
]

const handleOptions = [
  { value: 0, label: '惰行' },
  { value: 1, label: '牵引' },
  { value: 2, label: '制动' },
  { value: 4, label: '快制' },
]

const toggleFields = [
  { key: 'key_switch', label: '钥匙开关' },
  { key: 'door_closed_light', label: '门关好灯' },
  { key: 'ato_capable', label: '具备 ATO' },
  { key: 'ato_active', label: '激活 ATO' },
  { key: 'parking_release', label: '停放缓解' },
  { key: 'emergency_button', label: '紧急按钮保持' },
  { key: 'vigilance_allow', label: '警惕允许解除' },
  { key: 'network_fault_light', label: '网络故障灯' },
]

const pulseFields = [
  { key: 'ato_start_btn', label: 'ATO 启动' },
  { key: 'open_left_door', label: '开左门' },
  { key: 'open_right_door', label: '开右门' },
  { key: 'close_left_door', label: '关左门' },
  { key: 'close_right_door', label: '关右门' },
  { key: 'parking_apply', label: '停放施加' },
  { key: 'parking_release', label: '停放缓解脉冲' },
  { key: 'horn', label: '电笛' },
  { key: 'forced_release', label: '强迫缓解' },
  { key: 'forced_pump', label: '强迫泵风' },
]

const feedbackLamps = [
  { key: 'high_voltage_on', label: '高断合灯' },
  { key: 'brake_bad_light', label: '制动缓解不良' },
  { key: 'door_open_light', label: '开门灯' },
  { key: 'door_closed_light', label: '门关好灯' },
  { key: 'network_fault', label: '网络故障' },
  { key: 'ato_capable', label: '具备 ATO' },
  { key: 'ato_active', label: '激活 ATO' },
  { key: 'auto_reverse_cap', label: '具备折返' },
  { key: 'auto_reverse_active', label: '激活折返' },
  { key: 'wash_mode_status', label: '洗车模式' },
]

const handlePercentLabel = computed(() =>
  Number(inputState.value.main_handle_raw) === 2 || Number(inputState.value.main_handle_raw) === 4
    ? '制动极位'
    : '牵引极位'
)

const handlePercentValue = computed(() =>
  Number(inputState.value.main_handle_raw) === 2 || Number(inputState.value.main_handle_raw) === 4
    ? Number(inputState.value.brake_percent ?? 0)
    : Number(inputState.value.traction_percent ?? 0)
)

let pollTimer = null

onMounted(async () => {
  await refreshStatus()
  pollTimer = window.setInterval(refreshStatus, 300)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})

async function refreshStatus() {
  try {
    status.value = await getDriverDeskSimStatus()
  } catch (err) {
    console.warn('[driver-desk-sim] status refresh failed', err?.message ?? err)
  }
}

async function startRig() {
  try {
    status.value = await startDriverDeskSim({
      vehicle_id: activeVehicleId.value,
      simulator_host: '127.0.0.1',
      simulator_port: 18001,
      pulse_width_ms: 250,
    })
    ui.showToast({
      type: 'success',
      title: '本地司机台联调已启动',
      message: '现在可以开始推拉手柄，并观察现有车辆页面和灯光回写。',
      duration: 2600,
    })
  } catch (err) {
    ui.showToast({
      type: 'error',
      title: '启动失败',
      message: err.response?.data?.detail ?? err.message ?? 'driver_desk_sim_start_failed',
      duration: 3600,
    })
  }
}

async function stopRig() {
  try {
    status.value = await stopDriverDeskSim()
    ui.showToast({
      type: 'info',
      title: '本地司机台联调已停止',
      message: '协议模拟器和后端桥接都已经停止。',
      duration: 2200,
    })
  } catch (err) {
    ui.showToast({
      type: 'error',
      title: '停止失败',
      message: err.response?.data?.detail ?? err.message ?? 'driver_desk_sim_stop_failed',
      duration: 3600,
    })
  }
}

async function setInput(patch) {
  try {
    status.value.simulator.input_state = {
      ...(status.value.simulator.input_state ?? {}),
      ...patch,
    }
    status.value = await updateDriverDeskSimInput(patch)
  } catch (err) {
    ui.showToast({
      type: 'error',
      title: '输入更新失败',
      message: err.response?.data?.detail ?? err.message ?? 'driver_desk_input_update_failed',
      duration: 3000,
    })
  }
}

async function pulseField(fieldName) {
  try {
    status.value = await pulseDriverDeskSim(fieldName)
  } catch (err) {
    ui.showToast({
      type: 'error',
      title: '按钮脉冲失败',
      message: err.response?.data?.detail ?? err.message ?? 'driver_desk_pulse_failed',
      duration: 3000,
    })
  }
}

function setHandle(handle) {
  if (handle === 1) {
    setInput({ main_handle_raw: 1, brake_percent: 0 })
    return
  }
  if (handle === 2 || handle === 4) {
    setInput({ main_handle_raw: handle, traction_percent: 0 })
    return
  }
  setInput({ main_handle_raw: 0, traction_percent: 0, brake_percent: 0 })
}

function updateHandlePercent(value) {
  const numeric = Number(value)
  if (Number(inputState.value.main_handle_raw) === 2 || Number(inputState.value.main_handle_raw) === 4) {
    setInput({ brake_percent: numeric, traction_percent: 0 })
    return
  }
  setInput({ traction_percent: numeric, brake_percent: 0 })
}

function applyPreset(preset) {
  if (preset === 'ato-ready') {
    setInput({
      direction: 'forward',
      main_handle_raw: 0,
      traction_percent: 0,
      brake_percent: 0,
      key_switch: true,
      door_closed_light: true,
      ato_capable: true,
      ato_active: true,
      emergency_button: false,
      parking_release: true,
    })
    pulseField('ato_start_btn')
    return
  }
  if (preset === 'traction-50') {
    setInput({
      direction: 'forward',
      main_handle_raw: 1,
      traction_percent: 50,
      brake_percent: 0,
      key_switch: true,
      emergency_button: false,
    })
    return
  }
  if (preset === 'brake-40') {
    setInput({
      main_handle_raw: 2,
      traction_percent: 0,
      brake_percent: 40,
    })
    return
  }
  setInput({
    main_handle_raw: 0,
    traction_percent: 0,
    brake_percent: 0,
    emergency_button: false,
  })
}

function handleButtonClass(handle) {
  if (handle === 1) return 'border-emerald-500/50 bg-emerald-500/10 text-emerald-100'
  if (handle === 2) return 'border-amber-500/50 bg-amber-500/10 text-amber-100'
  if (handle === 4) return 'border-red-500/50 bg-red-500/10 text-red-100'
  return 'border-cyan-400/60 bg-cyan-400/10 text-cyan-100'
}

function formatEpochTime(value) {
  if (value == null) return '—'
  const numeric = Number(value)
  const timestamp = Number.isFinite(numeric) ? (numeric > 1e12 ? numeric : numeric * 1000) : Date.parse(value)
  if (!Number.isFinite(timestamp)) return '—'
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
</script>
