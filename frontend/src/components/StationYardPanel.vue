<template>
  <section class="overflow-hidden rounded-sm border border-[#252538] bg-black">
    <div class="relative min-h-[460px] bg-black">
      <div class="pointer-events-none absolute left-1/2 top-3 z-10 -translate-x-1/2 text-center">
        <div class="text-2xl font-semibold text-white">{{ station.name }}</div>
      </div>

      <div v-if="hasLocalEdges" class="px-2 pb-2 pt-10">
        <svg
          class="block h-[430px] w-full"
          :viewBox="`${canvasViewBox.minX} ${canvasViewBox.minY} ${canvasViewBox.width} ${canvasViewBox.height}`"
          role="img"
          :aria-label="`${station.name} 站场图`"
        >
          <rect
            :x="canvasViewBox.minX"
            :y="canvasViewBox.minY"
            :width="canvasViewBox.width"
            :height="canvasViewBox.height"
            fill="#000000"
          />

          <g class="direction-labels">
            <text
              :x="canvasViewBox.minX + 12"
              :y="directionLabelY - 15"
              fill="#f8fafc"
              font-size="7"
              font-family="'Courier New', monospace"
            >
              ← {{ leftDirectionLabel }}
            </text>
            <text
              :x="canvasViewBox.maxX - 12"
              :y="directionLabelY + 25"
              fill="#f8fafc"
              font-size="7"
              text-anchor="end"
              font-family="'Courier New', monospace"
            >
              {{ rightDirectionLabel }} →
            </text>
          </g>

          <g id="yard-tracks">
            <polyline
              v-for="edge in localEdges"
              :key="`rail-${edge.seg_id}`"
              :points="polylinePoints(edge.points)"
              :stroke="railStroke(edge)"
              :stroke-width="railWidth(edge)"
              stroke-linecap="butt"
              stroke-linejoin="miter"
              fill="none"
            />
          </g>

          <g>
            <line
              v-for="line in trackConnectors"
              :key="`track-connector-${line.key}`"
              :x1="line.x1"
              :y1="line.y1"
              :x2="line.x2"
              :y2="line.y2"
              stroke="#9a9cff"
              stroke-width="1.25"
              stroke-linecap="butt"
            />
            <line
              v-for="line in turnoutBranchLines"
              :key="line.key"
              :x1="line.x1"
              :y1="line.y1"
              :x2="line.x2"
              :y2="line.y2"
              :stroke="turnoutBranchStroke(line)"
              :stroke-width="line.active ? 1.8 : 1.1"
              stroke-linecap="butt"
            />
          </g>

          <g>
            <polyline
              v-for="item in highlightedEdgeStates"
              :key="`live-${item.edge.seg_id}`"
              :points="polylinePoints(item.edge.points)"
              :stroke="aspectStroke(item.segment)"
              :stroke-width="item.segment.occupied || item.segment.aspect === 'red' ? 3 : 2"
              stroke-linecap="butt"
              stroke-linejoin="miter"
              fill="none"
            />
          </g>

          <g v-for="label in visibleSegmentLabels" :key="`seg-label-${label.seg_id}`">
            <text
              :x="label.x"
              :y="label.y"
              :fill="segmentLabelColor(label)"
              font-size="5"
              text-anchor="middle"
              font-family="'Courier New', monospace"
            >
              {{ compactId(label.seg_id) }}
            </text>
          </g>

          <text
            v-for="annotation in schematicAnnotations"
            :key="`schematic-annotation-${annotation.text}-${annotation.x}-${annotation.y}`"
            :x="annotation.x"
            :y="annotation.y"
            fill="#22c55e"
            font-size="6.5"
            text-anchor="middle"
            font-family="'Courier New', monospace"
          >
            {{ annotation.text }}
          </text>

          <g v-for="label in platformLabels" :key="`platform-label-${label.seg_id}`">
            <rect
              v-if="isReferenceSchematic"
              :x="label.x - referencePlatformWidth(label) / 2"
              :y="label.y - referencePlatformHeight(label) / 2"
              :width="referencePlatformWidth(label)"
              :height="referencePlatformHeight(label)"
              fill="#050505"
              stroke="#d7d7e8"
              stroke-width="1"
            />
            <line
              v-else
              :x1="label.x - 16"
              :x2="label.x + 16"
              :y1="label.y"
              :y2="label.y"
              stroke="#d7d7e8"
              stroke-width="2.4"
            />
            <text
              v-if="!isReferenceSchematic"
              :x="label.x"
              :y="label.y - 4"
              fill="#f8fafc"
              font-size="5.4"
              text-anchor="middle"
              font-family="'Courier New', monospace"
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
              stroke="#d1d5db"
              stroke-width="0.8"
            />
            <line
              :x1="signal.x"
              :x2="signalHeadX(signal)"
              :y1="signal.headY"
              :y2="signal.headY"
              stroke="#d1d5db"
              stroke-width="0.8"
            />
            <circle
              :cx="signalHeadX(signal)"
              :cy="signal.headY"
              r="3"
              :fill="signalFill(signal.state)"
              stroke="#d1d5db"
              stroke-width="0.7"
            />
            <circle
              :cx="signalHeadX(signal) + signalSpareOffset(signal)"
              :cy="signal.headY"
              r="2.6"
              fill="#050505"
              stroke="#d1d5db"
              stroke-width="0.6"
            />
            <text
              :x="signalLabelX(signal)"
              :y="signal.labelY"
              fill="#e5e7eb"
              font-size="5.4"
              font-weight="700"
              :text-anchor="signalTextAnchor(signal)"
              font-family="'Courier New', monospace"
            >
              {{ compactId(signal.signal_id) }}
            </text>
          </g>

          <g
            v-for="turnout in localTurnoutsWithGuards"
            :key="`turnout-${turnout.turnout_id}-${turnout.position}`"
          >
            <circle
              :cx="turnout.graph_x"
              :cy="turnout.graph_y"
              r="1.15"
              :fill="turnout.locked ? '#ef4444' : '#9a9cff'"
            />
            <text
              v-if="!isReferenceSchematic"
              :x="turnout.graph_x"
              :y="turnout.graph_y + turnoutLabelOffset(turnout)"
              :fill="turnout.locked ? '#ef4444' : '#22c55e'"
              font-size="5"
              text-anchor="middle"
              font-family="'Courier New', monospace"
            >
              {{ compactId(turnout.turnout_id) }}
            </text>
          </g>

          <g
            v-for="vehicle in vehicleMarkers"
            :key="`vehicle-${vehicle.vehicle_id}`"
            class="yard-vehicle-marker"
            :style="{ transform: `translate(${vehicle.x}px, ${vehicle.y}px)` }"
          >
            <rect
              x="-10"
              y="-4.5"
              width="20"
              height="9"
              rx="1.5"
              :fill="vehicle.emergency_brake ? '#dc2626' : '#f59e0b'"
              stroke="#f8fafc"
              stroke-width="0.8"
            />
            <text
              x="0"
              :y="vehicle.labelY - vehicle.y"
              fill="#f8fafc"
              font-size="5.8"
              font-weight="700"
              text-anchor="middle"
              font-family="'Courier New', monospace"
            >
              {{ vehicle.vehicle_id }}
            </text>
          </g>

        </svg>
      </div>

      <div v-else class="flex min-h-[460px] items-center justify-center px-8 text-center">
        <div class="font-mono text-sm text-slate-500">
          <span class="block text-lg font-semibold text-slate-300">暂无站场图数据</span>
          <span class="mt-2 block text-xs">请确认当前加载的是包含 yard_layout 的真实线路数据，而不是旧版 mock line-layout。</span>
        </div>
      </div>
    </div>

  </section>
</template>

<style scoped>
.yard-vehicle-marker,
.yard-vehicle-marker rect,
.yard-vehicle-marker text {
  transition: transform 0.45s linear;
}
</style>

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

const fallbackViewBox = {
  minX: 0,
  minY: 0,
  maxX: 1000,
  maxY: 360,
  width: 1000,
  height: 360,
}

const localEdges = computed(() => arrayOrEmpty(yard.value?.localEdges))
const localEdgesCount = computed(() => localEdges.value.length)
const hasLocalEdges = computed(() => localEdgesCount.value > 0)
const platformLabels = computed(() => arrayOrEmpty(yard.value?.platformLabels))
const segmentLabelMarkers = computed(() => arrayOrEmpty(yard.value?.segmentLabelMarkers))
const viewBox = computed(() => yard.value?.viewBox ?? fallbackViewBox)
const canvasViewBox = computed(() => ({
  minX: viewBox.value.minX - 14,
  minY: viewBox.value.minY - 28,
  maxX: viewBox.value.maxX + 14,
  maxY: viewBox.value.maxY + 30,
  width: viewBox.value.width + 28,
  height: viewBox.value.height + 58,
}))
const liveEdgeStates = computed(() => arrayOrEmpty(yard.value?.liveEdgeStates))
const trackConnectors = computed(() => arrayOrEmpty(yard.value?.trackConnectors))
const highlightedEdgeStates = computed(() =>
  liveEdgeStates.value.filter(({ segment }) =>
    segment?.occupied || ['red', 'yellow'].includes(segment?.aspect),
  ),
)
const turnoutBranchLines = computed(() => arrayOrEmpty(yard.value?.turnoutBranchLines))
const localSignalMarkers = computed(() => arrayOrEmpty(yard.value?.localSignalMarkers))
const localTurnoutsWithGuards = computed(() => arrayOrEmpty(yard.value?.localTurnoutsWithGuards))
const localVehicles = computed(() => arrayOrEmpty(yard.value?.localVehicles))
const vehicleMarkers = computed(() => arrayOrEmpty(yard.value?.vehicleMarkers))
const isReferenceSchematic = computed(() => Boolean(yard.value?.isReferenceSchematic))
const schematicAnnotations = computed(() => arrayOrEmpty(yard.value?.schematicAnnotations))
const directionLabelY = computed(() => {
  const ys = localEdges.value.flatMap((edge) =>
    arrayOrEmpty(edge.points).map((point) => Number(point?.[1])).filter(Number.isFinite),
  ).sort((a, b) => a - b)
  return ys.length ? ys[Math.floor(ys.length / 2)] : 0
})
const visibleSegmentLabels = computed(() => {
  const minimumGap = Math.max(30, viewBox.value.width / 18)
  const lastXByLane = new Map()
  return [...segmentLabelMarkers.value]
    .sort((a, b) => a.y - b.y || a.x - b.x)
    .filter((label) => {
      const lane = Math.round(label.y / 8)
      const previousX = lastXByLane.get(lane)
      if (previousX != null && label.x - previousX < minimumGap) return false
      lastXByLane.set(lane, label.x)
      return true
    })
})

const leftDirectionLabel = computed(() => {
  const prev = props.stations.find((station) => station.position < props.station.position)
  return prev ? `${prev.name} 方向` : '上行方向'
})

const rightDirectionLabel = computed(() => {
  const next = [...props.stations].reverse().find((station) => station.position > props.station.position)
  return next ? `${next.name} 方向` : '下行方向'
})

function arrayOrEmpty(value) {
  return Array.isArray(value) ? value : []
}

function polylinePoints(points = []) {
  return points
    .filter((point) => Array.isArray(point) && point.length >= 2)
    .map((point) => `${point[0]},${point[1]}`)
    .join(' ')
}


function compactId(value) {
  return String(value ?? '')
    .replace(/^SIG[-_]?/i, 'S')
    .replace(/^SW[-_]?/i, 'W')
    .replace(/^SEC[-_]?/i, '')
    .replace(/^TRACK[-_]?/i, 'T')
}

function signalFill(state) {
  if (state === 'red') return '#ef4444'
  if (state === 'yellow') return '#facc15'
  if (state === 'green') return '#22c55e'
  return '#0f172a'
}

function aspectStroke(segment) {
  const aspect = segment?.aspect ?? (segment?.occupied ? 'red' : 'green')
  if (aspect === 'red') return '#ef4444'
  if (aspect === 'yellow') return '#facc15'
  return '#22c55e'
}

function railStroke(edge) {
  return edge.branch === 'branch' ? '#8585df' : '#a0a0ff'
}

function railWidth(edge) {
  return edge.branch === 'branch' ? 1.15 : 1.45
}

function turnoutBranchStroke(line) {
  if (line.active) return '#d9dcff'
  return '#5556c8'
}

function segmentLabelColor(label) {
  if (label.occupied || label.aspect === 'red') return '#ef4444'
  if (label.aspect === 'yellow') return '#facc15'
  return '#22c55e'
}

function turnoutLabelOffset(turnout) {
  return turnout.graph_y <= (props.station.graph_y ?? 252) ? -8 : 12
}

function referencePlatformWidth(label) {
  return Math.max(80, Number(label.width ?? 0))
}

function referencePlatformHeight(label) {
  return Math.max(10, Number(label.height ?? 0))
}

function signalHeadX(signal) {
  if (signal.facing === 'left') return signal.x - 5.2
  if (signal.facing === 'right') return signal.x + 5.2
  return signal.x
}

function signalSpareOffset(signal) {
  if (signal.facing === 'left') return -6.2
  return 6.2
}

function signalLabelX(signal) {
  if (signal.facing === 'left') return signal.x - 7
  if (signal.facing === 'right') return signal.x + 7
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

</script>
