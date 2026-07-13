<!-- OCC 电子地图：Seg 拓扑 · 列车沿轨 · 区段染色 · 缩放拖拽 -->
<template>
  <div :class="compact ? '' : 'rounded-2xl bg-gray-900 border border-gray-800 p-5'">
    <div v-if="!compact" class="flex flex-wrap items-center justify-between gap-3 mb-3">
      <div>
        <h3 class="text-sm font-semibold text-gray-200">电子地图 · 线路拓扑</h3>
        <p class="text-xs text-gray-500 mt-0.5">
          {{ lineLabel }} · Seg {{ graph?.placed_seg_count ?? 0 }}/{{ graph?.total_seg_count ?? 0 }} · MA 折线 · 信号机 · 滚轮缩放
        </p>
        <p class="text-[11px] text-slate-400 mt-1">
          区段底色表示占用状态；是否允许继续运行请看信号机灯色和 MA。
        </p>
      </div>
      <div class="flex items-center gap-2">
        <span
          v-if="selectedTrain"
          class="text-[10px] px-2 py-1 rounded border"
          :class="selectedPermissionChipClass"
        >
          {{ selectedPermissionText }}
        </span>
        <span
          v-if="selectedMappingText"
          class="text-[10px] px-2 py-1 rounded border border-slate-700 bg-slate-900/90 text-slate-300"
        >
          {{ selectedMappingText }}
        </span>
        <button
          type="button"
          class="text-[10px] px-2 py-1 rounded border transition-colors"
          :class="followTrain
            ? 'border-sky-600 bg-sky-950 text-sky-300'
            : 'border-gray-700 text-gray-400 hover:text-gray-200'"
          @click="followTrain = !followTrain"
        >
          {{ followTrain ? '跟随中' : '跟随选中车' }}
        </button>
        <button
          type="button"
          class="text-[10px] px-2 py-1 rounded border border-gray-700 text-gray-400 hover:text-gray-200"
          @click="reset()"
        >
          重置视图
        </button>
        <span class="text-xs text-gray-500">{{ vehicles.length }} 列</span>
      </div>
    </div>

    <div v-if="!graph?.edges?.length" class="text-sm text-gray-600 py-12 text-center">
      当前还没有收到可绘制的线路拓扑，请确认后端已返回 `sections` 线路数据
    </div>

    <div
      v-else
      class="relative rounded-xl border border-gray-800 bg-[#0a0f1a] overflow-hidden select-none"
      :class="dragging ? 'cursor-grabbing' : 'cursor-grab'"
      :style="{ height: compact ? '240px' : '420px' }"
      @wheel="onWheel"
      @mousedown="onPointerDown"
    >
      <svg
        width="100%"
        height="100%"
        :viewBox="viewBoxString"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <filter id="track-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="1.2" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        <!-- 暗色网格 -->
        <g opacity="0.12">
          <line
            v-for="gx in gridLines.x"
            :key="`gx-${gx}`"
            :x1="gx" :y1="bounds.minY - 30"
            :x2="gx" :y2="bounds.maxY + 30"
            stroke="#475569" stroke-width="0.5"
          />
          <line
            v-for="gy in gridLines.y"
            :key="`gy-${gy}`"
            :x1="bounds.minX - 30" :y1="gy"
            :x2="bounds.maxX + 30" :y2="gy"
            stroke="#475569" stroke-width="0.5"
          />
        </g>

        <!-- MA 进路 Seg 高亮 -->
        <g v-if="selectedMaSegIds.size">
          <polyline
            v-for="edge in graph.edges"
            :key="`ma-${edge.seg_id}`"
            v-show="selectedMaSegIds.has(edge.seg_id)"
            :points="pathPoints(edge)"
            :stroke="color(selectedId)"
            stroke-width="5"
            stroke-linecap="round"
            stroke-linejoin="round"
            fill="none"
            opacity="0.35"
          />
        </g>

        <!-- 相邻区段之间的连续连接线 -->
        <g v-if="graph.connectors?.length">
          <polyline
            v-for="connector in graph.connectors"
            :key="`connector-bed-${connector.key}`"
            :points="pathPoints(connector)"
            :stroke="edgeBedStroke(connectorColor(connector))"
            :stroke-width="connector.branch === 'branch' ? 8 : 10"
            stroke-linecap="round"
            stroke-linejoin="round"
            fill="none"
            opacity="0.88"
          />
          <polyline
            v-for="connector in graph.connectors"
            :key="`connector-core-${connector.key}`"
            :points="pathPoints(connector)"
            :stroke="edgeStroke(connectorColor(connector))"
            :stroke-width="connector.branch === 'branch' ? 2 : 2.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            fill="none"
            opacity="0.92"
          />
        </g>

        <!-- 轨床 + 占用染色 -->
        <g v-for="edge in graph.edges" :key="`track-${edge.seg_id}`">
          <polyline
            :points="pathPoints(edge)"
            :stroke="edgeBedStroke(edgeColor(edge.seg_id))"
            :stroke-width="edge.branch === 'branch' ? 10 : 12"
            stroke-linecap="round"
            stroke-linejoin="round"
            fill="none"
            opacity="0.9"
          />
          <polyline
            :points="pathPoints(edge)"
            :stroke="edgeStroke(edgeColor(edge.seg_id))"
            :stroke-width="edge.branch === 'branch' ? 2.5 : 3.5"
            :stroke-dasharray="edge.branch === 'branch' ? '6 4' : undefined"
            stroke-linecap="round"
            stroke-linejoin="round"
            fill="none"
            :opacity="edge.branch === 'branch' ? 0.75 : 0.95"
            :filter="edgeColor(edge.seg_id) === 'green' ? 'url(#track-glow)' : undefined"
          />
        </g>

        <!-- 选中车 MA 进路折线 -->
        <g v-if="selectedMaPath.length > 1">
          <polyline
            :points="selectedMaPath.map((p) => `${p.x},${p.y}`).join(' ')"
            fill="none"
            :stroke="color(selectedId)"
            stroke-width="2.5"
            stroke-dasharray="5 4"
            opacity="0.85"
          />
          <circle
            :cx="selectedMaPath[selectedMaPath.length - 1].x"
            :cy="selectedMaPath[selectedMaPath.length - 1].y"
            r="3.5"
            :fill="color(selectedId)"
            opacity="0.9"
          />
        </g>

        <!-- 信号机 -->
        <g v-for="sig in visibleSignals" :key="sig.signal_id">
          <line
            :x1="sig.track_x" :y1="sig.track_y"
            :x2="sig.x" :y2="sig.y"
            stroke="#475569" stroke-width="0.8"
          />
          <g :transform="`translate(${sig.x}, ${sig.y}) rotate(${sig.angle + 90})`">
            <rect x="-2.5" y="-5" width="5" height="10" rx="1" fill="#1e293b" stroke="#64748b" stroke-width="0.6" />
            <circle cx="0" cy="-2.5" r="1.4" :fill="sig.state === 'red' ? '#ef4444' : '#450a0a'" />
            <circle cx="0" cy="0" r="1.4" :fill="sig.state === 'yellow' ? '#eab308' : '#422006'" />
            <circle cx="0" cy="2.5" r="1.4" :fill="sig.state === 'green' ? '#22c55e' : '#064e3b'" />
          </g>
          <title>{{ sig.signal_id }} · {{ signalTypeLabel(sig.signal_type) }} · {{ sig.state }} · {{ Math.round(sig.position) }}m</title>
        </g>

        <!-- 车站 -->
        <g v-for="st in visibleStations" :key="st.station_id">
          <rect
            :x="st.graph_x - 14" :y="st.graph_y - 6"
            width="28" height="12" rx="2"
            fill="#1e293b" stroke="#64748b" stroke-width="1"
          />
          <text
            :x="st.graph_x" :y="st.graph_y + 3"
            text-anchor="middle" fill="#94a3b8" font-size="7" font-weight="600"
          >{{ st.name }}</text>
        </g>

        <!-- 道岔 -->
        <g v-for="t in visibleTurnouts" :key="t.turnout_id">
          <polygon
            :points="diamond(t.graph_x, t.graph_y, 4)"
            :fill="t.locked ? '#78350f' : '#1e293b'"
            :stroke="t.locked ? '#fbbf24' : '#64748b'"
            stroke-width="1"
          />
          <title>{{ t.turnout_id }} · {{ t.locked ? '锁闭' : '解锁' }}</title>
        </g>

        <!-- 列车：沿轨道方向的小矩形 + 速度尾迹 -->
        <g
          v-for="train in trainMarkers"
          :key="train.vehicle_id"
          class="cursor-pointer train-marker"
          data-pan-ignore="true"
          :transform="trainTransform(train)"
          @click.stop="$emit('select', train.vehicle_id)"
        >
          <line
            v-if="train.speed > 5"
            :x1="-speedTrailLen(train.speed)"
            y1="0"
            x2="-10"
            y2="0"
            :stroke="train.emergency_brake ? '#fca5a5' : color(train.vehicle_id)"
            stroke-width="2"
            stroke-linecap="round"
            :opacity="0.35"
          />
          <rect
            x="-11" y="-3.5"
            width="22" height="7" rx="1"
            :fill="train.emergency_brake ? '#dc2626' : color(train.vehicle_id)"
            :stroke="train.vehicle_id === selectedId ? '#fff' : '#0f172a'"
            stroke-width="train.vehicle_id === selectedId ? 1.2 : 0.8"
          />
          <rect
            x="7" y="-2"
            width="3" height="4" rx="0.5"
            fill="rgba(255,255,255,0.5)"
          />
          <title>{{ train.vehicle_id }} · {{ Math.round(train.speed) }} km/h · {{ Math.round(train.position) }} m</title>
        </g>
      </svg>

      <!-- 缩放提示 -->
      <div class="absolute bottom-2 right-2 text-[10px] text-gray-600 pointer-events-none">
        ×{{ zoom.toFixed(1) }}
      </div>
    </div>

    <div v-if="!compact" class="flex flex-wrap gap-x-4 gap-y-2 mt-3 text-[11px] text-gray-500">
      <span class="flex items-center gap-1"><span class="w-4 h-1 bg-sky-400 rounded" /> 空闲区段</span>
      <span class="flex items-center gap-1"><span class="w-4 h-1 bg-amber-500 rounded" /> 临近占用</span>
      <span class="flex items-center gap-1"><span class="w-4 h-1 bg-rose-400 rounded" /> 已占用</span>
      <span class="flex items-center gap-1"><span class="w-2 h-3 rounded-sm bg-gray-700 border border-gray-500" /> 信号机灯色 = 通行许可</span>
      <span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm bg-sky-500" /> 列车</span>
      <span
        v-for="v in vehicles"
        :key="`lg-${v.vehicle_id}`"
        class="flex items-center gap-1 cursor-pointer hover:text-gray-300"
        data-pan-ignore="true"
        @click="$emit('select', v.vehicle_id)"
      >
        <span class="w-2 h-2 rounded-sm" :style="{ backgroundColor: color(v.vehicle_id) }" />
        {{ v.vehicle_id }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, toRef } from 'vue'
import { useSvgPanZoom } from '@/composables/useSvgPanZoom'
import { useTrainInterpolation } from '@/composables/useTrainInterpolation'
import { lerpAngle } from '@/utils/interpolate'
import {
  findCandidateBlocksForVehicle,
  locateTrainOnGraph,
  buildMaPathOnGraph,
  buildMaPathSegIds,
  locateSignalOnGraph,
  signalTypeLabel,
  edgeAspect,
  edgeStroke,
  edgeBedStroke,
  spreadTrainMarkers,
} from '@/utils/trainGraphPosition'

const props = defineProps({
  graph: { type: Object, default: null },
  blocks: { type: Array, default: () => [] },
  segments: { type: Array, default: () => [] },
  stations: { type: Array, default: () => [] },
  turnouts: { type: Array, default: () => [] },
  signals: { type: Array, default: () => [] },
  vehicles: { type: Array, default: () => [] },
  selectedId: { type: String, default: null },
  color: { type: Function, required: true },
  lineLabel: { type: String, default: '线路' },
  compact: { type: Boolean, default: false },
  totalLength: { type: Number, default: null },
  motionPaused: { type: Boolean, default: false },
})

defineEmits(['select'])

const followTrain = ref(false)
const trainMarkers = ref([])
const prevMarkerStates = new Map()

const { displayVehicles } = useTrainInterpolation(toRef(props, 'vehicles'), {
  totalLength: toRef(props, 'totalLength'),
  paused: toRef(props, 'motionPaused'),
})

const bounds = computed(() => {
  const edges = props.graph?.edges ?? []
  const connectors = props.graph?.connectors ?? []
  if (!edges.length && !connectors.length) return { minX: 0, maxX: 800, minY: 200, maxY: 320 }
  const xs = [...edges, ...connectors].flatMap((item) => edgePoints(item).map((point) => point[0]))
  const ys = [...edges, ...connectors].flatMap((item) => edgePoints(item).map((point) => point[1]))
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minY: Math.min(...ys),
    maxY: Math.max(...ys),
  }
})

function getBaseViewBox() {
  const b = bounds.value
  const padX = 50
  const padY = 40
  return {
    x: b.minX - padX,
    y: b.minY - padY,
    width: b.maxX - b.minX + padX * 2,
    height: b.maxY - b.minY + padY * 2,
  }
}

const panZoom = useSvgPanZoom(getBaseViewBox)
const { viewBoxString, zoom, dragging, reset, smoothPanToWorld, onWheel, onPointerDown } = panZoom

function refreshTrainMarkers() {
  const edges = props.graph?.edges ?? []
  const activeIds = new Set(displayVehicles.value.map((vehicle) => vehicle.vehicle_id))
  for (const id of [...prevMarkerStates.keys()]) {
    if (!activeIds.has(id)) prevMarkerStates.delete(id)
  }

  const raw = displayVehicles.value
    .map((v) => {
      const prev = prevMarkerStates.get(v.vehicle_id) ?? null
      const pos = locateTrainOnGraph(v, props.blocks, edges, {
        preferredSegId: prev?.seg_id ?? null,
        prevPoint: prev ? { x: prev.x, y: prev.y } : null,
      })
      if (!pos) return null
      const angle = resolveTrainAngle(pos, prev)
      const marker = { ...v, ...pos, angle }
      prevMarkerStates.set(v.vehicle_id, {
        x: pos.x,
        y: pos.y,
        angle,
        seg_id: pos.seg_id,
      })
      return marker
    })
    .filter(Boolean)
  trainMarkers.value = spreadTrainMarkers(raw)
}

watch(displayVehicles, refreshTrainMarkers, { immediate: true })
watch(() => props.graph?.edges, refreshTrainMarkers)
watch(() => props.blocks, refreshTrainMarkers, { deep: true })

const followedTrainMarker = computed(() =>
  trainMarkers.value.find((marker) => marker.vehicle_id === props.selectedId) ?? null
)

watch(
  [followedTrainMarker, followTrain, dragging],
  ([marker, shouldFollow, isDragging]) => {
    if (!marker || !shouldFollow || isDragging) return
    smoothPanToWorld(marker.x + (marker.offsetX ?? 0), marker.y + (marker.offsetY ?? 0), 0.12)
  },
  { immediate: true },
)

const gridLines = computed(() => {
  const b = bounds.value
  const step = 80
  const x = []
  const y = []
  for (let i = Math.floor(b.minX / step) * step; i <= b.maxX; i += step) x.push(i)
  for (let j = Math.floor(b.minY / step) * step; j <= b.maxY; j += step) y.push(j)
  return { x, y }
})

const visibleStations = computed(() =>
  props.stations.filter((s) => s.graph_x != null)
)

const visibleTurnouts = computed(() => {
  const list = props.turnouts.filter((t) => t.graph_x != null)
  if (list.length <= 25) return list
  const step = Math.ceil(list.length / 25)
  return list.filter((_, i) => i % step === 0)
})

const visibleSignals = computed(() => {
  const edges = props.graph?.edges ?? []
  const placed = []
  const seen = new Set()

  for (const s of props.signals) {
    const pos = locateSignalOnGraph(s, props.blocks, edges)
    if (!pos) continue
    const key = `${Math.round(pos.track_x / 8)}-${Math.round(pos.track_y / 8)}-${s.state}`
    if (seen.has(key)) continue
    seen.add(key)
    placed.push(pos)
  }

  if (placed.length <= 45) return placed
  const step = Math.ceil(placed.length / 45)
  return placed.filter((_, i) => i % step === 0)
})

const selectedTrain = computed(() =>
  displayVehicles.value.find((v) => v.vehicle_id === props.selectedId)
    ?? props.vehicles.find((v) => v.vehicle_id === props.selectedId)
)

const selectedMarker = computed(() =>
  trainMarkers.value.find((marker) => marker.vehicle_id === props.selectedId) ?? null
)

const selectedMaPath = computed(() => {
  const train = selectedTrain.value
  if (!train?.ma_limit) return []
  return buildMaPathOnGraph(
    train.position,
    train.ma_limit,
    props.blocks,
    props.graph?.edges ?? [],
  )
})

const selectedMaSegIds = computed(() => {
  const train = selectedTrain.value
  if (!train?.ma_limit) return new Set()
  return buildMaPathSegIds(train.position, train.ma_limit, props.blocks)
})

function edgeColor(segId) {
  return edgeAspect(segId, props.segments, props.blocks)
}

function edgePoints(item) {
  if (Array.isArray(item?.points) && item.points.length >= 2) return item.points
  return [
    [item?.x1 ?? 0, item?.y1 ?? 0],
    [item?.x2 ?? 0, item?.y2 ?? 0],
  ]
}

function pathPoints(item) {
  return edgePoints(item).map((point) => `${point[0]},${point[1]}`).join(' ')
}

function connectorColor(connector) {
  const from = edgeColor(connector.from_seg_id)
  const to = edgeColor(connector.to_seg_id)
  if (from === 'red' || to === 'red') return 'red'
  if (from === 'yellow' || to === 'yellow') return 'yellow'
  return 'green'
}

function trainTransform(train) {
  const x = train.x + (train.offsetX ?? 0)
  const y = train.y + (train.offsetY ?? 0)
  return `translate(${x}, ${y}) rotate(${train.angle})`
}

function speedTrailLen(speed) {
  return Math.min(22, 8 + speed * 0.18)
}

function diamond(x, y, r) {
  return `${x},${y - r} ${x + r},${y} ${x},${y + r} ${x - r},${y}`
}

function resolveTrainAngle(positionOnGraph, prev) {
  const rawAngle = positionOnGraph.angle ?? 0
  if (!prev) return rawAngle

  const dx = positionOnGraph.x - prev.x
  const dy = positionOnGraph.y - prev.y
  const motionDistance = Math.hypot(dx, dy)
  const referenceAngle = motionDistance >= 0.6
    ? (Math.atan2(dy, dx) * 180) / Math.PI
    : prev.angle

  const alignedAngle = alignAngleVariant(rawAngle, referenceAngle)
  return lerpAngle(prev.angle, alignedAngle, 0.38)
}

function alignAngleVariant(rawAngle, referenceAngle) {
  const candidateA = rawAngle
  const candidateB = rawAngle + 180
  const deltaA = angleDelta(referenceAngle, candidateA)
  const deltaB = angleDelta(referenceAngle, candidateB)
  return Math.abs(deltaA) <= Math.abs(deltaB) ? candidateA : candidateB
}

function angleDelta(fromDeg, toDeg) {
  let delta = ((toDeg - fromDeg + 180) % 360) - 180
  if (delta < -180) delta += 360
  return delta
}

const selectedPermissionText = computed(() => {
  const train = selectedTrain.value
  if (!train) return ''
  if (train.permission === 'stop' || train.signal_state === 'red') return `${train.vehicle_id} · 前方许可：红灯停车`
  if (train.permission === 'restricted' || train.signal_state === 'yellow') return `${train.vehicle_id} · 前方许可：黄灯限速`
  if (train.permission === 'allow' || train.signal_state === 'green') return `${train.vehicle_id} · 前方许可：绿灯允许`
  return `${train.vehicle_id} · 前方许可：待确认`
})

const selectedPermissionChipClass = computed(() => {
  const train = selectedTrain.value
  if (!train) return 'border-slate-700 text-slate-300'
  if (train.permission === 'stop' || train.signal_state === 'red') return 'border-red-500/50 bg-red-950 text-red-200'
  if (train.permission === 'restricted' || train.signal_state === 'yellow') return 'border-amber-500/50 bg-amber-950 text-amber-200'
  if (train.permission === 'allow' || train.signal_state === 'green') return 'border-emerald-500/40 bg-emerald-950 text-emerald-200'
  return 'border-slate-700 text-slate-300'
})

const selectedMappingText = computed(() => {
  const train = selectedTrain.value
  if (!train) return ''

  const candidates = findCandidateBlocksForVehicle(train, props.blocks)
  const segId = selectedMarker.value?.seg_id ?? '—'
  const sectionId = selectedMarker.value?.block?.section_id ?? selectedMarker.value?.block?.segment_id ?? '—'
  return candidates.length > 1
    ? `图上挂载 seg ${segId} · 区段 ${sectionId} · 重叠候选 ${candidates.length}`
    : `图上挂载 seg ${segId} · 区段 ${sectionId}`
})
</script>

<style scoped>
.train-marker {
  will-change: transform;
}
</style>
