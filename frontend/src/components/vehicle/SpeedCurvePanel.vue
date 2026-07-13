<template>
  <section class="app-panel">
    <!-- 面板头 -->
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Speed Curve</p>
        <h3 class="app-section-title">速度曲线</h3>
        <p class="app-section-copy">
          实时速度随位置变化曲线，叠加当前驾驶指令的前向预测。
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <!-- 车辆选择 -->
        <select
          v-if="store.vehicles.length > 1"
          :value="store.selectedVehicleId"
          class="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-cyan-400/40"
          @change="store.selectVehicle($event.target.value)"
        >
          <option v-for="id in store.vehicles" :key="id" :value="id">{{ id }}</option>
        </select>

        <!-- 预测曲线开关 -->
        <button
          type="button"
          class="rounded-xl border px-3 py-1.5 text-xs transition-colors"
          :class="store.showPrediction
            ? 'border-cyan-400/60 bg-cyan-400/10 text-cyan-100'
            : 'border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-slate-200'"
          @click="store.showPrediction = !store.showPrediction"
        >
          {{ store.showPrediction ? '隐藏预测' : '显示预测' }}
        </button>

        <!-- 连接状态指示 -->
        <span
          class="flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs"
          :class="connectionBadgeClass"
        >
          <span
            class="h-1.5 w-1.5 rounded-full"
            :class="connectionDotClass"
          />
          {{ connectionLabel }}
        </span>
      </div>
    </div>

    <!-- 指标卡：第一行（速度 / 位置 / 加速度 / 坡度） -->
    <div v-if="store.currentStatus" class="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
      <article
        v-for="card in statusCards"
        :key="card.label"
        class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-4"
      >
        <p class="app-metric-label">{{ card.label }}</p>
        <p class="mt-2 text-lg font-semibold leading-none" :class="card.highlight ?? 'text-slate-100'">
          {{ card.value }}
        </p>
        <p class="mt-1.5 text-xs text-slate-500">{{ card.hint }}</p>
      </article>
    </div>

    <!-- 指标卡：第二行（牵引/制动档位 + 力） -->
    <div v-if="store.currentStatus && showEffortRow" class="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
      <article
        v-for="card in effortCards"
        :key="card.label"
        class="rounded-[1.05rem] border border-white/10 bg-white/[0.03] px-4 py-3"
      >
        <p class="app-metric-label">{{ card.label }}</p>
        <p class="mt-1.5 text-base font-semibold leading-none" :class="card.highlight ?? 'text-slate-200'">
          {{ card.value }}
        </p>
        <p v-if="card.sub" class="mt-1 text-xs text-slate-500">{{ card.sub }}</p>
      </article>
    </div>

    <!-- 图表 -->
    <template v-if="hasData">
      <div class="mt-4 rounded-[1.1rem] border border-white/10 bg-black/10 px-3 py-3">
        <EChartsContainer :option="chartOption" height="360px" />
      </div>

      <!-- 图例 -->
      <div class="mt-2 flex flex-wrap gap-4 px-1 text-[11px] text-slate-500">
        <span class="flex items-center gap-1.5">
          <span class="inline-block h-[2px] w-5 rounded-full bg-cyan-400" />
          实际速度
        </span>
        <span
          v-if="store.showPrediction && store.predictedPoints.length"
          class="flex items-center gap-1.5"
        >
          <span class="inline-block h-0 w-5 border-t-2 border-dashed border-amber-400" />
          预测曲线
        </span>
        <span v-if="hasSpeedLimit" class="flex items-center gap-1.5">
          <span class="inline-block h-0 w-5 border-t border-dotted border-red-400/70" />
          限速
        </span>
        <span class="ml-auto text-slate-600">
          {{ store.displayPoints.length }} 点 ·
          位置跨度 {{ positionSpan }}
        </span>
      </div>
    </template>

    <!-- 错误 -->
    <div
      v-else-if="store.error"
      class="mt-4 rounded-[1.1rem] border border-dashed border-red-400/20 bg-red-400/5 px-4 py-8 text-center text-sm text-red-300/70"
    >
      {{ store.error }}
    </div>

    <!-- 空态 -->
    <div
      v-else
      class="mt-4 rounded-[1.1rem] border border-dashed border-white/10 bg-black/10 px-4 py-12 text-center"
    >
      <p class="text-sm text-slate-500">
        {{ store.wsConnecting ? '正在连接…' : '暂无速度曲线数据' }}
      </p>
      <p class="mt-1 text-xs text-slate-600">
        {{ store.selectedVehicleId
          ? `等待 ${store.selectedVehicleId} 的数据接入`
          : '后端还没有追踪到任何车辆' }}
      </p>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import EChartsContainer from '@/components/EChartsContainer.vue'
import { useSpeedCurveStore } from '@/stores/speedCurve'

const store = useSpeedCurveStore()

// ── 连接状态 badge ────────────────────────────────────────────────────
const connectionLabel = computed(() => {
  if (store.wsConnecting) return '连接中…'
  if (store.wsConnected) return 'WebSocket 已连'
  if (store.dataSource === 'rest') return 'REST 轮询'
  return '未连接'
})
const connectionBadgeClass = computed(() => {
  if (store.wsConnected) return 'border-cyan-400/30 bg-cyan-400/5 text-cyan-300'
  if (store.wsConnecting) return 'border-amber-400/30 bg-amber-400/5 text-amber-300'
  if (store.dataSource === 'rest') return 'border-white/10 bg-white/[0.03] text-slate-400'
  return 'border-white/10 bg-white/[0.03] text-slate-600'
})
const connectionDotClass = computed(() => {
  if (store.wsConnected) return 'bg-cyan-400 animate-pulse'
  if (store.wsConnecting) return 'bg-amber-400 animate-pulse'
  if (store.dataSource === 'rest') return 'bg-slate-400'
  return 'bg-slate-700'
})

// ── 状态卡（第一行）──────────────────────────────────────────────────
const statusCards = computed(() => {
  const s = store.currentStatus
  if (!s) return []

  const overSpeed = s.current_speed_limit_kmh != null
    && s.current_speed_kmh > s.current_speed_limit_kmh
  const speedColor = s.emergency_brake
    ? 'text-red-400'
    : overSpeed
    ? 'text-amber-400'
    : 'text-cyan-200'

  return [
    {
      label: '当前速度',
      value: `${s.current_speed_kmh.toFixed(1)} km/h`,
      hint: s.emergency_brake
        ? '⚠ 紧急制动中'
        : s.current_speed_limit_kmh != null
        ? `限速 ${s.current_speed_limit_kmh.toFixed(0)} km/h`
        : `控制模式：${s.control_mode === 'ato' ? 'ATO' : '手动'}`,
      highlight: speedColor,
    },
    {
      label: '当前位置',
      value: `${s.current_position_m.toFixed(0)} m`,
      hint: '列车前端里程',
    },
    {
      label: '加速度',
      value: `${s.current_acceleration_mps2 >= 0 ? '+' : ''}${s.current_acceleration_mps2.toFixed(2)} m/s²`,
      hint: s.current_acceleration_mps2 > 0.1
        ? '牵引加速'
        : s.current_acceleration_mps2 < -0.1
        ? '制动减速'
        : '匀速/惰行',
      highlight: s.current_acceleration_mps2 < -0.8
        ? 'text-amber-300'
        : 'text-slate-100',
    },
    {
      label: '坡度',
      value: `${s.current_gradient_permille >= 0 ? '+' : ''}${s.current_gradient_permille.toFixed(1)} ‰`,
      hint: s.current_gradient_permille > 2
        ? '明显上坡'
        : s.current_gradient_permille < -2
        ? '明显下坡'
        : '近似平道',
    },
  ]
})

// ── 牵引/制动行（第二行）────────────────────────────────────────────
const showEffortRow = computed(() => {
  const s = store.currentStatus
  if (!s) return false
  return (
    s.traction_level != null ||
    s.brake_level != null ||
    s.traction_force_n != null ||
    s.brake_force_n != null
  )
})

const effortCards = computed(() => {
  const s = store.currentStatus
  if (!s) return []
  return [
    {
      label: '牵引档',
      value: s.traction_level != null ? `T${s.traction_level}` : '—',
      sub: s.current_traction_percent != null
        ? `${(s.current_traction_percent * 100).toFixed(0)}%`
        : null,
      highlight: (s.traction_level ?? 0) > 0 ? 'text-green-300' : 'text-slate-400',
    },
    {
      label: '制动档',
      value: s.brake_level != null ? `B${s.brake_level}` : '—',
      sub: s.current_brake_percent != null
        ? `${(s.current_brake_percent * 100).toFixed(0)}%`
        : null,
      highlight: (s.brake_level ?? 0) > 0 ? 'text-amber-300' : 'text-slate-400',
    },
    {
      label: '牵引力',
      value: s.traction_force_n != null
        ? `${(s.traction_force_n / 1000).toFixed(1)} kN`
        : '—',
      sub: '正值 = 驱动',
      highlight: (s.traction_force_n ?? 0) > 0 ? 'text-green-200' : 'text-slate-400',
    },
    {
      label: '制动力',
      value: s.brake_force_n != null
        ? `${(s.brake_force_n / 1000).toFixed(1)} kN`
        : '—',
      sub: s.emergency_brake ? '⚠ 紧急制动' : '常用制动',
      highlight: (s.brake_force_n ?? 0) > 0 ? 'text-red-300' : 'text-slate-400',
    },
  ]
})

// ── 图表 ─────────────────────────────────────────────────────────────
const hasData = computed(() => store.displayPoints.length > 0)

const hasSpeedLimit = computed(() =>
  store.displayPoints.some((p) => p.speed_limit_kmh != null)
)

const positionSpan = computed(() => {
  const pts = store.displayPoints
  if (pts.length < 2) return '—'
  const min = pts[0].position_m
  const max = pts[pts.length - 1].position_m
  const span = Math.abs(max - min)
  return span >= 1000 ? `${(span / 1000).toFixed(2)} km` : `${span.toFixed(0)} m`
})

const chartOption = computed(() => {
  const history = store.displayPoints
  const predicted = store.showPrediction ? store.predictedPoints : []

  // 历史曲线：[position_m, speed_kmh]
  const historySeries = history.map((p) => [p.position_m, p.speed_kmh])

  // 预测曲线：position_m 是相对当前位置的偏移，需要加上当前最后位置
  const lastPos = history.length ? history[history.length - 1].position_m : 0
  const predSeries = predicted.map((p) => [lastPos + p.position_m, p.speed_kmh])

  // 限速线
  const limitSeries = history
    .filter((p) => p.speed_limit_kmh != null)
    .map((p) => [p.position_m, p.speed_limit_kmh])

  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: { left: 52, right: 28, top: 28, bottom: 52, containLabel: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15,25,44,0.94)',
      borderColor: 'rgba(148,163,184,0.15)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter(params) {
        const pos = params[0]?.value?.[0]
        if (pos == null) return ''
        const header = `<div style="margin-bottom:5px;font-size:11px;color:#94a3b8">${pos.toFixed(0)} m</div>`
        const rows = params.map((p) => {
          const v = p.value?.[1]
          return `<span style="color:${p.color}">■</span> ${p.seriesName}：<b>${v != null ? v.toFixed(1) : '—'}</b> km/h`
        })
        // 找到当前位置对应的历史点以显示更多信息
        const nearestPt = history.reduce((best, pt) => {
          const d = Math.abs(pt.position_m - pos)
          return d < Math.abs((best?.position_m ?? Infinity) - pos) ? pt : best
        }, null)
        let extra = ''
        if (nearestPt) {
          const lines = []
          if (nearestPt.acceleration_mps2 != null)
            lines.push(`加速度：${nearestPt.acceleration_mps2 >= 0 ? '+' : ''}${nearestPt.acceleration_mps2.toFixed(2)} m/s²`)
          if (nearestPt.gradient_permille != null)
            lines.push(`坡度：${nearestPt.gradient_permille.toFixed(1)} ‰`)
          if (nearestPt.traction_level != null || nearestPt.brake_level != null)
            lines.push(`档位：T${nearestPt.traction_level ?? 0} / B${nearestPt.brake_level ?? 0}`)
          if (lines.length) {
            extra = `<div style="margin-top:6px;padding-top:5px;border-top:1px solid rgba(148,163,184,0.12);font-size:11px;color:#64748b">${lines.join('<br/>')}</div>`
          }
        }
        return header + rows.join('<br/>') + extra
      },
    },
    xAxis: {
      type: 'value',
      name: '位置（m）',
      nameLocation: 'end',
      nameGap: 8,
      nameTextStyle: { color: '#475569', fontSize: 11 },
      axisLine: { lineStyle: { color: '#1e293b' } },
      splitLine: { lineStyle: { color: '#0f172a', type: 'dashed' } },
      axisLabel: { color: '#475569', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: 'km/h',
      nameTextStyle: { color: '#475569', fontSize: 11 },
      axisLine: { lineStyle: { color: '#1e293b' } },
      splitLine: { lineStyle: { color: '#0f172a', type: 'dashed' } },
      axisLabel: { color: '#475569', fontSize: 11 },
      min: 0,
    },
    series: [
      // 实际速度（历史）
      {
        name: '实际速度',
        type: 'line',
        data: historySeries,
        smooth: 0.3,
        symbol: 'none',
        sampling: 'lttb',
        lineStyle: { color: '#22d3ee', width: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(34,211,238,0.15)' },
              { offset: 1, color: 'rgba(34,211,238,0.01)' },
            ],
          },
        },
      },
      // 预测曲线
      ...(predSeries.length
        ? [{
            name: '预测曲线',
            type: 'line',
            data: predSeries,
            smooth: 0.4,
            symbol: 'none',
            lineStyle: { color: '#fbbf24', width: 1.5, type: 'dashed' },
          }]
        : []),
      // 限速线
      ...(limitSeries.length
        ? [{
            name: '限速',
            type: 'line',
            data: limitSeries,
            smooth: false,
            symbol: 'none',
            lineStyle: { color: 'rgba(248,113,113,0.65)', width: 1.5, type: 'dotted' },
          }]
        : []),
    ],
  }
})
</script>
