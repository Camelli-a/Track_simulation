<!-- 北京地铁9号线 · 竖向线路示意图 -->
<template>
  <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <div>
        <h3 class="text-sm font-semibold text-gray-200">北京地铁 9 号线</h3>
        <p class="text-xs text-gray-500 mt-0.5">
          郭公庄 ↓ 国家图书馆 · {{ sortedStations.length }} 站 · {{ formatKm(totalLength) }}
        </p>
      </div>
      <div class="flex items-center gap-3 text-xs text-gray-500">
        <span>{{ vehicles.length }} 列在线</span>
      </div>
    </div>

    <div
      class="rounded-xl border border-gray-800 bg-gradient-to-b from-gray-950 to-gray-900/80 overflow-y-auto max-h-[520px]"
    >
      <div class="flex gap-3 py-3 pl-3 pr-4" :style="{ minHeight: `${chartHeight}px` }">
        <!-- 轨道 + 列车（HTML 标签标注车号，避免误读） -->
        <div
          class="relative shrink-0"
          :style="{ width: `${TRACK_COL_W}px`, height: `${chartHeight}px` }"
        >
          <svg :width="TRACK_COL_W" :height="chartHeight" class="block">
            <defs>
              <linearGradient id="l9-track-v" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stop-color="#065f46" />
                <stop offset="50%" stop-color="#10b981" />
                <stop offset="100%" stop-color="#059669" />
              </linearGradient>
            </defs>

            <rect
              :x="TRACK_X - 10" :y="contentTop - 2"
              width="20" :height="drawH"
              rx="10" fill="#0f172a" stroke="#1e293b" stroke-width="1"
            />

            <rect
              v-for="seg in visibleSegments"
              :key="seg.segment_id"
              :x="TRACK_X - 7"
              :y="segY(seg.start)"
              width="14"
              :height="Math.max(1, segY(seg.end) - segY(seg.start))"
              :fill="aspectFill(seg)" opacity="0.65" rx="1"
            />

            <line
              :x1="TRACK_X" :y1="contentTop"
              :x2="TRACK_X" :y2="contentTop + drawH"
              stroke="url(#l9-track-v)" stroke-width="3" stroke-linecap="round"
            />

            <g v-if="selectedTrain?.ma_limit != null">
              <rect
                :x="TRACK_X - 7" :y="segY(selectedTrain.position)"
                width="14"
                :height="Math.max(2, segY(selectedTrain.ma_limit) - segY(selectedTrain.position))"
                :fill="`${color(selectedTrain.vehicle_id)}44`" rx="2"
              />
              <line
                :x1="TRACK_X - 20" :x2="TRACK_X + 20"
                :y1="segY(selectedTrain.ma_limit)" :y2="segY(selectedTrain.ma_limit)"
                :stroke="color(selectedTrain.vehicle_id)"
                stroke-width="1" stroke-dasharray="2 2" opacity="0.7"
              />
            </g>

            <!-- 车站圆点 -->
            <circle
              v-for="(st, idx) in sortedStations"
              :key="`dot-${st.station_id}`"
              :cx="TRACK_X" :cy="stationY(idx)"
              r="4.5" fill="#0f172a" stroke="#6ee7b7" stroke-width="1.5"
            />

            <!-- 列车：画在轨道中心，小方块像车厢 -->
            <g
              v-for="train in trainMarkers"
              :key="train.vehicle_id"
              class="cursor-pointer train-schematic-marker"
              @click="$emit('select', train.vehicle_id)"
            >
              <rect
                :x="TRACK_X - 7" :y="train.y - 5"
                width="14" height="10" rx="2"
                :fill="train.emergency_brake ? '#dc2626' : color(train.vehicle_id)"
                :stroke="train.vehicle_id === selectedId ? '#fff' : '#0f172a'"
                stroke-width="train.vehicle_id === selectedId ? 1.5 : 1"
              />
              <title>{{ train.vehicle_id }} · {{ train.speed }} km/h · {{ Math.round(train.position) }} m</title>
            </g>
          </svg>

          <!-- 车号标签（HTML，固定字号） -->
          <button
            v-for="train in trainMarkers"
            :key="`lbl-${train.vehicle_id}`"
            type="button"
            class="absolute left-0 flex items-center gap-1 -translate-y-1/2 pointer-events-auto"
            :style="{ top: `${train.y}px` }"
            @click="$emit('select', train.vehicle_id)"
          >
            <span
              class="text-[10px] font-bold px-1 py-px rounded leading-none whitespace-nowrap"
              :class="train.vehicle_id === selectedId ? 'ring-1 ring-white' : ''"
              :style="{ backgroundColor: color(train.vehicle_id), color: '#fff' }"
            >{{ train.vehicle_id }}</span>
          </button>
        </div>

        <!-- 站名 -->
        <div class="flex-1 flex flex-col min-w-0" :style="{ height: `${chartHeight}px` }">
          <p class="text-[10px] text-gray-600 mb-1 shrink-0">郭公庄 ↑</p>
          <div class="flex-1 flex flex-col justify-between">
            <div
              v-for="(st, idx) in sortedStations"
              :key="st.station_id"
              class="flex items-center gap-2 min-h-0 leading-tight"
              :style="{ height: `${rowSlotH}px` }"
            >
              <button
                type="button"
                class="rounded-full border px-2 py-0.5 text-left text-xs font-medium transition-colors"
                :class="st.station_id === selectedStationId
                  ? 'border-cyan-400/60 bg-cyan-400/10 text-cyan-100'
                  : 'border-transparent text-emerald-200/90 hover:border-white/10 hover:bg-white/5'"
                @click="$emit('select-station', st.station_id)"
              >
                {{ stationLabel(st.name) }}
              </button>
              <span class="text-[10px] text-gray-500 shrink-0">{{ st.name }}</span>
            </div>
          </div>
          <p class="text-[10px] text-gray-600 mt-1 shrink-0">国家图书馆 ↓</p>
        </div>
      </div>
    </div>

    <!-- 图例：明确说明列车标记含义 -->
    <div class="flex flex-wrap gap-x-4 gap-y-1.5 mt-3 text-[11px] text-gray-500">
      <span class="flex items-center gap-1.5 text-gray-400">
        <span class="inline-block w-3.5 h-2.5 rounded-sm bg-sky-500" />
        彩色块 = 在线列车（点击选中）
      </span>
      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full border border-emerald-400" /> 车站</span>
      <span class="text-gray-400">点击站名可展开站场视图</span>
      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-emerald-400" /> 空闲区段</span>
      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-red-500" /> 占用</span>
      <span
        v-for="v in vehicles"
        :key="`lg-${v.vehicle_id}`"
        class="flex items-center gap-1 cursor-pointer hover:text-gray-300"
        @click="$emit('select', v.vehicle_id)"
      >
        <span class="w-2 h-2 rounded-sm" :style="{ backgroundColor: color(v.vehicle_id) }" />
        {{ v.vehicle_id }} · {{ v.speed }} km/h · {{ Math.round(v.position) }} m
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, toRef } from 'vue'
import { useTrainInterpolation } from '@/composables/useTrainInterpolation'
import { positionToY, stationLabel, aspectColor } from '@/utils/lineSchematic'

const props = defineProps({
  stations: { type: Array, default: () => [] },
  segments: { type: Array, default: () => [] },
  vehicles: { type: Array, default: () => [] },
  totalLength: { type: Number, default: 47500 },
  selectedId: { type: String, default: null },
  selectedStationId: { type: String, default: null },
  color: { type: Function, required: true },
  motionPaused: { type: Boolean, default: false },
})

defineEmits(['select', 'select-station'])

const { displayVehicles } = useTrainInterpolation(toRef(props, 'vehicles'), {
  totalLength: toRef(props, 'totalLength'),
  paused: toRef(props, 'motionPaused'),
})

const TRACK_COL_W = 72
const TRACK_X = 36
const contentTop = 20
const ROW_SLOT = 34

const sortedStations = computed(() =>
  [...props.stations].sort((a, b) => a.position - b.position)
)

const rowSlotH = computed(() => ROW_SLOT)

const chartHeight = computed(() => {
  const n = sortedStations.value.length
  return Math.max(360, (n - 1) * ROW_SLOT + contentTop * 2 + 40)
})

const drawH = computed(() => chartHeight.value - contentTop * 2 - 40)

const selectedTrain = computed(() =>
  displayVehicles.value.find((v) => v.vehicle_id === props.selectedId) ?? null
)

/** 列车 Y 坐标 + 重叠时错开（插值后平滑移动） */
const trainMarkers = computed(() => {
  const sorted = [...displayVehicles.value].sort((a, b) => a.position - b.position)
  const placed = []
  const minGap = 16

  for (const v of sorted) {
    let y = segY(v.position)
    for (const p of placed) {
      if (Math.abs(p.y - y) < minGap) y = p.y + minGap
    }
    placed.push({ ...v, y })
  }
  return placed
})

const visibleSegments = computed(() => {
  const segs = props.segments
  if (segs.length <= 50) return segs
  const step = Math.ceil(segs.length / 50)
  return segs.filter((_, i) => i % step === 0)
})

function stationY(index) {
  const n = sortedStations.value.length
  if (n <= 1) return contentTop + drawH.value / 2
  return contentTop + (index / (n - 1)) * drawH.value
}

function segY(position) {
  return contentTop + positionToY(position, props.totalLength, 0, drawH.value)
}

function aspectFill(seg) {
  const aspect = seg.aspect ?? (seg.occupied ? 'red' : 'green')
  return aspectColor(aspect)
}

function formatKm(m) {
  return `${(m / 1000).toFixed(1)} km`
}
</script>

<style scoped>
.train-schematic-marker {
  will-change: transform;
}
</style>
