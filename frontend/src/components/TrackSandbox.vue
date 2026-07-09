<!-- 全线动态沙盘：按真实里程比例渲染，支持长线路横向滚动 -->
<template>
  <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-gray-300 tracking-wide">全局调度沙盘</h3>
      <span class="text-xs text-gray-500">
        全长 {{ formatKm(totalLength) }} · {{ segments.length }} 逻辑区段 · {{ vehicles.length }} 列
        <span v-if="layoutLoaded" class="text-sky-500/80 ml-1">· 老师线路数据</span>
      </span>
    </div>

    <div class="overflow-x-auto pb-2">
      <div class="relative mb-14 pt-8" :style="{ minWidth: `${trackPx}px` }">
        <!-- MA 授权区 -->
        <div class="absolute top-0 left-0 h-5" :style="{ width: `${trackPx}px` }">
          <template v-for="train in vehiclesWithMa" :key="`ma-${train.vehicle_id}`">
            <template v-if="train.vehicle_id === selectedId">
              <div class="absolute top-0 h-full rounded-sm" :style="maZoneStyle(train)" />
              <div class="absolute top-0 h-full w-0.5" :style="maEndLineStyle(train)" />
            </template>
          </template>
        </div>

        <!-- 站台 -->
        <div
          v-for="st in stations"
          :key="st.station_id"
          class="absolute top-6 flex flex-col items-center z-[1]"
          :style="{ left: `${px(st.position)}px`, transform: 'translateX(-50%)' }"
        >
          <div class="w-px h-14 bg-sky-600/40" />
          <span class="text-[9px] text-sky-400/90 mt-0.5 whitespace-nowrap bg-gray-950/90 px-1 rounded">
            {{ st.name }}
          </span>
        </div>

        <!-- 逻辑区段（等比例宽度） -->
        <div
          class="relative h-14 rounded-xl overflow-hidden border border-gray-700 z-[2]"
          :style="{ width: `${trackPx}px` }"
        >
          <div
            v-for="seg in visibleSegments"
            :key="seg.segment_id"
            class="absolute top-0 h-full border-r border-gray-900/50 transition-colors duration-300"
            :class="segmentClass(seg)"
            :style="segmentStyle(seg)"
            :title="segmentTitle(seg)"
          />

          <!-- 列车 -->
          <button
            v-for="(train, idx) in displayVehicles"
            :key="train.vehicle_id"
            type="button"
            class="absolute flex flex-col items-center z-10 cursor-pointer focus:outline-none train-sandbox-marker"
            :style="trainStyle(train, idx)"
            @click="$emit('select', train.vehicle_id)"
          >
            <div
              class="w-9 h-5 rounded flex items-center justify-center text-[9px] font-bold text-white shadow-lg"
              :class="[
                train.emergency_brake ? 'bg-red-600 animate-pulse' : '',
                train.vehicle_id === selectedId ? 'ring-2 ring-white scale-110' : 'hover:scale-105',
              ]"
              :style="{ backgroundColor: train.emergency_brake ? undefined : color(train.vehicle_id) }"
            >{{ shortId(train.vehicle_id) }}</div>
          </button>
        </div>

        <!-- 道岔（抽样显示，避免过密） -->
        <div class="absolute left-0 h-7 z-[2]" :style="{ width: `${trackPx}px`, top: 'calc(100% - 2.5rem)' }">
          <div
            v-for="t in sampledTurnouts"
            :key="t.turnout_id"
            class="absolute flex flex-col items-center"
            :style="{ left: `${px(t.position)}px`, transform: 'translateX(-50%)' }"
            :title="`${t.turnout_id} @ ${t.position}m`"
          >
            <div class="w-4 h-4 rounded-sm border text-[7px] flex items-center justify-center font-bold" :class="turnoutClass(t)">
              {{ t.state === 'reverse' ? '反' : '定' }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <p v-if="segments.length > maxSegments" class="text-[10px] text-gray-600 mb-2">
      沙盘展示 {{ visibleSegments.length }}/{{ segments.length }} 个区段（等间隔抽样，表格中可查看全部）
    </p>

    <div class="flex flex-wrap gap-x-4 gap-y-2 text-xs text-gray-500">
      <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-emerald-900/60 border border-emerald-600" /> 空闲</span>
      <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-yellow-900/50 border border-yellow-600" /> 接近</span>
      <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-red-900/70 border border-red-600" /> 占用</span>
      <span v-for="train in vehicles" :key="`lg-${train.vehicle_id}`" class="flex items-center gap-1.5">
        <span class="w-3 h-3 rounded" :style="{ backgroundColor: color(train.vehicle_id) }" />{{ train.vehicle_id }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, toRef } from 'vue'
import { useTrainInterpolation } from '@/composables/useTrainInterpolation'

const props = defineProps({
  segments: { type: Array, default: () => [] },
  vehicles: { type: Array, default: () => [] },
  signals: { type: Array, default: () => [] },
  turnouts: { type: Array, default: () => [] },
  stations: { type: Array, default: () => [] },
  selectedId: { type: String, default: null },
  totalLength: { type: Number, default: 5000 },
  layoutLoaded: { type: Boolean, default: false },
  color: { type: Function, required: true },
  maxSegments: { type: Number, default: 120 },
  motionPaused: { type: Boolean, default: false },
})

defineEmits(['select'])

const { displayVehicles } = useTrainInterpolation(toRef(props, 'vehicles'), {
  totalLength: toRef(props, 'totalLength'),
  paused: toRef(props, 'motionPaused'),
})

const PX_PER_KM = 28
const trackPx = computed(() => Math.max(900, (props.totalLength / 1000) * PX_PER_KM * 10))

const vehiclesWithMa = computed(() =>
  displayVehicles.value.filter((v) => v.ma_limit != null && !Number.isNaN(v.ma_limit))
)

const visibleSegments = computed(() => {
  if (props.segments.length <= props.maxSegments) return props.segments
  const step = Math.ceil(props.segments.length / props.maxSegments)
  return props.segments.filter((_, i) => i % step === 0)
})

const sampledTurnouts = computed(() => {
  if (props.turnouts.length <= 30) return props.turnouts
  const step = Math.ceil(props.turnouts.length / 30)
  return props.turnouts.filter((_, i) => i % step === 0)
})

function px(position) {
  return (position / props.totalLength) * trackPx.value
}

function formatKm(m) {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`
}

function shortId(id) {
  return id.length > 4 ? id.slice(-3) : id
}

function segmentStyle(seg) {
  return {
    left: `${px(seg.start)}px`,
    width: `${Math.max(1, px(seg.end) - px(seg.start))}px`,
  }
}

function segmentClass(seg) {
  const aspect = seg.aspect ?? (seg.occupied ? 'red' : 'green')
  if (aspect === 'red' || seg.occupied) return 'bg-red-900/70'
  if (aspect === 'yellow') return 'bg-yellow-900/50'
  return 'bg-emerald-900/35'
}

function segmentTitle(seg) {
  const aspect = seg.aspect ?? (seg.occupied ? 'red' : 'green')
  const labels = { green: '空闲', yellow: '接近', red: '占用' }
  return `${seg.segment_id}: ${seg.start}–${seg.end}m · ${labels[aspect] ?? aspect}`
}

function trainStyle(train, index) {
  return {
    left: `${px(train.position)}px`,
    top: `${-6 - (index % 3) * 20}px`,
    transform: 'translateX(-50%)',
  }
}

function maZoneStyle(train) {
  const c = props.color(train.vehicle_id)
  return {
    left: `${px(Math.min(train.position, train.ma_limit))}px`,
    width: `${Math.max(2, px(train.ma_limit) - px(train.position))}px`,
    backgroundColor: `${c}22`,
    borderBottom: `2px dashed ${c}88`,
  }
}

function maEndLineStyle(train) {
  const c = props.color(train.vehicle_id)
  return { left: `${px(train.ma_limit)}px`, backgroundColor: c }
}

function turnoutClass(t) {
  if (t.locked) return 'border-amber-500 bg-amber-950/50 text-amber-300'
  if (t.state === 'reverse') return 'border-purple-500 bg-purple-950/40 text-purple-300'
  return 'border-gray-600 bg-gray-800 text-gray-400'
}
</script>

<style scoped>
.train-sandbox-marker {
  will-change: left, top;
}
</style>
