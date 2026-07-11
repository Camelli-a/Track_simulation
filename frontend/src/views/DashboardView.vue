<template>
  <div class="space-y-5">
    <header class="app-panel">
      <div class="app-section-head">
        <div>
          <p class="app-section-kicker">Line Situation</p>
          <h2 class="text-xl font-semibold text-slate-100">全线态势</h2>
          <p class="app-section-copy">
            把线路主视图、分区占用、联锁约束和 MA 授权放在同一页面里，减少来回切页才能判断问题的成本。
          </p>
        </div>

        <div class="flex flex-wrap gap-2">
          <button
            v-for="mode in sandboxModes"
            :key="mode.value"
            type="button"
            class="rounded-xl border px-3 py-2 text-xs transition-colors"
            :class="sandboxMode === mode.value
              ? 'border-cyan-400/60 bg-cyan-400/10 text-cyan-100'
              : 'border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-slate-200'"
            @click="setSandboxMode(mode.value)"
          >
            {{ mode.label }}
          </button>
        </div>
      </div>

      <div class="mt-4 flex flex-wrap gap-2 text-xs">
        <span class="app-chip">全长 {{ (store.totalLength / 1000).toFixed(1) }} km</span>
        <span class="app-chip">{{ store.stations.length }} 座车站</span>
        <span class="app-chip">{{ store.vehicles.length }} 列在线列车</span>
        <span class="app-chip">{{ occupiedCount }} 个占用分区</span>
        <span class="app-chip">{{ deniedRouteCount }} 项进路未通过</span>
        <span class="app-chip">{{ interlockingConflicts.length }} 项联锁待核查</span>
      </div>
    </header>

    <PageEmptyState
      v-if="!store.trackSegments.length && !store.stations.length"
      title="等待线路底座数据接入"
      description="当前还没有收到区段、车站和线路拓扑快照，因此无法展示全线态势、站场下钻和联锁冲突。"
      next-step="请确认后端已推送 sections、stations 和线路静态布局；如果连接已建立但这里仍为空，请先检查 line-layout 与实时快照的区段映射。"
    />

    <template v-else>
      <section class="app-panel">
        <div class="app-section-head">
          <div>
            <p class="app-section-kicker">Main Sandbox</p>
            <h3 class="app-section-title">线路主视图</h3>
            <p class="app-section-copy">
              电子地图适合看全线拓扑，站序图适合按站下钻，里程展开适合沿线查占用与信号变化。
            </p>
          </div>

          <div class="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span v-if="selectedStationRange" class="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-3 py-1 text-cyan-200">
              已下钻 {{ selectedStationRange.name }}
            </span>
            <span class="rounded-full border border-white/10 px-3 py-1">
              {{ sandboxModeLabel }}
            </span>
          </div>
        </div>

        <div class="mt-4">
          <TrackGraphSandbox
            v-if="sandboxMode === 'occ'"
            :graph="store.graph"
            :blocks="store.rawBlocks"
            :segments="store.trackSegments"
            :stations="store.stations"
            :turnouts="store.turnouts"
            :signals="store.signals"
            :vehicles="store.vehicles"
            :selected-id="store.selectedVehicleId"
            :total-length="store.totalLength"
            :motion-paused="store.dataStale"
            :color="store.vehicleColor"
            @select="store.selectVehicle"
          />

          <TrackLineSchematic
            v-else-if="sandboxMode === 'schematic'"
            :stations="store.stations"
            :segments="store.trackSegments"
            :vehicles="store.vehicles"
            :total-length="store.totalLength"
            :motion-paused="store.dataStale"
            :selected-id="store.selectedVehicleId"
            :selected-station-id="selectedStationId"
            :color="store.vehicleColor"
            @select="store.selectVehicle"
            @select-station="toggleStation"
          />

          <TrackSandbox
            v-else
            :segments="store.trackSegments"
            :vehicles="store.vehicles"
            :signals="store.signals"
            :turnouts="store.turnouts"
            :stations="store.stations"
            :selected-id="store.selectedVehicleId"
            :total-length="store.totalLength"
            :motion-paused="store.dataStale"
            :layout-loaded="!!store.slopeProfile.length"
            :color="store.vehicleColor"
            @select="store.selectVehicle"
          />
        </div>

        <div
          v-if="sandboxMode === 'schematic'"
          class="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-[1rem] border border-white/10 bg-white/[0.03] px-4 py-3 text-xs"
        >
          <p class="text-slate-400">
            点击站名即可在当前页展开站场，快速核对该站的区段、信号机、道岔和当前列车。
          </p>
          <button
            v-if="selectedStationRange"
            type="button"
            class="rounded-full border border-white/10 px-3 py-1 text-slate-300 transition hover:border-white/20 hover:bg-white/5"
            @click="selectedStationId = null"
          >
            收起 {{ selectedStationRange.name }}
          </button>
        </div>

        <StationYardPanel
          v-if="sandboxMode === 'schematic' && selectedStationRange"
          class="mt-4"
          :station="selectedStationRange"
          :range="selectedStationRange"
          :stations="store.stations"
          :segments="store.trackSegments"
          :signals="store.signals"
          :turnouts="store.turnouts"
          :vehicles="store.vehicles"
          :color="store.vehicleColor"
          @close="selectedStationId = null"
        />
      </section>

      <section class="app-panel">
        <div class="app-section-head">
          <div>
            <p class="app-section-kicker">Signal Inline</p>
            <h3 class="app-section-title">信号 / 道岔状态</h3>
            <p class="app-section-copy">
              用分区色带先看占用分布，再只把真正影响调度判断的联锁冲突与道岔状态挑出来。
            </p>
          </div>

          <div class="flex flex-wrap gap-2 text-xs">
            <span class="app-chip">红灯 / 占用 {{ occupiedCount }}</span>
            <span class="app-chip">黄灯接近 {{ warningSegmentCount }}</span>
            <span class="app-chip">道岔 {{ store.turnouts.length }} 组</span>
          </div>
        </div>

        <div class="mt-4">
          <SegmentStatusBar :segments="store.trackSegments" />
        </div>

        <div class="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
          <div class="app-metric-tile">
            <p class="app-metric-label">联锁冲突</p>
            <p class="app-metric-value">{{ interlockingConflicts.length }}</p>
            <p class="mt-2 text-xs text-slate-500">直接列出不满足条件的道岔、区段和信号组合。</p>
          </div>
          <div class="app-metric-tile">
            <p class="app-metric-label">未通过进路申请</p>
            <p class="app-metric-value">{{ deniedRouteCount }}</p>
            <p class="mt-2 text-xs text-slate-500">{{ deniedRouteSummary }}</p>
          </div>
          <div class="app-metric-tile">
            <p class="app-metric-label">数据等待提示</p>
            <p class="mt-1 text-sm text-slate-200">{{ signalReadinessText }}</p>
            <p class="mt-2 text-xs text-slate-500">{{ signalReadinessNextStep }}</p>
          </div>
        </div>

        <div v-if="interlockingConflicts.length" class="mt-5 space-y-3">
          <article
            v-for="conflict in interlockingConflicts"
            :key="conflict.id"
            class="rounded-[1.15rem] border px-4 py-4"
            :class="conflict.level === 'high'
              ? 'border-red-900/60 bg-red-950/20'
              : 'border-amber-900/60 bg-amber-950/20'"
          >
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div class="flex flex-wrap items-center gap-2">
                <span
                  class="rounded-full px-2 py-0.5 text-[11px]"
                  :class="conflict.level === 'high'
                    ? 'bg-red-950 text-red-300'
                    : 'bg-amber-950 text-amber-300'"
                >
                  {{ conflict.level === 'high' ? '高优先级' : '关注' }}
                </span>
                <span class="text-sm font-medium text-slate-100">{{ conflict.title }}</span>
              </div>
              <span class="text-[11px] text-slate-500">{{ conflict.kind }}</span>
            </div>

            <div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3 text-xs">
              <div class="app-metric-tile">
                <p class="app-metric-label">道岔</p>
                <p class="mt-1 text-slate-200">{{ conflict.turnoutLabel }}</p>
              </div>
              <div class="app-metric-tile">
                <p class="app-metric-label">区段</p>
                <p class="mt-1 text-slate-200">{{ conflict.segmentLabel }}</p>
              </div>
              <div class="app-metric-tile">
                <p class="app-metric-label">信号</p>
                <p class="mt-1 text-slate-200">{{ conflict.signalLabel }}</p>
              </div>
            </div>

            <p class="mt-3 text-sm leading-6 text-slate-300">{{ conflict.detail }}</p>
          </article>
        </div>

        <div
          v-else
          class="mt-5 rounded-[1.15rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center"
        >
          <p class="text-sm text-slate-200">当前未发现明显联锁冲突</p>
          <p class="mt-2 text-xs leading-5 text-slate-500">
            系统仍会持续检查“区段占用但信号开放”“关键道岔解锁时邻近区段占用”“反位道岔涉及冲突分支占用”等条件。
          </p>
        </div>

        <div class="mt-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h4 class="text-sm font-semibold text-slate-100">道岔状态表</h4>
              <p class="mt-1 text-xs text-slate-500">默认折叠；若存在冲突会自动展开，优先标出受影响的关键道岔。</p>
            </div>
            <button
              type="button"
              class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:bg-white/10"
              @click="turnoutPanelOpen = !turnoutPanelOpen"
            >
              {{ turnoutPanelOpen ? '收起' : '展开' }}道岔表
            </button>
          </div>

          <div v-if="turnoutPanelOpen" class="app-table-shell">
            <table class="app-table">
              <thead>
                <tr>
                  <th class="text-left">道岔</th>
                  <th class="text-right">位置</th>
                  <th class="text-right">状态</th>
                  <th class="text-right">锁闭</th>
                  <th class="text-right">锁闭进路</th>
                  <th class="text-right">原因</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="turnout in sortedTurnouts"
                  :key="turnout.turnout_id"
                  :class="turnoutConflictIds.has(turnout.turnout_id) ? 'bg-red-950/10' : ''"
                >
                  <td class="text-slate-200">{{ turnout.turnout_id }}</td>
                  <td class="text-right text-slate-400">{{ Math.round(turnout.position ?? 0) }} m</td>
                  <td class="text-right" :class="isReverseState(turnout.state) ? 'text-cyan-300' : 'text-slate-300'">
                    {{ isReverseState(turnout.state) ? '反位' : '定位' }}
                  </td>
                  <td class="text-right" :class="turnout.locked ? 'text-amber-300' : 'text-slate-500'">
                    {{ turnout.locked ? '锁闭' : '解锁' }}
                  </td>
                  <td class="text-right text-slate-400">{{ turnout.locked_by_route_id ?? '—' }}</td>
                  <td class="text-right text-slate-400">{{ reasonLabel(turnout.reason) }}</td>
                </tr>
                <tr v-if="!store.turnouts.length">
                  <td colspan="6" class="py-8 text-center text-slate-500">暂无道岔数据</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section class="app-panel">
        <div class="app-section-head">
          <div>
            <p class="app-section-kicker">Communication & Commands</p>
            <h3 class="app-section-title">通信链路与控制输入</h3>
            <p class="app-section-copy">
              这里直接消费后端的 `communication`、`driver_inputs`、`ato_commands` 和 `publish-track-info` 接口，用于联调链路、司机台和算法下发。
            </p>
          </div>
          <button
            type="button"
            class="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs text-cyan-100 transition hover:border-cyan-300/50 hover:bg-cyan-400/15"
            @click="requestPublishTrackInfo"
          >
            发布当前线路数据
          </button>
        </div>

        <div class="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-4">
          <div class="app-metric-tile">
            <p class="app-metric-label">司机台连接</p>
            <p class="mt-1 text-sm text-slate-200">{{ communication.driver_console_connected ? '已连接' : '未连接' }}</p>
            <p class="mt-2 text-xs text-slate-500">来源 {{ communication.source ?? 'unknown' }}</p>
          </div>
          <div class="app-metric-tile">
            <p class="app-metric-label">UDP / ZMQ</p>
            <p class="mt-1 text-sm text-slate-200">
              UDP {{ communication.udp_connected ? '在线' : '离线' }} · ZMQ {{ communication.zmq_connected ? '在线' : '离线' }}
            </p>
            <p class="mt-2 text-xs text-slate-500">若这里离线，优先看后端消息总线和通信模块。</p>
          </div>
          <div class="app-metric-tile">
            <p class="app-metric-label">链路延迟 / 丢包</p>
            <p class="mt-1 text-sm text-slate-200">{{ communicationLatencyLabel }}</p>
            <p class="mt-2 text-xs text-slate-500">丢包 {{ communication.packet_loss_count ?? 0 }} 次</p>
          </div>
          <div class="app-metric-tile">
            <p class="app-metric-label">最近协议消息</p>
            <p class="mt-1 text-sm text-slate-200">{{ communicationMessageLabel }}</p>
            <p class="mt-2 text-xs text-slate-500">用于判断上游仿真是否还在持续推送。</p>
          </div>
        </div>

        <div class="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-2">
          <div class="rounded-[1.15rem] border border-white/10 bg-black/10 px-4 py-4">
            <div class="flex items-center justify-between gap-3">
              <div>
                <h4 class="text-sm font-semibold text-slate-100">司机台最近输入</h4>
                <p class="mt-1 text-xs text-slate-500">直接展示后端 `driver_inputs`，便于核对司机台指令是否真的进到了前端链路。</p>
              </div>
              <span class="rounded-full border border-white/10 px-3 py-1 text-[11px] text-slate-400">
                {{ store.driverInputs.length }} 条
              </span>
            </div>

            <div v-if="sortedDriverInputs.length" class="mt-4 space-y-2">
              <div
                v-for="input in sortedDriverInputs"
                :key="`${input.vehicle_id}-${input.updated_at}-${input.source}`"
                class="rounded-xl border border-white/10 bg-white/[0.02] px-4 py-3"
              >
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <span class="text-sm font-medium text-slate-100">{{ input.vehicle_id }}</span>
                  <span class="text-[11px] text-slate-500">{{ formatEpochTime(input.updated_at) }}</span>
                </div>
                <p class="mt-1 text-xs text-slate-400">
                  来源 {{ input.source }} · 模式 {{ input.control_mode }} · 方向 {{ input.direction }}
                </p>
                <p class="mt-2 text-xs text-slate-300">
                  牵引 {{ input.traction_level }} / 制动 {{ input.brake_level }} / 紧急按钮 {{ input.emergency_button ? '按下' : '未按下' }}
                </p>
              </div>
            </div>

            <div v-else class="mt-4 rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-6 text-center text-sm text-slate-500">
              当前还没有收到司机台输入；如果你正在联调通信模块，这里应当随输入变化而刷新。
            </div>
          </div>

          <div class="rounded-[1.15rem] border border-white/10 bg-black/10 px-4 py-4">
            <div class="flex items-center justify-between gap-3">
              <div>
                <h4 class="text-sm font-semibold text-slate-100">ATO 最近下发命令</h4>
                <p class="mt-1 text-xs text-slate-500">直接展示后端 `ato_commands`，便于核对算法目标速度和目标位置有没有进入 OCC 视图。</p>
              </div>
              <span class="rounded-full border border-white/10 px-3 py-1 text-[11px] text-slate-400">
                {{ store.atoCommands.length }} 条
              </span>
            </div>

            <div v-if="sortedAtoCommands.length" class="mt-4 space-y-2">
              <div
                v-for="command in sortedAtoCommands"
                :key="`${command.vehicle_id}-${command.updated_at}-${command.reason}`"
                class="rounded-xl border border-white/10 bg-white/[0.02] px-4 py-3"
              >
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <span class="text-sm font-medium text-slate-100">{{ command.vehicle_id }}</span>
                  <span class="text-[11px] text-slate-500">{{ formatEpochTime(command.updated_at) }}</span>
                </div>
                <p class="mt-1 text-xs text-slate-400">
                  目标速度 {{ command.target_speed }} km/h · 目标位置 {{ command.target_position != null ? `${Math.round(command.target_position)} m` : '—' }}
                </p>
                <p class="mt-2 text-xs text-slate-300">
                  牵引 {{ command.traction_level }} / 制动 {{ command.brake_level }} / 原因 {{ command.reason ?? '—' }}
                </p>
              </div>
            </div>

            <div v-else class="mt-4 rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-6 text-center text-sm text-slate-500">
              当前还没有收到 ATO 指令；如果算法模块正在下发目标速度，这里应当出现最新指令。
            </div>
          </div>
        </div>
      </section>

      <section class="app-panel">
        <div class="app-section-head">
          <div>
            <p class="app-section-kicker">Movement Authority</p>
            <h3 class="app-section-title">MA 授权总览</h3>
            <p class="app-section-copy">
              用每列车的当前位置和 MA 范围做可视化进度条，替代表格堆叠，快速判断哪一列车更接近授权边界。
            </p>
          </div>
          <span class="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-400">
            当前关注 {{ store.selectedVehicle?.vehicle_id ?? '未选车' }}
          </span>
        </div>

        <div class="mt-4 space-y-4">
          <div
            v-for="vehicle in vehiclesWithMa"
            :key="vehicle.vehicle_id"
            class="rounded-[1.1rem] border border-white/10 bg-black/10 px-4 py-4"
          >
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div class="flex items-center gap-3">
                <span class="h-2.5 w-2.5 rounded-full" :style="{ backgroundColor: store.vehicleColor(vehicle.vehicle_id) }" />
                <div>
                  <p class="text-sm font-medium text-slate-100">{{ vehicle.vehicle_id }}</p>
                  <p class="mt-1 text-[11px] text-slate-500">
                    {{ vehicle.mode ?? '—' }} · 许可 {{ permissionLabel(vehicle.ma_permission) }} · 信号 {{ signalStateLabel(vehicle.ma_signal_state) }}
                  </p>
                </div>
              </div>

              <div class="text-right text-xs">
                <p class="text-slate-300">{{ vehicle.ma_limit != null ? `${Math.max(0, vehicle.ma_limit - vehicle.position).toFixed(1)} m` : '暂无 MA' }}</p>
                <p class="mt-1 text-slate-500">{{ vehicle.ma_route_id ?? '未上报进路' }}</p>
              </div>
            </div>

            <div class="relative mt-4 h-3 overflow-hidden rounded-full bg-slate-900">
              <div
                class="absolute top-0 h-full rounded-full opacity-75"
                :style="maBarStyle(vehicle)"
              />
              <span
                class="absolute top-1/2 h-4 w-0.5 -translate-y-1/2 bg-white/80"
                :style="{ left: `${vehiclePositionPercent(vehicle)}%` }"
              />
              <span
                v-if="vehicle.ma_limit != null"
                class="absolute top-1/2 h-4 w-0.5 -translate-y-1/2 bg-cyan-100/80"
                :style="{ left: `${vehicleMaPercent(vehicle)}%` }"
              />
            </div>

            <div class="mt-3 grid grid-cols-2 gap-3 text-xs lg:grid-cols-4">
              <div class="app-metric-tile">
                <p class="app-metric-label">当前位置</p>
                <p class="mt-1 text-slate-200">{{ Math.round(vehicle.position) }} m</p>
              </div>
              <div class="app-metric-tile">
                <p class="app-metric-label">MA 边界</p>
                <p class="mt-1 text-slate-200">{{ vehicle.ma_limit != null ? `${Math.round(vehicle.ma_limit)} m` : '—' }}</p>
              </div>
              <div class="app-metric-tile">
                <p class="app-metric-label">协议限速</p>
                <p class="mt-1 text-slate-200">{{ vehicle.ma_speed_limit != null ? `${vehicle.ma_speed_limit} km/h` : '—' }}</p>
              </div>
              <div class="app-metric-tile">
                <p class="app-metric-label">前车 / 安全间距</p>
                <p class="mt-1 text-slate-200">
                  {{ vehicle.ma_front_vehicle_id ?? '无前车' }}
                  <span v-if="vehicle.ma_safe_distance != null" class="text-slate-500"> · {{ vehicle.ma_safe_distance }} m</span>
                </p>
              </div>
            </div>
          </div>

          <div
            v-if="!vehiclesWithMa.length"
            class="rounded-[1.15rem] border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500"
          >
            当前尚未收到列车 MA 数据；请确认后端是否已推送 `ma_limits` 或每车 `ma_limit` 字段。
          </div>
        </div>
      </section>

      <section class="app-panel">
        <div class="app-section-head">
          <div>
            <p class="app-section-kicker">Timeline</p>
            <h3 class="app-section-title">时间轴</h3>
            <p class="app-section-copy">
              折叠收纳占用热图与事件流，避免一直占大面积，但需要追溯时一键展开。
            </p>
          </div>
          <button
            type="button"
            class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:bg-white/10"
            @click="timelineExpanded = !timelineExpanded"
          >
            {{ timelineExpanded ? '收起时间轴' : '展开时间轴' }}
          </button>
        </div>

        <div v-if="timelineExpanded" class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
          <div class="app-panel-compact">
            <OccupancyTimeline
              :occupancy-history="store.occupancyHistory"
              :time-labels="store.timeLabels"
              :total-length="store.totalLength"
              :stations="store.stations"
            />
          </div>
          <div class="app-panel-compact">
            <EventTimeline
              :events="store.eventTimeline"
              :selected-vehicle-id="store.selectedVehicleId"
              :color="store.vehicleColor"
              @select="store.selectVehicle"
            />
          </div>
        </div>

        <div
          v-else
          class="mt-4 rounded-[1.1rem] border border-dashed border-white/10 bg-black/10 px-4 py-5 text-sm text-slate-400"
        >
          当前已折叠时间轴。这里收纳最近 {{ store.timeLabels.length }} 帧占用历史与 {{ store.eventTimeline.length }} 条事件，便于需要时再展开追溯。
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { usePageSimulation } from '@/composables/usePageSimulation'
import EventTimeline from '@/components/EventTimeline.vue'
import OccupancyTimeline from '@/components/OccupancyTimeline.vue'
import PageEmptyState from '@/components/PageEmptyState.vue'
import SegmentStatusBar from '@/components/SegmentStatusBar.vue'
import StationYardPanel from '@/components/StationYardPanel.vue'
import TrackGraphSandbox from '@/components/TrackGraphSandbox.vue'
import TrackLineSchematic from '@/components/TrackLineSchematic.vue'
import TrackSandbox from '@/components/TrackSandbox.vue'
import { useUiStore } from '@/stores/ui'

const store = usePageSimulation()
const ui = useUiStore()

const sandboxMode = ref('occ')
const selectedStationId = ref(null)
const turnoutPanelOpen = ref(false)
const timelineExpanded = ref(false)

const sandboxModes = [
  { value: 'occ', label: '电子地图' },
  { value: 'schematic', label: '站序图' },
  { value: 'linear', label: '里程展开' },
]

const sandboxModeLabel = computed(() =>
  sandboxModes.find((mode) => mode.value === sandboxMode.value)?.label ?? '电子地图'
)

const occupiedCount = computed(() =>
  store.trackSegments.filter((segment) => segment.occupied).length
)

const warningSegmentCount = computed(() =>
  store.trackSegments.filter((segment) => {
    const aspect = segment.aspect ?? (segment.occupied ? 'red' : 'green')
    return aspect === 'yellow'
  }).length
)

const deniedRouteCount = computed(() =>
  store.routeResults.filter((result) => !result.allowed).length
)

const deniedRouteSummary = computed(() => {
  if (!deniedRouteCount.value) return '当前所有已上报进路申请均已满足条件。'
  const sample = store.routeResults.find((result) => !result.allowed)
  return sample
    ? `${sample.vehicle_id ?? '列车'} 的 ${sample.route_id ?? '进路'} 最近一次未通过。`
    : '最近存在未通过的进路申请。'
})

const sortedStations = computed(() =>
  [...store.stations].sort((a, b) => (a.position ?? 0) - (b.position ?? 0))
)

const stationRanges = computed(() =>
  sortedStations.value.map((station, index) => ({
    ...station,
    start: index === 0 ? 0 : ((sortedStations.value[index - 1].position ?? 0) + (station.position ?? 0)) / 2,
    end: index === sortedStations.value.length - 1
      ? store.totalLength
      : ((station.position ?? 0) + (sortedStations.value[index + 1].position ?? store.totalLength)) / 2,
  }))
)

const selectedStationRange = computed(() =>
  stationRanges.value.find((station) => station.station_id === selectedStationId.value) ?? null
)

const selectedStationSegments = computed(() => {
  if (!selectedStationRange.value) return []
  return store.trackSegments.filter((segment) => isSegmentInStation(segment, selectedStationRange.value))
})

const selectedStationSignals = computed(() => {
  if (!selectedStationRange.value) return []
  return store.signals.filter((signal) =>
    isWithinExpandedRange(signal.position, selectedStationRange.value, 320)
  )
})

const selectedStationTurnouts = computed(() => {
  if (!selectedStationRange.value) return []
  return store.turnouts.filter((turnout) =>
    isWithinExpandedRange(turnout.position, selectedStationRange.value, 420)
  )
})

const selectedStationVehicles = computed(() => {
  if (!selectedStationRange.value) return []
  return store.vehicles.filter((vehicle) =>
    vehicle.station_name === selectedStationRange.value.name
    || isWithinExpandedRange(vehicle.position, selectedStationRange.value, 260)
  )
})

const vehiclesWithMa = computed(() =>
  store.vehicles.filter((vehicle) => vehicle.ma_limit != null)
)

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

const protocolRouteConflicts = computed(() =>
  store.routeResults
    .filter((result) => !result.allowed)
    .map((result) => ({
      id: `route-${result.vehicle_id}-${result.route_id}`,
      level: 'high',
      kind: '协议进路冲突',
      title: `${result.vehicle_id ?? '未知列车'} 的 ${result.route_id ?? '未命名进路'} 不满足联锁条件`,
      turnoutLabel: result.required_switch_id ?? '未上报道岔',
      segmentLabel: result.locked_by_route_id ? `被进路 ${result.locked_by_route_id} 占用/锁闭` : '需结合区段状态继续核对',
      signalLabel: result.current_position
        ? `当前 ${isReverseState(result.current_position) ? '反位' : '定位'} → 需要 ${isReverseState(result.required_position) ? '反位' : '定位'}`
        : '未上报当前位置',
      detail: `后端返回原因：${reasonLabel(result.reason)}。建议优先核对 ${result.required_switch_id ?? '对应道岔'} 的锁闭方和所需位置。`,
    }))
)

const heuristicConflicts = computed(() => {
  const conflicts = []

  for (const turnout of store.turnouts) {
    const activeTrackId = isReverseState(turnout.state) ? turnout.reverse_seg : turnout.normal_seg
    const inactiveTrackId = isReverseState(turnout.state) ? turnout.normal_seg : turnout.reverse_seg
    const activeSegments = segmentsByTrackId.value.get(activeTrackId) ?? []
    const inactiveSegments = segmentsByTrackId.value.get(inactiveTrackId) ?? []
    const mergeSegments = segmentsByTrackId.value.get(turnout.merge_seg_id) ?? []
    const nearbySignals = store.signals.filter((signal) => Math.abs((signal.position ?? 0) - (turnout.position ?? 0)) <= 260)

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
        segmentLabel: [activeOccupied, inactiveOccupied, mergeOccupied].filter(Boolean).map((segment) => segment.segment_id).join(' / '),
        signalLabel: nearbySignals.length ? nearbySignals.map((signal) => signal.signal_id).join(' / ') : '附近无已映射信号',
        detail: `当前道岔处于${isReverseState(turnout.state) ? '反位' : '定位'}且未锁闭，但关联进路区段仍有占用，建议先确认占用列车和进路释放条件。`,
      })
    }

    if (permissiveSignal && (activeOccupied || inactiveOccupied || mergeOccupied)) {
      conflicts.push({
        id: `signal-open-${turnout.turnout_id}-${permissiveSignal.signal_id}`,
        level: 'high',
        kind: '占用下开放信号',
        title: `信号 ${permissiveSignal.signal_id} 在占用条件下未保持红灯`,
        turnoutLabel: turnout.turnout_id,
        segmentLabel: [activeOccupied, inactiveOccupied, mergeOccupied].filter(Boolean).map((segment) => segment.segment_id).join(' / '),
        signalLabel: `${permissiveSignal.signal_id} · ${signalStateLabel(permissiveSignal.state)}`,
        detail: `道岔邻近区段存在占用，但附近信号仍显示${signalStateLabel(permissiveSignal.state)}，通常意味着联锁约束和显示条件没有完全闭合。`,
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
        detail: '建议检查是否仍有列车尾部未出清，或进路释放条件没有完全满足。',
      })
    }
  }

  for (const segment of occupiedSegments.value) {
    if ((segment.aspect ?? 'red') === 'red') continue
    const relatedSignal = nearestSignal(segment.start)
    conflicts.push({
      id: `occupied-aspect-${segment.segment_id}`,
      level: 'high',
      kind: '区段显示异常',
      title: `占用分区 ${segment.segment_id} 的显示未落至红灯`,
      turnoutLabel: nearestTurnoutLabel(segment),
      segmentLabel: `${segment.segment_id} · ${Math.round(segment.start ?? 0)}-${Math.round(segment.end ?? 0)} m`,
      signalLabel: relatedSignal ? `${relatedSignal.signal_id} · ${signalStateLabel(relatedSignal.state)}` : '未找到前方信号',
      detail: `该分区已被 ${segment.occupied_by ?? '列车'} 占用，但显示仍为${aspectLabel(segment.aspect)}，建议核对区段占用和信号防护逻辑。`,
    })
  }

  return conflicts
})

const interlockingConflicts = computed(() =>
  [...protocolRouteConflicts.value, ...heuristicConflicts.value].slice(0, 8)
)

const turnoutConflictIds = computed(() =>
  new Set(
    interlockingConflicts.value
      .map((conflict) => conflict.turnoutLabel)
      .filter(Boolean)
      .filter((label) => label !== '未上报道岔')
  )
)

const sortedTurnouts = computed(() =>
  [...store.turnouts].sort((a, b) => {
    const aPriority = turnoutConflictIds.value.has(a.turnout_id) ? 0 : 1
    const bPriority = turnoutConflictIds.value.has(b.turnout_id) ? 0 : 1
    if (aPriority !== bPriority) return aPriority - bPriority
    return (a.position ?? 0) - (b.position ?? 0)
  })
)

const signalReadinessText = computed(() => {
  if (!store.trackSegments.length && !store.signals.length) return '正在等待区段、信号机和道岔首帧快照。'
  if (!store.signals.length) return '已收到区段，但信号机状态还未到达。'
  if (!store.turnouts.length) return '已收到区段与信号，但道岔状态还未到达。'
  return '线路、信号和道岔快照已接入，可继续做联锁核查。'
})

const communication = computed(() =>
  store.communication ?? {
    source: 'unknown',
    driver_console_connected: false,
    udp_connected: false,
    zmq_connected: false,
    latency_ms: null,
    packet_loss_count: 0,
    last_message_at: null,
  }
)

const communicationLatencyLabel = computed(() =>
  communication.value.latency_ms != null
    ? `${Number(communication.value.latency_ms).toFixed(1)} ms`
    : '暂未上报'
)

const communicationMessageLabel = computed(() =>
  communication.value.last_message_at ? formatEpochTime(communication.value.last_message_at) : '暂未收到'
)

const sortedDriverInputs = computed(() =>
  [...store.driverInputs]
    .sort((a, b) => (Number(b.updated_at) || 0) - (Number(a.updated_at) || 0))
    .slice(0, 6)
)

const sortedAtoCommands = computed(() =>
  [...store.atoCommands]
    .sort((a, b) => (Number(b.updated_at) || 0) - (Number(a.updated_at) || 0))
    .slice(0, 6)
)

const signalReadinessNextStep = computed(() => {
  if (!store.connected && !store.connecting) return '请先确认 WebSocket 或 REST 快照是否已恢复。'
  if (!store.signals.length || !store.turnouts.length) return '优先检查后端是否推送 signals / switches 字段。'
  return '若冲突列表为空，可继续展开时间轴或站场下钻。'
})

watch(
  () => interlockingConflicts.value.length,
  (count) => {
    if (count > 0) turnoutPanelOpen.value = true
  },
  { immediate: true }
)

function toggleStation(stationId) {
  selectedStationId.value = selectedStationId.value === stationId ? null : stationId
}

function setSandboxMode(mode) {
  if (sandboxMode.value === mode) return
  sandboxMode.value = mode
  const label = sandboxModes.find((item) => item.value === mode)?.label ?? mode
  ui.showToast({
    type: 'info',
    title: `已切换到${label}`,
    message: mode === 'schematic'
      ? '此模式下可点击站名查看站场展开。'
      : '当前视角已切换，可继续核对线路态势。',
    duration: 1800,
  })
}

function requestPublishTrackInfo() {
  ui.requestConfirm({
    title: '确认发布当前线路数据到消息总线？',
    message: '该操作会调用后端 /api/v1/dashboard/publish-track-info，把当前缓存区段打包为 track_info 广播给其他模块。',
    confirmLabel: '立即发布',
    cancelLabel: '取消',
    onConfirm: () => store.publishTrackInfoMessage(),
  })
}

function isSegmentInStation(segment, stationRange) {
  if (!stationRange) return false
  if (segment.station_id) return segment.station_id === stationRange.station_id
  return isWithinExpandedRange(segmentCenter(segment), stationRange, 0)
}

function isWithinExpandedRange(position, stationRange, padding = 0) {
  if (position == null || !stationRange) return false
  return position >= stationRange.start - padding && position <= stationRange.end + padding
}

function segmentCenter(segment) {
  return ((segment.start ?? 0) + (segment.end ?? 0)) / 2
}

function maBarStyle(vehicle) {
  if (vehicle.ma_limit == null || !store.totalLength) {
    return {
      left: '0%',
      width: '0%',
      backgroundColor: store.vehicleColor(vehicle.vehicle_id),
    }
  }

  const left = vehiclePositionPercent(vehicle)
  const width = Math.max(0, vehicleMaPercent(vehicle) - left)
  return {
    left: `${left}%`,
    width: `${Math.min(100, width)}%`,
    backgroundColor: store.vehicleColor(vehicle.vehicle_id),
  }
}

function vehiclePositionPercent(vehicle) {
  if (!store.totalLength) return 0
  return Math.max(0, Math.min(100, (vehicle.position / store.totalLength) * 100))
}

function vehicleMaPercent(vehicle) {
  if (!store.totalLength || vehicle.ma_limit == null) return vehiclePositionPercent(vehicle)
  return Math.max(0, Math.min(100, (vehicle.ma_limit / store.totalLength) * 100))
}

function isReverseState(state) {
  return state === 'reverse' || state === 'diverging'
}

function permissionLabel(permission) {
  if (permission === 'allow') return '允许通过'
  if (permission === 'restricted') return '受限通过'
  if (permission === 'stop') return '停车'
  return permission ?? '—'
}

function signalStateLabel(state) {
  if (state === 'red') return '红灯'
  if (state === 'yellow') return '黄灯'
  if (state === 'green') return '绿灯'
  return state ?? '—'
}

function aspectLabel(aspect) {
  if (aspect === 'red') return '红灯'
  if (aspect === 'yellow') return '黄灯'
  if (aspect === 'green') return '绿灯'
  return aspect ?? '未知'
}

function reasonLabel(reason) {
  if (!reason) return '—'
  return {
    route_locked_conflict: '进路锁闭冲突',
    switch_locked_conflict: '道岔锁闭冲突',
    route_available: '进路可用',
    route_locked: '进路已锁闭',
    front_vehicle_protection: '前车防护',
    route_end: '进路终点',
  }[reason] ?? reason
}

function nearestSignal(position) {
  let best = null
  let bestDistance = Number.POSITIVE_INFINITY

  for (const signal of store.signals) {
    const distance = Math.abs((signal.position ?? 0) - (position ?? 0))
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

  for (const turnout of store.turnouts) {
    const distance = Math.abs((turnout.position ?? 0) - segmentCenter(segment))
    if (distance < bestDistance) {
      best = turnout
      bestDistance = distance
    }
  }

  return best ? best.turnout_id : '未关联'
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
