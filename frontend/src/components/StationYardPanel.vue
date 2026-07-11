<template>
  <section class="rounded-[1.4rem] border border-emerald-500/15 bg-[#07110d] px-5 py-5 shadow-[0_18px_50px_rgba(0,0,0,0.28)]">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker text-emerald-300/80">Station Drilldown</p>
        <h3 class="app-section-title">{{ station.name }} 站场图</h3>
        <p class="app-section-copy text-slate-400">
          以当前站为中心裁切图窗，保留平台股道、咽喉道岔、防护信号和站内列车，并按联锁表示盘风格压成一张高密度图面。
        </p>
      </div>
      <button
        type="button"
        class="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:bg-white/10"
        @click="$emit('close')"
      >
        收起站场
      </button>
    </div>

    <div class="mt-4 flex flex-wrap gap-2 text-[11px]">
      <span class="rounded-full border border-emerald-500/20 bg-emerald-500/8 px-3 py-1 text-emerald-200">图段 {{ localEdges.length }}</span>
      <span class="rounded-full border border-emerald-500/20 bg-emerald-500/8 px-3 py-1 text-emerald-200">平台 {{ platformEdges.length }}</span>
      <span class="rounded-full border border-sky-500/20 bg-sky-500/8 px-3 py-1 text-sky-200">咽喉 {{ localTurnoutsWithGuards.length }}</span>
      <span class="rounded-full border border-amber-500/20 bg-amber-500/8 px-3 py-1 text-amber-200">防护信号 {{ guardSignals.length }}</span>
      <span class="rounded-full border border-red-500/20 bg-red-500/8 px-3 py-1 text-red-200">占用 {{ occupiedSegments.length }}</span>
      <span class="rounded-full border border-violet-500/20 bg-violet-500/8 px-3 py-1 text-violet-200">列车 {{ localVehicles.length }}</span>
    </div>

    <div class="mt-5 grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1.9fr)_minmax(22rem,0.85fr)]">
      <div class="rounded-[1.2rem] border border-white/8 bg-[#020503] px-4 py-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h4 class="text-sm font-semibold tracking-[0.16em] text-emerald-100">联锁表示盘风格站场示意</h4>
            <p class="mt-1 text-[11px] text-slate-500">
              里程 {{ formatPosition(range.start) }} - {{ formatPosition(range.end) }} · 平台 {{ platformTrackLabel }}
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-[10px] uppercase tracking-[0.14em] text-slate-500">
            <span class="inline-flex items-center gap-1.5">
              <span class="h-px w-7 bg-[#2fff69]" />
              Main rail
            </span>
            <span class="inline-flex items-center gap-1.5">
              <span class="h-px w-7 bg-[#4264ff]" />
              Crossover
            </span>
            <span class="inline-flex items-center gap-1.5">
              <span class="h-2 w-2 rounded-full bg-red-400" />
              Stop
            </span>
            <span class="inline-flex items-center gap-1.5">
              <span class="h-2 w-2 rounded-full bg-amber-300" />
              Approach
            </span>
            <span class="inline-flex items-center gap-1.5">
              <span class="h-2 w-2 rounded-full bg-emerald-300" />
              Clear
            </span>
          </div>
        </div>

        <div class="mt-4 overflow-hidden rounded-[1rem] border border-emerald-400/10 bg-[#010101]">
          <div v-if="localEdges.length" class="p-2 sm:p-3">
            <svg
              class="block h-auto w-full"
              :viewBox="`${viewBox.minX} ${viewBox.minY} ${viewBox.width} ${viewBox.height}`"
              role="img"
              :aria-label="`${station.name} 站场联锁示意图`"
            >
              <rect
                :x="viewBox.minX"
                :y="viewBox.minY"
                :width="viewBox.width"
                :height="viewBox.height"
                fill="#010101"
              />

              <g opacity="0.1">
                <line
                  v-for="gridX in gridXs"
                  :key="`grid-x-${gridX}`"
                  :x1="gridX"
                  :x2="gridX"
                  :y1="viewBox.minY"
                  :y2="viewBox.maxY"
                  stroke="#15512b"
                  stroke-width="0.6"
                />
                <line
                  v-for="gridY in gridYs"
                  :key="`grid-y-${gridY}`"
                  :x1="viewBox.minX"
                  :x2="viewBox.maxX"
                  :y1="gridY"
                  :y2="gridY"
                  stroke="#15512b"
                  stroke-width="0.6"
                />
              </g>

              <rect
                :x="viewBox.minX + 2.5"
                :y="viewBox.minY + 2.5"
                :width="viewBox.width - 5"
                :height="viewBox.height - 5"
                fill="none"
                stroke="#11351d"
                stroke-width="1"
              />

              <line
                v-if="station.graph_x != null"
                :x1="station.graph_x"
                :x2="station.graph_x"
                :y1="viewBox.minY + 8"
                :y2="viewBox.maxY - 8"
                stroke="#14532d"
                stroke-width="0.8"
                stroke-dasharray="3 4"
                opacity="0.7"
              />

              <g>
                <line
                  v-for="edge in localEdges"
                  :key="`rail-base-${edge.seg_id}`"
                  :x1="edge.x1"
                  :y1="edge.y1"
                  :x2="edge.x2"
                  :y2="edge.y2"
                  :stroke="railStroke(edge)"
                  stroke-width="3.8"
                  stroke-linecap="square"
                />
                <line
                  v-for="edge in localEdges"
                  :key="`rail-core-${edge.seg_id}`"
                  :x1="edge.x1"
                  :y1="edge.y1"
                  :x2="edge.x2"
                  :y2="edge.y2"
                  :stroke="railHighlight(edge)"
                  stroke-width="1.2"
                  stroke-linecap="square"
                  opacity="0.95"
                />
                <line
                  v-for="line in turnoutBranchLines"
                  :key="line.key"
                  :x1="line.x1"
                  :y1="line.y1"
                  :x2="line.x2"
                  :y2="line.y2"
                  :stroke="turnoutBranchStroke(line)"
                  :stroke-width="line.active ? 2.8 : 2.1"
                  stroke-linecap="square"
                />
                <line
                  v-for="item in liveEdgeStates"
                  :key="`live-${item.edge.seg_id}`"
                  :x1="item.edge.x1"
                  :y1="item.edge.y1"
                  :x2="item.edge.x2"
                  :y2="item.edge.y2"
                  :stroke="aspectStroke(item.segment)"
                  :stroke-width="item.segment.occupied ? 2.6 : 1.7"
                  stroke-linecap="square"
                />
              </g>

              <g v-for="label in segmentLabelMarkers" :key="`seg-label-${label.seg_id}`">
                <text
                  :x="label.x"
                  :y="label.y"
                  :fill="segmentLabelColor(label)"
                  font-size="5.8"
                  text-anchor="middle"
                  font-family="Consolas, Menlo, monospace"
                  opacity="0.92"
                >
                  {{ label.seg_id }}
                </text>
              </g>

              <g v-for="label in platformLabels" :key="`platform-label-${label.seg_id}`">
                <rect
                  :x="label.x - 13"
                  :y="label.y - 8"
                  width="26"
                  height="11"
                  fill="#010101"
                  stroke="#3ce674"
                  stroke-width="0.75"
                />
                <text
                  :x="label.x"
                  :y="label.y"
                  fill="#96ff9b"
                  font-size="6.3"
                  text-anchor="middle"
                  font-family="Consolas, Menlo, monospace"
                >
                  {{ label.text }}
                </text>
              </g>

              <g v-for="signal in localSignalMarkers" :key="`signal-${signal.key}`">
                <line
                  :x1="signal.x"
                  :x2="signal.x"
                  :y1="signal.anchorY"
                  :y2="signal.mastBaseY"
                  stroke="#d8ded8"
                  stroke-width="0.9"
                />
                <line
                  :x1="signal.x"
                  :x2="signalHeadX(signal)"
                  :y1="signal.headY"
                  :y2="signal.headY"
                  stroke="#d8ded8"
                  stroke-width="0.9"
                />
                <circle
                  :cx="signalHeadX(signal)"
                  :cy="signal.headY"
                  r="2.15"
                  :fill="signalFill(signal.state)"
                  :stroke="signal.isGuardSignal ? '#f8fafc' : '#9ca3af'"
                  stroke-width="0.45"
                />
                <circle
                  v-if="signal.isGuardSignal"
                  :cx="signalHeadX(signal)"
                  :cy="signal.headY"
                  r="3.55"
                  fill="none"
                  stroke="#e2e8f0"
                  stroke-width="0.45"
                  opacity="0.82"
                />
                <text
                  :x="signalLabelX(signal)"
                  :y="signal.labelY"
                  fill="#d8ded8"
                  font-size="6.1"
                  :text-anchor="signalTextAnchor(signal)"
                  font-family="Consolas, Menlo, monospace"
                >
                  {{ signal.signal_id }}
                </text>
              </g>

              <g v-for="turnout in localTurnoutsWithGuards" :key="`turnout-${turnout.turnout_id}-${turnout.position}`">
                <rect
                  :x="turnout.graph_x - 3.3"
                  :y="turnout.graph_y - 3.3"
                  width="6.6"
                  height="6.6"
                  :fill="turnoutFill(turnout)"
                  :stroke="turnout.locked ? '#fbbf24' : '#d8ded8'"
                  stroke-width="0.8"
                  :transform="`rotate(45 ${turnout.graph_x} ${turnout.graph_y})`"
                />
                <text
                  :x="turnout.graph_x"
                  :y="turnout.graph_y + turnoutLabelOffset(turnout)"
                  fill="#d8ded8"
                  font-size="6.1"
                  text-anchor="middle"
                  font-family="Consolas, Menlo, monospace"
                >
                  W{{ turnout.turnout_id }}
                </text>
              </g>

              <g v-for="vehicle in vehicleMarkers" :key="`vehicle-${vehicle.vehicle_id}`">
                <rect
                  :x="vehicle.x - 7.5"
                  :y="vehicle.y - 3.2"
                  width="15"
                  height="6.4"
                  rx="0.9"
                  :fill="vehicle.emergency_brake ? '#dc2626' : color(vehicle.vehicle_id)"
                  stroke="#f8fafc"
                  stroke-width="0.75"
                />
                <text
                  :x="vehicle.x"
                  :y="vehicle.labelY"
                  fill="#f8fafc"
                  font-size="6.2"
                  font-weight="600"
                  text-anchor="middle"
                  font-family="Consolas, Menlo, monospace"
                >
                  {{ vehicle.vehicle_id }}
                </text>
              </g>

              <g v-if="station.graph_x != null">
                <rect
                  :x="station.graph_x - 31"
                  :y="viewBox.minY + 7"
                  width="62"
                  height="13"
                  fill="#010101"
                  stroke="#31d764"
                  stroke-width="0.75"
                />
                <text
                  :x="station.graph_x"
                  :y="viewBox.minY + 15.8"
                  fill="#9affaa"
                  font-size="6.5"
                  text-anchor="middle"
                  font-family="Consolas, Menlo, monospace"
                >
                  {{ station.name }}
                </text>
              </g>
            </svg>
          </div>

          <div v-else class="px-4 py-10 text-center text-sm text-slate-500">
            当前站点还没有可绘制的拓扑图段。下一步请先核对 `line-layout.json` 中该站附近的 `graph.edges`、`platforms` 与道岔图形坐标。
          </div>
        </div>

        <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
          <div class="rounded-[0.95rem] border border-white/8 bg-white/[0.02] px-3 py-3">
            <p class="text-[10px] uppercase tracking-[0.16em] text-slate-500">Track label</p>
            <p class="mt-1 text-sm text-slate-100">{{ platformTrackLabel }}</p>
          </div>
          <div class="rounded-[0.95rem] border border-white/8 bg-white/[0.02] px-3 py-3">
            <p class="text-[10px] uppercase tracking-[0.16em] text-slate-500">Guard coverage</p>
            <p class="mt-1 text-sm text-slate-100">{{ guardCoverageText }}</p>
          </div>
          <div class="rounded-[0.95rem] border border-white/8 bg-white/[0.02] px-3 py-3">
            <p class="text-[10px] uppercase tracking-[0.16em] text-slate-500">Throat summary</p>
            <p class="mt-1 text-sm text-slate-100">{{ throatSummaryText }}</p>
          </div>
          <div class="rounded-[0.95rem] border border-white/8 bg-white/[0.02] px-3 py-3">
            <p class="text-[10px] uppercase tracking-[0.16em] text-slate-500">Vehicle summary</p>
            <p class="mt-1 text-sm text-slate-100">{{ vehicleSummaryText }}</p>
          </div>
        </div>
      </div>

      <div class="space-y-4">
        <div class="rounded-[1.05rem] border border-white/8 bg-[#030504] px-4 py-4">
          <div class="flex items-center justify-between gap-3">
            <h4 class="text-sm font-semibold text-slate-100">防护信号核对</h4>
            <span class="text-[10px] uppercase tracking-[0.16em] text-slate-500">{{ guardSignals.length }} signals</span>
          </div>

          <div v-if="guardSignals.length" class="mt-3 overflow-hidden rounded-[0.9rem] border border-white/8">
            <table class="min-w-full text-[11px]">
              <thead class="bg-white/[0.04] text-slate-500">
                <tr>
                  <th class="px-3 py-2 text-left font-medium">信号</th>
                  <th class="px-3 py-2 text-right font-medium">显示</th>
                  <th class="px-3 py-2 text-right font-medium">位置</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="signal in orderedSignals"
                  :key="`signal-card-${signal.key}`"
                  class="border-t border-white/6 text-slate-300"
                >
                  <td class="px-3 py-2">
                    <p class="font-medium text-slate-100">{{ signal.signal_id }}</p>
                    <p class="mt-0.5 text-[10px] text-slate-500">防护 {{ signal.guardsText || '—' }}</p>
                  </td>
                  <td class="px-3 py-2 text-right">
                    <span class="rounded-full px-2 py-0.5 text-[10px]" :class="signalBadge(signal.state)">
                      {{ signalStateLabel(signal.state) }}
                    </span>
                  </td>
                  <td class="px-3 py-2 text-right text-slate-400">{{ formatPosition(signal.position) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else class="mt-4 rounded-[0.95rem] border border-dashed border-white/8 bg-white/[0.02] px-3 py-4 text-sm text-slate-500">
            当前图窗内还没有识别到可映射的防护信号。若后端已有信号数据，优先检查信号 `seg_id / track_seg_id` 与区段映射。
          </div>
        </div>

        <div class="rounded-[1.05rem] border border-white/8 bg-[#030504] px-4 py-4">
          <div class="flex items-center justify-between gap-3">
            <h4 class="text-sm font-semibold text-slate-100">咽喉道岔核对</h4>
            <span class="text-[10px] uppercase tracking-[0.16em] text-slate-500">{{ localTurnoutsWithGuards.length }} turnouts</span>
          </div>

          <div v-if="localTurnoutsWithGuards.length" class="mt-3 overflow-hidden rounded-[0.9rem] border border-white/8">
            <table class="min-w-full text-[11px]">
              <thead class="bg-white/[0.04] text-slate-500">
                <tr>
                  <th class="px-3 py-2 text-left font-medium">道岔</th>
                  <th class="px-3 py-2 text-right font-medium">状态</th>
                  <th class="px-3 py-2 text-right font-medium">锁闭</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="turnout in orderedTurnouts"
                  :key="`turnout-card-${turnout.turnout_id}-${turnout.position}`"
                  class="border-t border-white/6 text-slate-300"
                >
                  <td class="px-3 py-2">
                    <p class="font-medium text-slate-100">W{{ turnout.turnout_id }}</p>
                    <p class="mt-0.5 text-[10px] text-slate-500">
                      {{ turnout.guardSignalIds.length ? turnout.guardSignalIds.join(' / ') : '未匹配防护' }}
                    </p>
                  </td>
                  <td class="px-3 py-2 text-right" :class="isReverseState(turnout.state) ? 'text-cyan-300' : 'text-slate-300'">
                    {{ isReverseState(turnout.state) ? '反位' : '定位' }}
                  </td>
                  <td class="px-3 py-2 text-right" :class="turnout.locked ? 'text-amber-300' : 'text-slate-500'">
                    {{ turnout.locked ? '锁闭' : '解锁' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else class="mt-4 rounded-[0.95rem] border border-dashed border-white/8 bg-white/[0.02] px-3 py-4 text-sm text-slate-500">
            当前站场图窗没有映射到咽喉道岔，说明此站要么是简化站位，要么静态拓扑还缺少道岔图形坐标。
          </div>
        </div>

        <div class="rounded-[1.05rem] border border-white/8 bg-[#030504] px-4 py-4">
          <div class="flex items-center justify-between gap-3">
            <h4 class="text-sm font-semibold text-slate-100">站场列车</h4>
            <span class="text-[10px] uppercase tracking-[0.16em] text-slate-500">{{ localVehicles.length }} trains</span>
          </div>

          <div v-if="localVehicles.length" class="mt-3 space-y-2">
            <div
              v-for="vehicle in orderedVehicles"
              :key="vehicle.vehicle_id"
              class="rounded-[0.95rem] border border-white/8 bg-white/[0.02] px-3 py-3"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="inline-flex items-center gap-2 text-sm font-medium text-slate-100">
                  <span class="h-2.5 w-2.5 rounded-full" :style="{ backgroundColor: color(vehicle.vehicle_id) }" />
                  {{ vehicle.vehicle_id }}
                </span>
                <span class="rounded-full px-2 py-0.5 text-[10px]" :class="vehicleBadge(vehicle)">
                  {{ vehicleTag(vehicle) }}
                </span>
              </div>
              <div class="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-slate-400">
                <p>速度 {{ vehicle.speed }} km/h</p>
                <p class="text-right">位置 {{ formatPosition(vehicle.position) }}</p>
                <p>模式 {{ vehicle.mode ?? '—' }}</p>
                <p class="text-right">MA {{ vehicle.ma_limit != null ? formatPosition(vehicle.ma_limit) : '—' }}</p>
              </div>
            </div>
          </div>

          <div v-else class="mt-4 rounded-[0.95rem] border border-dashed border-white/8 bg-white/[0.02] px-3 py-4 text-sm text-slate-500">
            当前没有列车落在该站场图窗。你可以切到别的站点，或者等待实时快照推送车辆位置。
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useLineLayoutStore } from '@/stores/lineLayout'
import { buildStationYardSnapshot } from '@/utils/stationYardTopology'

const props = defineProps({
  station: { type: Object, required: true },
  range: { type: Object, required: true },
  stations: { type: Array, default: () => [] },
  segments: { type: Array, default: () => [] },
  signals: { type: Array, default: () => [] },
  turnouts: { type: Array, default: () => [] },
  vehicles: { type: Array, default: () => [] },
  color: { type: Function, required: true },
})

defineEmits(['close'])

const layoutStore = useLineLayoutStore()
const yard = computed(() =>
  buildStationYardSnapshot({
    station: props.station,
    range: props.range,
    stations: props.stations,
    layout: layoutStore.layout,
    infrastructureSections: layoutStore.infrastructureSections,
    segments: props.segments,
    signals: props.signals,
    turnouts: props.turnouts,
    vehicles: props.vehicles,
  }),
)

const platformTrackLabel = computed(() => yard.value.platformTrackLabel)
const localEdges = computed(() => yard.value.localEdges)
const platformEdges = computed(() => yard.value.platformEdges)
const platformLabels = computed(() => yard.value.platformLabels)
const segmentLabelMarkers = computed(() => yard.value.segmentLabelMarkers)
const viewBox = computed(() => yard.value.viewBox)
const gridXs = computed(() => yard.value.gridXs)
const gridYs = computed(() => yard.value.gridYs)
const liveEdgeStates = computed(() => yard.value.liveEdgeStates)
const occupiedSegments = computed(() => yard.value.occupiedSegments)
const turnoutBranchLines = computed(() => yard.value.turnoutBranchLines)
const guardSignals = computed(() => yard.value.guardSignals)
const localSignalMarkers = computed(() => yard.value.localSignalMarkers)
const localTurnoutsWithGuards = computed(() => yard.value.localTurnoutsWithGuards)
const localVehicles = computed(() => yard.value.localVehicles)
const vehicleMarkers = computed(() => yard.value.vehicleMarkers)
const orderedSignals = computed(() => yard.value.orderedSignals)
const orderedTurnouts = computed(() => yard.value.orderedTurnouts)
const orderedVehicles = computed(() => yard.value.orderedVehicles)
const guardCoverageText = computed(() => yard.value.guardCoverageText)
const throatSummaryText = computed(() => yard.value.throatSummaryText)
const vehicleSummaryText = computed(() => yard.value.vehicleSummaryText)

function formatPosition(value) {
  if (value == null) return '—'
  return `${Math.round(value)} m`
}

function signalStateLabel(state) {
  if (state === 'red') return '红灯'
  if (state === 'yellow') return '黄灯'
  if (state === 'green') return '绿灯'
  return state ?? '未知'
}

function signalFill(state) {
  if (state === 'red') return '#ef4444'
  if (state === 'yellow') return '#f59e0b'
  if (state === 'green') return '#10b981'
  return '#64748b'
}

function signalBadge(state) {
  if (state === 'red') return 'bg-red-950 text-red-300'
  if (state === 'yellow') return 'bg-amber-950 text-amber-300'
  if (state === 'green') return 'bg-emerald-950 text-emerald-300'
  return 'bg-slate-800 text-slate-300'
}

function aspectStroke(segment) {
  const aspect = segment.aspect ?? (segment.occupied ? 'red' : 'green')
  if (aspect === 'red') return '#ff4d4f'
  if (aspect === 'yellow') return '#ffcc4d'
  return '#78ff7d'
}

function railStroke(edge) {
  return edge.branch === 'branch' ? '#204bff' : '#0ea64a'
}

function railHighlight(edge) {
  return edge.branch === 'branch' ? '#8ea2ff' : '#9bff72'
}

function turnoutBranchStroke(line) {
  if (line.active) return line.locked ? '#9db3ff' : '#5f82ff'
  return line.locked ? '#4763c9' : '#2847d6'
}

function segmentLabelColor(label) {
  if (label.occupied || label.aspect === 'red') return '#ff6b6b'
  if (label.aspect === 'yellow') return '#ffd447'
  if (label.aspect === 'branch') return '#7f95ff'
  return '#74ff88'
}

function turnoutFill(turnout) {
  if (turnout.locked) return '#f59e0b'
  if (isReverseState(turnout.state)) return '#5f82ff'
  return '#345444'
}

function turnoutLabelOffset(turnout) {
  return turnout.graph_y <= (props.station.graph_y ?? 252) ? -8 : 12.5
}

function signalHeadX(signal) {
  if (signal.facing === 'left') return signal.x - 5.2
  if (signal.facing === 'right') return signal.x + 5.2
  return signal.x
}

function signalLabelX(signal) {
  if (signal.facing === 'left') return signal.x - 6.8
  if (signal.facing === 'right') return signal.x + 6.8
  return signal.x
}

function signalTextAnchor(signal) {
  if (signal.facing === 'left') return 'end'
  if (signal.facing === 'right') return 'start'
  return 'middle'
}

function isReverseState(state) {
  return state === 'reverse' || state === 'diverging'
}

function vehicleTag(vehicle) {
  const distance = Math.abs((vehicle.position ?? 0) - (props.station.position ?? 0))
  if (distance < 80) return '站内'
  if (distance < 320) return '即将到站'
  return '邻站区间'
}

function vehicleBadge(vehicle) {
  const distance = Math.abs((vehicle.position ?? 0) - (props.station.position ?? 0))
  if (distance < 80) return 'bg-cyan-950 text-cyan-300'
  if (distance < 320) return 'bg-sky-950 text-sky-300'
  return 'bg-slate-800 text-slate-300'
}
</script>
