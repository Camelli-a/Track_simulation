<template>
  <div class="space-y-5">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-xl font-semibold">信号系统</h2>
        <p class="text-sm text-gray-500 mt-1">
          闭塞联锁 · 移动授权 MA · 道岔控制（F1.2 / F1.3）
        </p>
      </div>
      <ConnectionBadge :connected="store.connected" :data-stale="store.dataStale" />
    </header>

    <PageEmptyState
      v-if="!store.trackSegments.length && !store.signals.length && !store.turnouts.length"
      title="等待联锁与信号数据接入"
      description="当前还没有收到区段、信号机和道岔快照，因此无法进行联锁冲突检查、MA 展示和闭塞状态联动分析。"
      next-step="请确认后端正在推送 sections、signals 和 switches 字段，或先返回 OCC 大屏查看实时链路是否已经收到首帧数据。"
    />

    <template v-else>
    <div class="grid grid-cols-2 lg:grid-cols-5 gap-4">
      <StatusCard label="系统模式" :value="store.systemMode" />
      <StatusCard label="闭塞分区" :value="store.trackSegments.length" unit="个" />
      <StatusCard label="信号机" :value="store.signals.length" unit="架" />
      <StatusCard label="道岔" :value="store.turnouts.length" unit="组" />
      <StatusCard
        label="联锁冲突"
        :value="interlockingConflicts.length"
        unit="项"
      />
    </div>

    <SelectedVehicleSummary
      :vehicle="store.selectedVehicle"
      :color="store.vehicleColor"
      :insight="selectedVehicleInsight"
      description="当前关注列车会和调度沙盘、事件时间线保持联动，便于核对它的 MA、速度约束和紧急制动状态。"
    />

    <!-- 闭塞分区条 -->
    <div class="app-panel">
      <h3 class="text-sm font-semibold text-gray-300 mb-3">闭塞分区联锁状态</h3>
      <SegmentStatusBar :segments="store.trackSegments" />
    </div>

    <div class="app-panel">
      <div class="app-section-head">
        <div>
          <p class="app-section-kicker">Conflict Watch</p>
          <h3 class="app-section-title">联锁冲突检查</h3>
          <p class="app-section-copy">直接列出当前不满足联锁约束的道岔、区段和邻近信号组合，便于快速定位。</p>
        </div>
        <span
          class="text-xs px-2 py-0.5 rounded-full"
          :class="interlockingConflicts.length
            ? 'bg-amber-950 text-amber-300'
            : 'bg-emerald-950 text-emerald-300'"
        >
          {{ interlockingConflicts.length ? `${interlockingConflicts.length} 项待核查` : '未发现显著冲突' }}
        </span>
      </div>

      <div v-if="interlockingConflicts.length" class="mt-5 space-y-3">
        <div
          v-for="conflict in interlockingConflicts"
          :key="conflict.id"
          class="rounded-xl border px-4 py-4"
          :class="conflict.level === 'high'
            ? 'border-red-900/60 bg-red-950/20'
            : 'border-amber-900/60 bg-amber-950/20'"
        >
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="flex flex-wrap items-center gap-2">
              <span
                class="text-[11px] px-2 py-0.5 rounded-full"
                :class="conflict.level === 'high'
                  ? 'bg-red-950 text-red-300'
                  : 'bg-amber-950 text-amber-300'"
              >
                {{ conflict.level === 'high' ? '高优先级' : '关注' }}
              </span>
              <span class="text-sm font-medium text-gray-100">{{ conflict.title }}</span>
            </div>
            <span class="text-xs text-gray-500">{{ conflict.kind }}</span>
          </div>

          <div class="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div class="app-metric-tile">
              <p class="app-metric-label">道岔</p>
              <p class="mt-1 text-gray-200">{{ conflict.turnoutLabel }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">区段</p>
              <p class="mt-1 text-gray-200">{{ conflict.segmentLabel }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">信号</p>
              <p class="mt-1 text-gray-200">{{ conflict.signalLabel }}</p>
            </div>
          </div>

          <p class="mt-3 text-sm leading-6 text-gray-300">{{ conflict.detail }}</p>
        </div>
      </div>

      <div
        v-else
        class="mt-4 rounded-xl border border-dashed border-gray-800 bg-gray-950/40 px-4 py-8 text-center"
      >
        <p class="text-sm text-gray-300">当前未发现明显联锁冲突</p>
        <p class="mt-2 text-xs leading-5 text-gray-500">
          系统仍会持续检查“区段占用但信号开放”“关键道岔解锁时邻近区段占用”“反位道岔涉及冲突分支占用”等条件。
        </p>
      </div>
    </div>

    <!-- 信号机 -->
    <div class="app-panel">
      <h3 class="text-sm font-semibold text-gray-300 mb-4">沿线信号机</h3>
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <div
          v-for="light in store.signals"
          :key="light.signal_id"
          class="rounded-xl bg-gray-950 border border-gray-800 p-3 flex flex-col items-center gap-2"
        >
          <div class="flex flex-col items-center gap-1 py-1 px-2 rounded-lg bg-gray-900">
            <span class="w-3 h-3 rounded-full" :class="light.state === 'red' ? 'bg-red-500 shadow-[0_0_6px_#ef4444]' : 'bg-red-900/30'" />
            <span class="w-3 h-3 rounded-full" :class="light.state === 'yellow' ? 'bg-yellow-400 shadow-[0_0_6px_#facc15]' : 'bg-yellow-900/20'" />
            <span class="w-3 h-3 rounded-full" :class="light.state === 'green' ? 'bg-green-500 shadow-[0_0_6px_#22c55e]' : 'bg-green-900/20'" />
          </div>
          <span class="text-xs text-gray-300">{{ light.signal_id }}</span>
          <span class="text-[10px] text-gray-500">{{ light.position }} m</span>
        </div>
      </div>
    </div>

    <!-- 道岔 -->
    <div class="app-panel">
      <h3 class="text-sm font-semibold text-gray-300 mb-4">道岔锁闭状态</h3>
      <div class="app-table-shell">
        <table class="app-table">
          <thead>
            <tr>
              <th class="text-left">道岔</th>
              <th class="text-right">位置</th>
              <th class="text-right">状态</th>
              <th class="text-right">锁闭</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="t in store.turnouts"
              :key="t.turnout_id"
            >
              <td class="text-gray-300">{{ t.turnout_id }}</td>
              <td class="text-right text-gray-400">{{ t.position }} m</td>
              <td class="text-right">
                <span :class="isReverseState(t.state) ? 'text-purple-400' : 'text-gray-300'">
                  {{ isReverseState(t.state) ? '反位' : '定位' }}
                </span>
              </td>
              <td class="text-right">
                <span :class="t.locked ? 'text-amber-400' : 'text-gray-500'">
                  {{ t.locked ? '锁闭' : '解锁' }}
                </span>
              </td>
            </tr>
            <tr v-if="!store.turnouts.length">
              <td colspan="4" class="py-8 text-center text-gray-600">暂无道岔数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- MA 移动授权 -->
    <div class="app-panel">
      <h3 class="text-sm font-semibold text-gray-300 mb-4">各车移动授权（MA）</h3>
      <div class="app-table-shell">
        <table class="app-table">
          <thead>
            <tr>
              <th class="text-left">车辆</th>
              <th class="text-right">当前位置</th>
              <th class="text-right">MA 终点</th>
              <th class="text-right">授权长度</th>
              <th class="text-right">剩余距离</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="v in store.vehicles"
              :key="v.vehicle_id"
            >
              <td>
                <span class="inline-flex items-center gap-2">
                  <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: store.vehicleColor(v.vehicle_id) }" />
                  {{ v.vehicle_id }}
                </span>
              </td>
              <td class="text-right text-gray-400">{{ v.position }} m</td>
              <td class="text-right text-gray-300">{{ v.ma_limit ?? '—' }} m</td>
              <td class="text-right text-sky-400">
                {{ maLength(v) }}
              </td>
              <td class="text-right text-gray-400">
                {{ v.ma_limit != null ? (v.ma_limit - v.position).toFixed(1) + ' m' : '—' }}
              </td>
            </tr>
            <tr v-if="!store.vehicles.length">
              <td colspan="5" class="py-8 text-center text-gray-600">暂无列车 MA 数据</td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- MA 可视化条 -->
      <div class="mt-4 space-y-2">
        <div v-for="v in store.vehicles" :key="`ma-bar-${v.vehicle_id}`" class="flex items-center gap-3">
          <span class="text-xs text-gray-500 w-10 shrink-0">{{ v.vehicle_id }}</span>
          <div class="flex-1 h-2 rounded-full bg-gray-800 relative overflow-hidden">
            <div
              class="absolute h-full rounded-full opacity-60"
              :style="maBarStyle(v)"
            />
            <div
              class="absolute w-1.5 h-full bg-white rounded-full -translate-x-1/2"
              :style="{ left: `${(v.position / store.totalLength) * 100}%` }"
            />
          </div>
        </div>
      </div>
    </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { usePageSimulation } from '@/composables/usePageSimulation'
import PageEmptyState from '@/components/PageEmptyState.vue'
import StatusCard from '@/components/StatusCard.vue'
import SegmentStatusBar from '@/components/SegmentStatusBar.vue'
import ConnectionBadge from '@/components/ConnectionBadge.vue'
import SelectedVehicleSummary from '@/components/SelectedVehicleSummary.vue'

const store = usePageSimulation()

const selectedVehicleInsight = computed(() => {
  const vehicle = store.selectedVehicle
  if (!vehicle) return ''

  const remaining = vehicle.ma_limit != null ? vehicle.ma_limit - vehicle.position : null
  if (vehicle.emergency_brake) {
    return `${vehicle.vehicle_id} 当前处于紧急制动状态，请优先核对前方区段占用和 MA 是否发生收缩。`
  }
  if (remaining != null && remaining < 120) {
    return `${vehicle.vehicle_id} 距离 MA 边界仅剩 ${remaining.toFixed(1)} m，建议重点关注前方信号显示与闭塞占用。`
  }
  if (vehicle.target_speed != null && vehicle.speed > vehicle.target_speed + 2) {
    return `${vehicle.vehicle_id} 当前速度 ${vehicle.speed} km/h，高于目标 ${vehicle.target_speed} km/h，请关注 ATP 监督状态。`
  }
  return `${vehicle.vehicle_id} 当前 MA 裕量正常，可结合下方 MA 列表和闭塞状态继续检查运行许可。`
})

function maLength(v) {
  if (v.ma_limit == null) return '—'
  return `${(v.ma_limit - v.position).toFixed(1)} m`
}

function maBarStyle(v) {
  if (v.ma_limit == null) return {}
  const left = (v.position / store.totalLength) * 100
  const width = ((v.ma_limit - v.position) / store.totalLength) * 100
  return {
    left: `${left}%`,
    width: `${Math.max(0, width)}%`,
    backgroundColor: store.vehicleColor(v.vehicle_id),
  }
}

const segmentsByTrackId = computed(() => {
  const map = new Map()
  for (const segment of store.trackSegments) {
    const key = segment.track_seg_id ?? segment.segment_id
    const list = map.get(key) ?? []
    list.push(segment)
    map.set(key, list)
  }
  return map
})

const occupiedSegments = computed(() =>
  store.trackSegments.filter((segment) => segment.occupied)
)

const interlockingConflicts = computed(() => {
  const conflicts = []

  for (const turnout of store.turnouts) {
    const activeTrackId = isReverseState(turnout.state) ? turnout.reverse_seg : turnout.normal_seg
    const inactiveTrackId = isReverseState(turnout.state) ? turnout.normal_seg : turnout.reverse_seg
    const activeSegments = segmentsByTrackId.value.get(activeTrackId) ?? []
    const inactiveSegments = segmentsByTrackId.value.get(inactiveTrackId) ?? []
    const mergeSegments = segmentsByTrackId.value.get(turnout.merge_seg_id) ?? []
    const nearbySignals = store.signals.filter((signal) => Math.abs(signal.position - turnout.position) <= 260)

    const activeOccupied = activeSegments.find((segment) => segment.occupied)
    const inactiveOccupied = inactiveSegments.find((segment) => segment.occupied)
    const mergeOccupied = mergeSegments.find((segment) => segment.occupied)
    const permissiveSignal = nearbySignals.find((signal) => signal.state !== 'red')

    if (!turnout.locked && (activeOccupied || inactiveOccupied || mergeOccupied)) {
      conflicts.push({
        id: `unlock-occ-${turnout.turnout_id}`,
        level: 'high',
        kind: '道岔解锁占用',
        title: `道岔 ${turnout.turnout_id} 解锁时邻近区段仍被占用`,
        turnoutLabel: turnout.turnout_id,
        segmentLabel: [activeOccupied, inactiveOccupied, mergeOccupied]
          .filter(Boolean)
          .map((segment) => segment.segment_id)
          .join(' / '),
        signalLabel: nearbySignals.length ? nearbySignals.map((signal) => signal.signal_id).join(' / ') : '附近无已映射信号',
        detail: `当前道岔处于${isReverseState(turnout.state) ? '反位' : '定位'}且未锁闭，但关联的进路区段仍有占用，建议先确认占用列车和进路释放条件。`,
      })
    }

    if (permissiveSignal && (activeOccupied || inactiveOccupied || mergeOccupied)) {
      conflicts.push({
        id: `signal-open-${turnout.turnout_id}-${permissiveSignal.signal_id}`,
        level: 'high',
        kind: '占用下开放信号',
        title: `信号 ${permissiveSignal.signal_id} 在占用条件下未保持红灯`,
        turnoutLabel: turnout.turnout_id,
        segmentLabel: [activeOccupied, inactiveOccupied, mergeOccupied]
          .filter(Boolean)
          .map((segment) => segment.segment_id)
          .join(' / '),
        signalLabel: `${permissiveSignal.signal_id} · ${signalStateLabel(permissiveSignal.state)}`,
        detail: `道岔邻近区段存在占用，但附近信号仍显示${signalStateLabel(permissiveSignal.state)}，这通常意味着联锁约束和显示条件没有完全闭合。`,
      })
    }

    if (isReverseState(turnout.state) && inactiveOccupied) {
      conflicts.push({
        id: `reverse-branch-${turnout.turnout_id}`,
        level: 'warn',
        kind: '反位分支冲突',
        title: `道岔 ${turnout.turnout_id} 已反位，非当前分支仍存在占用`,
        turnoutLabel: turnout.turnout_id,
        segmentLabel: `${inactiveOccupied.segment_id}（非当前分支）`,
        signalLabel: nearbySignals.length ? nearbySignals.map((signal) => signal.signal_id).join(' / ') : '附近无已映射信号',
        detail: `反位道岔切向侧线时，另一分支区段仍处于占用状态，建议检查是否还有列车尾部未出清或进路未完全释放。`,
      })
    }
  }

  for (const segment of occupiedSegments.value) {
    if (segment.aspect === 'red') continue
    const relatedSignal = nearestSignal(segment.start)
    conflicts.push({
      id: `occupied-aspect-${segment.segment_id}`,
      level: 'high',
      kind: '区段显示异常',
      title: `占用分区 ${segment.segment_id} 的显示未落至红灯`,
      turnoutLabel: nearestTurnoutLabel(segment),
      segmentLabel: `${segment.segment_id} · ${Math.round(segment.start)}-${Math.round(segment.end)} m`,
      signalLabel: relatedSignal ? `${relatedSignal.signal_id} · ${signalStateLabel(relatedSignal.state)}` : '未找到前方信号',
      detail: `该分区已经被 ${segment.occupied_by ?? '列车'} 占用，但显示仍为${aspectText(segment.aspect)}，建议核对区段占用继电条件和信号防护逻辑。`,
    })
  }

  return conflicts.slice(0, 12)
})

function isReverseState(state) {
  return state === 'reverse' || state === 'diverging'
}

function signalStateLabel(state) {
  return { red: '红灯', yellow: '黄灯', green: '绿灯' }[state] ?? state
}

function aspectText(aspect) {
  return { red: '红灯', yellow: '黄灯', green: '绿灯' }[aspect] ?? aspect ?? '未知'
}

function nearestSignal(position) {
  let best = null
  let bestDistance = Number.POSITIVE_INFINITY

  for (const signal of store.signals) {
    const distance = Math.abs(signal.position - position)
    if (distance < bestDistance) {
      best = signal
      bestDistance = distance
    }
  }

  return best
}

function nearestTurnoutLabel(segment) {
  let best = null
  let bestDistance = Number.POSITIVE_INFINITY
  const center = ((segment.start ?? 0) + (segment.end ?? 0)) / 2

  for (const turnout of store.turnouts) {
    const distance = Math.abs((turnout.position ?? 0) - center)
    if (distance < bestDistance) {
      best = turnout
      bestDistance = distance
    }
  }

  return best ? best.turnout_id : '未关联'
}
</script>
