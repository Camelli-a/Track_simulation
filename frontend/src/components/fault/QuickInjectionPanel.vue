<template>
  <section class="app-panel">
    <div class="app-section-head">
      <div>
        <p class="app-section-kicker">Quick Injection</p>
        <h3 class="app-section-title">快速故障注入区</h3>
        <p class="app-section-copy">
          这里将放前方红灯、MA 收缩、区间封锁、道岔故障、通信异常等快速入口。
        </p>
      </div>
    </div>

    <div class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
      <article class="rounded-[1.1rem] border border-white/10 bg-white/[0.03] px-4 py-4">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h4 class="text-sm font-semibold text-slate-100">当前可直接执行的演示动作</h4>
            <p class="mt-1 text-xs text-slate-500">这些动作已经走在现有真实接口上，不依赖额外的故障注入协议。</p>
          </div>
          <span class="app-chip">已接后端</span>
        </div>

        <div class="mt-4 space-y-3">
          <button
            v-for="action in executableActions"
            :key="action.key"
            type="button"
            class="w-full rounded-[1rem] border border-white/10 bg-black/10 px-4 py-4 text-left transition hover:border-white/20 hover:bg-white/[0.05]"
            @click="action.onClick"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="text-sm font-medium text-slate-100">{{ action.title }}</p>
                <p class="mt-2 text-sm leading-6 text-slate-300">{{ action.detail }}</p>
                <p class="mt-2 text-[11px] text-slate-500">{{ action.hint }}</p>
              </div>
              <span class="rounded-full bg-cyan-950 px-3 py-1 text-[11px] text-cyan-200">执行</span>
            </div>
          </button>
        </div>
      </article>

      <article class="rounded-[1.1rem] border border-amber-900/40 bg-amber-950/10 px-4 py-4">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h4 class="text-sm font-semibold text-slate-100">待后端补专用注入协议</h4>
            <p class="mt-1 text-xs text-slate-500">这些动作目前只能在界面层提示，真正生效仍需要后端提供故障注入 API 或事件协议。</p>
          </div>
          <span class="app-chip">待补接口</span>
        </div>

        <div class="mt-4 space-y-3">
          <div
            v-for="action in pendingActions"
            :key="action.key"
            class="rounded-[1rem] border border-amber-900/40 bg-black/10 px-4 py-4"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="text-sm font-medium text-slate-100">{{ action.title }}</p>
                <p class="mt-2 text-sm leading-6 text-slate-300">{{ action.detail }}</p>
                <p class="mt-2 text-[11px] text-amber-200/80">{{ action.hint }}</p>
              </div>
              <span class="rounded-full bg-amber-950 px-3 py-1 text-[11px] text-amber-200">待接入</span>
            </div>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useFaultWorkbench } from '@/composables/useFaultWorkbench'

const {
  injectEmergencyBrake,
  injectLowSpeedCommand,
  injectStopAtMa,
  focusLatestAnomalyVehicle,
  publishTrackInfoAction,
} = useFaultWorkbench()

const executableActions = computed(() => [
  {
    key: 'emergency_brake',
    title: 'ATP 介入停车演示',
    detail: '对当前关注车辆下发紧急制动，直接演示 ATP 抢权停车。',
    hint: '走 `/api/v1/vehicle/control` 的真实紧急制动能力。',
    onClick: injectEmergencyBrake,
  },
  {
    key: 'low_speed',
    title: '低速约束演示',
    detail: '对当前关注车辆下发 15 km/h 目标速度，观察速度曲线、MA 裕量和场景变化。',
    hint: '走真实 ATO 控制接口，用于替代“临时限速”类演示。',
    onClick: injectLowSpeedCommand,
  },
  {
    key: 'stop_target',
    title: '安全停车目标演示',
    detail: '对当前关注车辆下发 0 km/h 停车目标，观察是否在 MA 边界内安全停住。',
    hint: '适合演示“前方约束出现后车辆如何收敛到停车结果”。',
    onClick: injectStopAtMa,
  },
  {
    key: 'focus_abnormal',
    title: '自动聚焦异常车辆',
    detail: '自动选择当前最需要看的异常车辆，方便你回切到其他页继续讲解。',
    hint: '优先挑 ATP 介入、停车等待或 MA 受限的车辆。',
    onClick: focusLatestAnomalyVehicle,
  },
  {
    key: 'publish_track',
    title: '重新发布线路静态数据',
    detail: '向主链路重新发布 `track_info`，适合在演示开场或链路异常后快速校准。',
    hint: '走 `/api/v1/dashboard/publish-track-info`。',
    onClick: publishTrackInfoAction,
  },
])

const pendingActions = computed(() => [
  {
    key: 'red_signal',
    title: '前方红灯注入',
    detail: '前端可以展示“红灯停车”结果，但要真正改变后端联锁和信号状态，还需要后端补红灯注入接口。',
    hint: '建议后端提供 signal / route 层的 fault injection endpoint。',
  },
  {
    key: 'ma_shrink',
    title: 'MA 收缩注入',
    detail: 'Page 1 和 Page 2 已经能识别 MA 收缩结果，但前端目前还没有一个真实后端接口可以主动触发这类收缩。',
    hint: '建议后端提供按 vehicle_id 注入新 MA 边界或故障原因的接口。',
  },
  {
    key: 'section_block',
    title: '区段封锁 / 站间不可用',
    detail: '这类演示最适合老师说的“某几站不可用”场景，但必须由后端真正修改 route_result / section condition。',
    hint: '建议后端支持按 section_id 设置 blocked / fault 条件。',
  },
  {
    key: 'comm_abnormal',
    title: '通信异常 / 数据降级',
    detail: '当前前端能显示连接状态和 stale，但不能主动让后端进入通信降级或断链演示。',
    hint: '建议后端补 communication fault 或 mock source degradation 接口。',
  },
])
</script>
