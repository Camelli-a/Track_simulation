<template>
  <div class="space-y-5">
    <header class="app-panel">
      <div class="app-section-head">
        <div>
          <p class="app-section-kicker">Cab Console</p>
          <h2 class="text-xl font-semibold text-slate-100">列车驾驶室</h2>
          <p class="app-section-copy">
            聚焦单车驾驶判断与人工干预，把目标速度、MA 裕量、制动曲线和控制结果放在同一视线范围内。
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="app-chip">实时快照 {{ store.vehicles.length }} 列</span>
          <span class="app-chip">管理列表 {{ store.managedTrains.length }} 列</span>
          <span class="app-chip">{{ managementModeLabel }}</span>
          <ConnectionBadge :connected="store.connected" :data-stale="store.dataStale" />
        </div>
      </div>
    </header>

    <section class="app-panel">
      <div class="app-section-head">
        <div>
          <p class="app-section-kicker">Vehicle Management</p>
          <h3 class="app-section-title">车辆实例管理</h3>
          <p class="app-section-copy">
            这里直接调用 `POST /api/v1/vehicle/manage` 与 `GET /api/v1/vehicle/trains`。页面以管理接口返回的 `trains` 为准，不用 dashboard 演示快照反推真实车辆实例。
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            type="button"
            class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 transition hover:border-white/20 hover:bg-white/10 disabled:opacity-50"
            :disabled="store.managedTrainsLoading"
            @click="refreshManagedTrains"
          >
            {{ store.managedTrainsLoading ? '刷新中...' : '刷新车辆列表' }}
          </button>
          <button
            type="button"
            class="rounded-xl border border-amber-700/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-200 transition hover:border-amber-500"
            :disabled="store.managedTrainsLoading || !canManageVehicles"
            @click="requestResetTrains"
          >
            重置车辆
          </button>
          <button
            type="button"
            class="rounded-xl border border-red-700/40 bg-red-950/30 px-3 py-2 text-xs text-red-200 transition hover:border-red-500"
            :disabled="store.managedTrainsLoading || !store.managedTrains.length || !canManageVehicles"
            @click="requestClearTrains"
          >
            清空车辆
          </button>
        </div>
      </div>

      <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div class="app-metric-tile">
          <p class="app-metric-label">管理中的车辆</p>
          <p class="app-metric-value">{{ store.managedTrains.length }}</p>
          <p class="mt-2 text-xs text-slate-500">以 `/vehicle/trains` 或 manage 返回体为准。</p>
        </div>
        <div class="app-metric-tile">
          <p class="app-metric-label">实时快照车辆</p>
          <p class="app-metric-value">{{ store.vehicles.length }}</p>
          <p class="mt-2 text-xs text-slate-500">来自 `/ws/dashboard` 或 snapshot 兜底。</p>
        </div>
        <div class="app-metric-tile">
          <p class="app-metric-label">仅管理未上屏</p>
          <p class="app-metric-value">{{ store.managedOnlyTrains.length }}</p>
          <p class="mt-2 text-xs text-slate-500">常见于 `DATA_SOURCE=mock` 下演示快照未跟随管理接口。</p>
        </div>
        <div class="app-metric-tile">
          <p class="app-metric-label">最近同步</p>
          <p class="mt-1 text-sm text-slate-200">{{ managedSyncText }}</p>
          <p class="mt-2 text-xs text-slate-500">{{ manageStatusHint }}</p>
        </div>
      </div>

      <div class="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-[1.05fr_1.35fr]">
        <div class="rounded-[1.1rem] border border-white/10 bg-black/10 px-4 py-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h4 class="text-sm font-semibold text-slate-100">添加 / 删除 / 重置</h4>
              <p class="mt-1 text-xs text-slate-500">`train_index` 可留空，后端会自动选择最小空闲槽位。</p>
            </div>
            <span class="rounded-full border border-sky-500/20 bg-sky-500/10 px-3 py-1 text-[11px] text-sky-200">
              槽位 > 20 仍可存在，只是不进入固定 UDP 帧
            </span>
          </div>

          <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <label class="space-y-2 text-sm text-slate-300">
              <span>车辆编号</span>
              <input
                v-model.trim="manageForm.vehicle_id"
                type="text"
                class="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
                placeholder="例如 TRAIN-011"
              >
            </label>
            <label class="space-y-2 text-sm text-slate-300">
              <span>槽位编号</span>
              <input
                v-model.number="manageForm.train_index"
                type="number"
                min="1"
                class="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
                placeholder="留空自动分配"
              >
            </label>
            <label class="space-y-2 text-sm text-slate-300">
              <span>线路编号</span>
              <input
                v-model.trim="manageForm.line_id"
                type="text"
                class="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
                placeholder="LINE-1"
              >
            </label>
            <label class="space-y-2 text-sm text-slate-300">
              <span>初始位置 m</span>
              <input
                v-model.number="manageForm.position"
                type="number"
                min="0"
                step="1"
                class="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
                placeholder="1200"
              >
            </label>
          </div>

          <div class="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              class="rounded-xl border border-emerald-700/50 bg-emerald-950/40 px-4 py-2.5 text-sm font-medium text-emerald-200 transition hover:border-emerald-500 disabled:opacity-45"
              :disabled="store.managedTrainsLoading || !canManageVehicles"
              @click="submitAddTrain"
            >
              添加车辆
            </button>
            <button
              type="button"
              class="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:border-white/20 hover:bg-white/10 disabled:opacity-45"
              :disabled="store.managedTrainsLoading"
              @click="fillNextTrainSuggestion"
            >
              自动生成下一辆
            </button>
          </div>

          <div class="mt-4 rounded-[1rem] border border-white/10 bg-slate-950/40 px-4 py-3 text-xs">
            <p class="text-slate-500">最近管理反馈</p>
            <p class="mt-2 text-sm" :class="lastManageActionClass">{{ lastManageActionText }}</p>
            <p v-if="store.lastManageAction?.result" class="mt-2 text-xs text-slate-500">
              {{ manageResultSummary }}
            </p>
          </div>

          <div
            v-if="!canManageVehicles"
            class="mt-4 rounded-[1rem] border border-amber-900/50 bg-amber-950/20 px-4 py-3 text-sm text-amber-100"
          >
            你当前本地运行的后端还是旧版车辆接口：有 `/vehicle/status`，但还没更新到最新的 `/vehicle/trains` 和 `/vehicle/manage`。因此这里可以看兼容兜底列表，但暂时不能直接增删车辆。
          </div>
        </div>

        <div class="rounded-[1.1rem] border border-white/10 bg-black/10 px-4 py-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h4 class="text-sm font-semibold text-slate-100">管理列表</h4>
              <p class="mt-1 text-xs text-slate-500">删除操作优先按 `vehicle_id`；若后端只返回槽位，也可按 `train_index` 删除。</p>
            </div>
            <span class="text-[11px] text-slate-500">
              {{ store.managedTrains.length }} 列
            </span>
          </div>

          <div v-if="store.managedTrainsError" class="mt-3 rounded-xl border border-red-900/50 bg-red-950/20 px-3 py-3 text-sm text-red-200">
            {{ store.managedTrainsError }}
          </div>

          <div v-if="store.managedTrains.length" class="mt-4 app-table-shell">
            <table class="app-table">
              <thead>
                <tr>
                  <th class="text-left">车辆</th>
                  <th class="text-right">槽位</th>
                  <th class="text-right">位置</th>
                  <th class="text-right">模式</th>
                  <th class="text-right">状态</th>
                  <th class="text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="train in store.managedTrains" :key="train.vehicle_id ?? train.train_index">
                  <td>
                    <div class="flex items-center gap-2">
                      <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: store.vehicleColor(train.vehicle_id ?? `slot-${train.train_index}`) }" />
                      <div>
                        <p class="text-slate-100">{{ train.vehicle_id ?? `槽位 ${train.train_index}` }}</p>
                        <p class="text-[11px] text-slate-500">{{ train.line_id ?? 'LINE-1' }}</p>
                      </div>
                    </div>
                  </td>
                  <td class="text-right text-slate-400">{{ train.train_index ?? '—' }}</td>
                  <td class="text-right text-slate-400">{{ Math.round(train.position ?? 0) }} m</td>
                  <td class="text-right text-slate-400">{{ modeLabel(train.mode) }}</td>
                  <td class="text-right">
                    <span
                      class="rounded-full px-2 py-0.5 text-[11px]"
                      :class="store.managedOnlyTrains.some((item) => item.vehicle_id === train.vehicle_id)
                        ? 'bg-amber-950 text-amber-300'
                        : 'bg-emerald-950 text-emerald-300'"
                    >
                      {{ store.managedOnlyTrains.some((item) => item.vehicle_id === train.vehicle_id) ? '已管理未上屏' : '已上屏' }}
                    </span>
                  </td>
                  <td class="text-right">
                    <div class="flex justify-end gap-2">
                      <button
                        v-if="store.vehicles.some((vehicle) => vehicle.vehicle_id === train.vehicle_id)"
                        type="button"
                        class="rounded-lg border border-white/10 px-2.5 py-1 text-[11px] text-slate-300 transition hover:border-white/20 hover:bg-white/5"
                        @click="store.selectVehicle(train.vehicle_id)"
                      >
                        关注
                      </button>
                      <button
                        type="button"
                        class="rounded-lg border border-red-700/50 px-2.5 py-1 text-[11px] text-red-200 transition hover:border-red-500 hover:bg-red-950/20"
                        @click="requestRemoveTrain(train)"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else class="mt-4 rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500">
            当前还没有管理中的车辆。你可以先添加一辆车，或者用“重置车辆”恢复默认 10 列。
          </div>
        </div>
      </div>
    </section>

    <PageEmptyState
      v-if="!store.vehicles.length"
      title="实时驾驶快照尚未到达"
      description="车辆管理接口可以单独工作，但当前还没有收到列车位置、速度和运行模式快照，所以驾驶监督、制动曲线和控制历史暂时无法展开。"
      next-step="如果上面的管理列表已经有车，请继续检查 `/ws/dashboard` 或 `/api/v1/dashboard/snapshot` 是否同步输出这些车辆；`DATA_SOURCE=mock` 下也要注意 dashboard 演示数据可能不跟随管理接口。"
    />

    <template v-else>
      <section class="grid grid-cols-1 gap-4 xl:grid-cols-[1.1fr_1.2fr]">
        <div class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Vehicle Select</p>
              <h3 class="app-section-title">车辆选择</h3>
              <p class="app-section-copy">切换关注车辆后，下方监督指标、手动控车和控制历史会同步联动。</p>
            </div>
            <span class="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-400">
              共 {{ store.vehicles.length }} 列
            </span>
          </div>

          <div class="mt-4 flex flex-wrap gap-2">
            <button
              v-for="vehicle in store.vehicles"
              :key="vehicle.vehicle_id"
              type="button"
              class="rounded-xl border px-3 py-2 text-sm transition-all"
              :class="store.selectedVehicleId === vehicle.vehicle_id
                ? 'border-cyan-400/60 bg-cyan-400/10 text-cyan-100'
                : 'border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-slate-200'"
              @click="store.selectVehicle(vehicle.vehicle_id)"
            >
              <span class="mr-2 inline-block h-2 w-2 rounded-full" :style="{ backgroundColor: store.vehicleColor(vehicle.vehicle_id) }" />
              {{ vehicle.vehicle_id }}
            </button>
          </div>
        </div>

        <div v-if="active" class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Current Vehicle</p>
              <h3 class="app-section-title">{{ active.vehicle_id }} 当前状态摘要</h3>
              <p class="app-section-copy">先确认模式、紧急制动状态和数据新鲜度，再进入速度与 MA 判断。</p>
            </div>
            <div class="flex flex-wrap gap-2 text-xs">
              <span class="rounded-full px-3 py-1" :class="active.mode === 'manual' ? 'bg-orange-950 text-orange-300' : 'bg-sky-950 text-sky-300'">
                {{ modeLabel(active.mode) }}
              </span>
              <span v-if="active.emergency_brake" class="rounded-full bg-red-950 px-3 py-1 text-red-300">ATP 紧急制动</span>
              <span class="rounded-full border border-white/10 px-3 py-1 text-slate-400">{{ heartbeatLabel(active) }}</span>
            </div>
          </div>

          <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-[0.9fr_1.1fr]">
            <div class="rounded-[1.15rem] border border-white/10 bg-black/10 px-4 py-4">
              <SpeedGauge :speed="active.speed" :limit="active.target_speed ?? active.ma_speed_limit ?? 80" />
            </div>

            <div class="grid grid-cols-2 gap-3 xl:grid-cols-3">
              <div class="app-metric-tile">
                <p class="app-metric-label">当前位置</p>
                <p class="app-metric-value">{{ Math.round(active.position) }} m</p>
              </div>
              <div class="app-metric-tile">
                <p class="app-metric-label">停车距离</p>
                <p class="app-metric-value">{{ active.stop_distance != null ? `${active.stop_distance.toFixed(1)} m` : '—' }}</p>
              </div>
              <div class="app-metric-tile">
                <p class="app-metric-label">协议限速</p>
                <p class="app-metric-value">{{ active.ma_speed_limit != null ? `${active.ma_speed_limit} km/h` : '—' }}</p>
              </div>
              <div class="app-metric-tile">
                <p class="app-metric-label">约束原因</p>
                <p class="mt-1 text-sm text-slate-200">{{ reasonLabel(active.ma_reason) }}</p>
              </div>
              <div class="app-metric-tile">
                <p class="app-metric-label">管理槽位</p>
                <p class="app-metric-value">{{ currentVehicleSlot }}</p>
              </div>
              <div class="app-metric-tile">
                <p class="app-metric-label">当前区段 / 边</p>
                <p class="mt-1 text-sm text-slate-200">{{ currentSectionText }}</p>
                <p class="mt-1 text-xs text-slate-500">{{ currentEdgeText }}</p>
              </div>
              <div class="app-metric-tile">
                <p class="app-metric-label">运行方向</p>
                <p class="mt-1 text-sm text-slate-200">{{ currentDirectionText }}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section v-if="active" class="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <article class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Speed Supervision</p>
              <h3 class="app-section-title">目标速度 vs 实际速度</h3>
              <p class="app-section-copy">这是 ATO 监督的第一判断面板，用来快速识别速度偏差和超速风险。</p>
            </div>
            <span
              class="rounded-full px-3 py-1 text-xs"
              :class="speedDelta > 0 ? 'bg-red-950 text-red-300' : 'bg-emerald-950 text-emerald-300'"
            >
              {{ speedDelta > 0 ? `超出 ${speedDelta.toFixed(1)} km/h` : `低于 ${Math.abs(speedDelta).toFixed(1)} km/h` }}
            </span>
          </div>

          <div class="mt-5 grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">实际速度</p>
              <p class="mt-2 text-3xl font-semibold text-white">{{ active.speed }}</p>
              <p class="mt-1 text-xs text-slate-500">km/h</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">目标速度</p>
              <p class="mt-2 text-3xl font-semibold text-cyan-300">{{ active.target_speed ?? '--' }}</p>
              <p class="mt-1 text-xs text-slate-500">km/h</p>
            </div>
          </div>

          <div class="mt-4">
            <div class="flex items-center justify-between text-[11px] text-slate-500">
              <span>速度利用率</span>
              <span>{{ speedUsage.toFixed(0) }}%</span>
            </div>
            <div class="mt-2 h-2 overflow-hidden rounded-full bg-slate-900">
              <div
                class="h-full rounded-full transition-all duration-300"
                :class="speedUsage > 100 ? 'bg-red-500' : speedUsage > 85 ? 'bg-amber-400' : 'bg-emerald-400'"
                :style="{ width: `${Math.min(100, speedUsage)}%` }"
              />
            </div>
          </div>
        </article>

        <article class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Movement Authority</p>
              <h3 class="app-section-title">MA 裕量</h3>
              <p class="app-section-copy">这是 ATP 安全防线的核心面板，反映当前列车距离授权边界还剩多少安全空间。</p>
            </div>
            <span
              class="rounded-full px-3 py-1 text-xs"
              :class="maRemaining != null && maRemaining < 120 ? 'bg-amber-950 text-amber-300' : 'bg-sky-950 text-sky-300'"
            >
              {{ maRemainingText }}
            </span>
          </div>

          <div class="mt-5 grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">当前位置</p>
              <p class="mt-2 text-2xl font-semibold text-white">{{ Math.round(active.position) }}</p>
              <p class="mt-1 text-xs text-slate-500">m</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">MA 边界</p>
              <p class="mt-2 text-2xl font-semibold text-cyan-300">{{ active.ma_limit ?? '--' }}</p>
              <p class="mt-1 text-xs text-slate-500">m</p>
            </div>
          </div>

          <div class="mt-4">
            <div class="flex items-center justify-between text-[11px] text-slate-500">
              <span>授权使用率</span>
              <span>{{ maUsage.toFixed(0) }}%</span>
            </div>
            <div class="mt-2 h-2 overflow-hidden rounded-full bg-slate-900">
              <div
                class="h-full rounded-full transition-all duration-300"
                :class="maUsage > 90 ? 'bg-red-500' : maUsage > 70 ? 'bg-amber-400' : 'bg-sky-400'"
                :style="{ width: `${Math.min(100, maUsage)}%` }"
              />
            </div>
          </div>

          <div class="mt-4 grid grid-cols-2 gap-3 text-xs">
            <div class="app-metric-tile">
              <p class="app-metric-label">协议进路</p>
              <p class="mt-1 text-slate-200">{{ active.ma_route_id ?? '—' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">运行许可</p>
              <p class="mt-1" :class="permissionClass(active.ma_permission)">{{ permissionLabel(active.ma_permission) }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">防护信号</p>
              <p class="mt-1 text-slate-200">{{ signalStateLabel(active.ma_signal_state) }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">前车 / 安全间距</p>
              <p class="mt-1 text-slate-200">
                {{ active.ma_front_vehicle_id ?? '无前车' }}
                <span v-if="active.ma_safe_distance != null" class="text-slate-500"> · {{ active.ma_safe_distance }} m</span>
              </p>
            </div>
          </div>
        </article>

        <article class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Manual Control</p>
              <h3 class="app-section-title">手动控车与指令反馈</h3>
              <p class="app-section-copy">牵引、制动可直接下发；紧急制动会先确认，结果反馈会同步写入下方历史。</p>
            </div>
            <span
              class="rounded-full px-3 py-1 text-xs"
              :class="canManualControl ? 'bg-orange-950 text-orange-300' : 'bg-slate-800 text-slate-300'"
            >
              {{ canManualControl ? '允许手动控车' : '当前非手动模式' }}
            </span>
          </div>

          <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <label class="space-y-2 text-sm text-slate-300">
              <span>手动级位</span>
              <select
                v-model.number="manualControl.level"
                class="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
              >
                <option v-for="level in [1, 2, 3, 4]" :key="level" :value="level">L{{ level }}</option>
              </select>
            </label>
            <label class="space-y-2 text-sm text-slate-300">
              <span>运行方向</span>
              <select
                v-model="manualControl.direction"
                class="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
              >
                <option value="forward">前进</option>
                <option value="neutral">空挡</option>
                <option value="backward">后退</option>
              </select>
            </label>
          </div>

          <div class="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              class="rounded-xl border border-emerald-700/50 bg-emerald-950/40 px-4 py-2.5 text-sm font-medium text-emerald-200 transition hover:border-emerald-500 disabled:cursor-not-allowed disabled:opacity-45"
              :disabled="!canManualControl"
              @click="sendManualCommand('traction')"
            >
              牵引 L{{ manualControl.level }}
            </button>
            <button
              type="button"
              class="rounded-xl border border-amber-700/50 bg-amber-950/40 px-4 py-2.5 text-sm font-medium text-amber-200 transition hover:border-amber-500 disabled:cursor-not-allowed disabled:opacity-45"
              :disabled="!canManualControl"
              @click="sendManualCommand('brake')"
            >
              制动 L{{ manualControl.level }}
            </button>
            <button
              type="button"
              class="rounded-xl border border-red-700/50 bg-red-950/40 px-4 py-2.5 text-sm font-medium text-red-200 transition hover:border-red-500 disabled:cursor-not-allowed disabled:opacity-45"
              :disabled="!active"
              @click="sendManualCommand('emergency_brake')"
            >
              紧急制动
            </button>
          </div>

          <div class="mt-4 rounded-[1rem] border border-white/10 bg-black/10 px-4 py-3 text-xs">
            <p class="text-slate-500">最近反馈</p>
            <p class="mt-2 text-sm" :class="lastControlFeedbackClass">{{ lastControlFeedbackText }}</p>
          </div>

          <div class="mt-4 rounded-[1rem] border border-white/10 bg-black/10 px-4 py-4">
            <div class="flex items-center justify-between gap-3">
              <div>
                <h4 class="text-sm font-semibold text-slate-100">ATO 目标下发</h4>
                <p class="mt-1 text-xs text-slate-500">这组参数直接对应后端 `/api/v1/vehicle/control` 中的 `command=ato` 能力。</p>
              </div>
              <span class="rounded-full border border-sky-500/20 bg-sky-500/10 px-3 py-1 text-[11px] text-sky-200">
                ATO / ATP 联调
              </span>
            </div>

            <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
              <label class="space-y-2 text-sm text-slate-300">
                <span>目标速度 km/h</span>
                <input
                  v-model.number="atoForm.target_speed"
                  type="number"
                  min="0"
                  step="1"
                  class="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
                >
              </label>
              <label class="space-y-2 text-sm text-slate-300">
                <span>目标位置 m</span>
                <input
                  v-model.number="atoForm.target_position"
                  type="number"
                  min="0"
                  step="1"
                  class="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
                  placeholder="可留空，仅按目标速度运行"
                >
              </label>
              <label class="space-y-2 text-sm text-slate-300">
                <span>牵引级位</span>
                <select
                  v-model.number="atoForm.traction_level"
                  class="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
                >
                  <option v-for="level in [0, 1, 2, 3, 4]" :key="`ato-t-${level}`" :value="level">L{{ level }}</option>
                </select>
              </label>
              <label class="space-y-2 text-sm text-slate-300">
                <span>制动级位</span>
                <select
                  v-model.number="atoForm.brake_level"
                  class="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
                >
                  <option v-for="level in [0, 1, 2, 3, 4]" :key="`ato-b-${level}`" :value="level">L{{ level }}</option>
                </select>
              </label>
            </div>

            <label class="mt-3 block space-y-2 text-sm text-slate-300">
              <span>下发原因</span>
              <input
                v-model.trim="atoForm.reason"
                type="text"
                class="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
                placeholder="cab_console_ato"
              >
            </label>

            <div class="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                class="rounded-xl border border-sky-700/50 bg-sky-950/40 px-4 py-2.5 text-sm font-medium text-sky-200 transition hover:border-sky-500"
                :disabled="!active"
                @click="sendAtoCommand"
              >
                下发 ATO 目标
              </button>
              <button
                type="button"
                class="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:border-white/20 hover:bg-white/10"
                :disabled="!active"
                @click="syncAtoFormFromActive"
              >
                读取当前推荐值
              </button>
            </div>
          </div>

          <div class="mt-4">
            <div class="flex items-center justify-between gap-3">
              <h4 class="text-sm font-semibold text-slate-100">最近控制指令历史</h4>
              <span class="text-[11px] text-slate-500">最近 {{ recentControls.length }} 条</span>
            </div>

            <div v-if="!recentControls.length" class="mt-3 rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-6 text-center text-sm text-slate-500">
              当前列车还没有控制指令记录
            </div>

            <div v-else class="mt-3 space-y-2">
              <div
                v-for="entry in recentControls"
                :key="entry.id"
                class="rounded-xl border px-4 py-3"
                :class="entry.status === 'error'
                  ? 'border-red-900/60 bg-red-950/20'
                  : entry.status === 'ok'
                    ? 'border-emerald-900/60 bg-emerald-950/20'
                    : 'border-sky-900/60 bg-sky-950/20'"
              >
                <div class="flex items-center justify-between gap-3">
                  <span class="text-sm font-medium text-slate-100">{{ entry.label }}</span>
                  <span class="text-[11px]" :class="entry.status === 'error' ? 'text-red-300' : entry.status === 'ok' ? 'text-emerald-300' : 'text-sky-300'">
                    {{ controlStatusLabel(entry.status) }}
                  </span>
                </div>
                <p class="mt-1 text-xs text-slate-400">
                  {{ entry.vehicleId }} · {{ controlEntrySummary(entry) }} · {{ formatTime(entry.at) }}
                </p>
                <p v-if="entry.error" class="mt-2 text-xs text-red-300">{{ entry.error }}</p>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section v-if="active" class="app-panel-compact">
        <EChartsContainer :option="brakingCurveOption" height="300px" />
      </section>

      <section v-if="active" class="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <article class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">Driver Input Echo</p>
              <h3 class="app-section-title">最近驾驶输入</h3>
              <p class="app-section-copy">用来核对手动控车指令有没有真的写入后端快照。</p>
            </div>
            <span class="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-400">
              {{ activeDriverInput ? formatProtocolTimestamp(activeDriverInput.updated_at) : '等待回显' }}
            </span>
          </div>

          <div v-if="activeDriverInput" class="mt-4 grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">来源</p>
              <p class="mt-1 text-sm text-slate-200">{{ activeDriverInput.source ?? '—' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">控制模式</p>
              <p class="mt-1 text-sm text-slate-200">{{ activeDriverInput.control_mode ?? '—' }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">牵引级位</p>
              <p class="app-metric-value">{{ activeDriverInput.traction_level ?? 0 }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">制动级位</p>
              <p class="app-metric-value">{{ activeDriverInput.brake_level ?? 0 }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">方向</p>
              <p class="mt-1 text-sm text-slate-200">{{ directionText(activeDriverInput.direction) }}</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">紧急按钮</p>
              <p class="mt-1 text-sm" :class="activeDriverInput.emergency_button ? 'text-red-300' : 'text-emerald-300'">
                {{ activeDriverInput.emergency_button ? '已按下' : '正常' }}
              </p>
            </div>
          </div>

          <div v-else class="mt-4 rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-6 text-center text-sm text-slate-500">
            当前车辆还没有收到驾驶输入回显
          </div>
        </article>

        <article class="app-panel">
          <div class="app-section-head">
            <div>
              <p class="app-section-kicker">ATO Echo</p>
              <h3 class="app-section-title">最近 ATO 命令</h3>
              <p class="app-section-copy">用来核对目标速度、目标位置和调速理由是否已经被后端记录。</p>
            </div>
            <span class="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-400">
              {{ activeAtoCommand ? formatProtocolTimestamp(activeAtoCommand.updated_at) : '等待回显' }}
            </span>
          </div>

          <div v-if="activeAtoCommand" class="mt-4 grid grid-cols-2 gap-3">
            <div class="app-metric-tile">
              <p class="app-metric-label">目标速度</p>
              <p class="app-metric-value">{{ activeAtoCommand.target_speed ?? 0 }}</p>
              <p class="mt-1 text-xs text-slate-500">km/h</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">目标位置</p>
              <p class="app-metric-value">{{ activeAtoCommand.target_position != null ? Math.round(activeAtoCommand.target_position) : '—' }}</p>
              <p class="mt-1 text-xs text-slate-500">m</p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">牵引 / 制动</p>
              <p class="mt-1 text-sm text-slate-200">
                T{{ activeAtoCommand.traction_level ?? 0 }} · B{{ activeAtoCommand.brake_level ?? 0 }}
              </p>
            </div>
            <div class="app-metric-tile">
              <p class="app-metric-label">原因</p>
              <p class="mt-1 text-sm text-slate-200">{{ activeAtoCommand.reason ?? '—' }}</p>
            </div>
          </div>

          <div v-else class="mt-4 rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-6 text-center text-sm text-slate-500">
            当前车辆还没有收到 ATO 命令回显
          </div>
        </article>
      </section>

      <ParkingPrecision
        :current-error="store.currentStopErrorCm"
        :records="store.parkingRecords"
      />

      <section class="app-panel">
        <div class="app-section-head">
          <div>
            <p class="app-section-kicker">Fleet Snapshot</p>
            <h3 class="app-section-title">全车队列表</h3>
            <p class="app-section-copy">这里只保留判断车队状态所需的最小列集；若要看全线运行轨迹，请切回“全线态势”。</p>
          </div>
          <span class="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-400">
            按点击切换当前关注列车
          </span>
        </div>

        <div class="app-table-shell">
          <table class="app-table">
            <thead>
              <tr>
                <th class="text-left">车辆</th>
                <th class="text-right">模式</th>
                <th class="text-right">速度</th>
                <th class="text-right">MA</th>
                <th class="text-right">状态</th>
                <th class="text-right">上次心跳</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="vehicle in store.vehicles"
                :key="vehicle.vehicle_id"
                class="cursor-pointer"
                :class="store.selectedVehicleId === vehicle.vehicle_id ? 'bg-cyan-950/10' : ''"
                @click="store.selectVehicle(vehicle.vehicle_id)"
              >
                <td>
                  <span class="inline-flex items-center gap-2">
                    <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: store.vehicleColor(vehicle.vehicle_id) }" />
                    {{ vehicle.vehicle_id }}
                  </span>
                </td>
                <td class="text-right text-slate-400">{{ modeLabel(vehicle.mode) }}</td>
                <td class="text-right" :class="vehicle.speed > (vehicle.target_speed ?? 80) ? 'text-red-300' : 'text-slate-300'">
                  {{ vehicle.speed }} km/h
                </td>
                <td class="text-right text-slate-400">{{ vehicle.ma_limit != null ? `${Math.round(vehicle.ma_limit)} m` : '—' }}</td>
                <td class="text-right">
                  <span v-if="vehicle.emergency_brake" class="text-xs text-red-300">EB</span>
                  <span v-else class="text-xs text-emerald-300">运行</span>
                </td>
                <td class="text-right text-slate-400">{{ heartbeatLabel(vehicle) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { modeLabel } from '@/adapters/simulation'
import { usePageSimulation } from '@/composables/usePageSimulation'
import ConnectionBadge from '@/components/ConnectionBadge.vue'
import EChartsContainer from '@/components/EChartsContainer.vue'
import PageEmptyState from '@/components/PageEmptyState.vue'
import ParkingPrecision from '@/components/ParkingPrecision.vue'
import SpeedGauge from '@/components/SpeedGauge.vue'
import { useUiStore } from '@/stores/ui'

const store = usePageSimulation()
const ui = useUiStore()
const active = computed(() => store.selectedVehicle)
const canManualControl = computed(() => active.value?.mode === 'manual')
const now = ref(Date.now())
const manualControl = reactive({
  level: 1,
  direction: 'forward',
})
const atoForm = reactive({
  target_speed: 0,
  target_position: null,
  traction_level: 2,
  brake_level: 0,
  reason: 'cab_console_ato',
})
const manageForm = reactive({
  vehicle_id: '',
  train_index: null,
  line_id: 'LINE-1',
  position: 0,
})
const activeManagedTrain = computed(() =>
  store.managedTrains.find((train) => train.vehicle_id === active.value?.vehicle_id) ?? null
)
const activeDriverInput = computed(() =>
  store.driverInputs.find((input) => input.vehicle_id === active.value?.vehicle_id) ?? null
)
const activeAtoCommand = computed(() =>
  store.atoCommands.find((command) => command.vehicle_id === active.value?.vehicle_id) ?? null
)

const canManageVehicles = computed(() => store.vehicleManagementMode === 'full')
const managementModeLabel = computed(() => {
  if (store.vehicleManagementMode === 'full') return '管理接口已接入'
  if (store.vehicleManagementMode === 'status_fallback') return '旧后端兼容模式'
  if (store.vehicleManagementMode === 'unavailable') return '车辆管理接口不可用'
  return '管理接口待检测'
})

let timer = null

onMounted(() => {
  timer = window.setInterval(() => {
    now.value = Date.now()
  }, 1000)
  store.hydrateManagedTrains({ silent: true })
    .catch(() => [])
    .finally(() => {
      if (!manageForm.vehicle_id && !manageForm.train_index) {
        fillNextTrainSuggestion()
      }
    })
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})

watch(
  () => active.value?.vehicle_id,
  () => {
    syncAtoFormFromActive()
  },
  { immediate: true },
)

const speedDelta = computed(() => {
  if (!active.value) return 0
  return active.value.speed - (active.value.target_speed ?? active.value.speed)
})

const speedUsage = computed(() => {
  if (!active.value || !active.value.target_speed) return Math.min(100, active.value?.speed ?? 0)
  return Math.max(0, (active.value.speed / active.value.target_speed) * 100)
})

const maRemaining = computed(() => {
  if (!active.value || active.value.ma_limit == null) return null
  return active.value.ma_limit - active.value.position
})

const maRemainingText = computed(() => {
  if (maRemaining.value == null) return '暂无 MA'
  return `${Math.max(0, maRemaining.value).toFixed(1)} m`
})

const maUsage = computed(() => {
  if (!active.value || active.value.ma_limit == null || active.value.ma_limit <= 0) return 0
  return Math.max(0, (active.value.position / active.value.ma_limit) * 100)
})

const currentVehicleSlot = computed(() =>
  active.value?.train_index ?? activeManagedTrain.value?.train_index ?? '—'
)

const currentSectionText = computed(() => {
  if (!active.value) return '—'
  return active.value.section_id ?? '尚未上报 section_id'
})

const currentEdgeText = computed(() => {
  if (!active.value) return '—'
  const edge = active.value.edge_id != null ? `edge ${active.value.edge_id}` : 'edge 未知'
  const offset = active.value.edge_offset_m != null ? `偏移 ${Number(active.value.edge_offset_m).toFixed(1)} m` : '偏移未上报'
  return `${edge} · ${offset}`
})

const currentDirectionText = computed(() =>
  directionCodeLabel(active.value?.direction_code)
)

const managedSyncText = computed(() => {
  if (!store.lastManagedSyncAt) return '尚未同步'
  const delta = Math.max(0, now.value - store.lastManagedSyncAt)
  if (delta < 1000) return '刚刚刷新'
  if (delta < 60000) return `${Math.floor(delta / 1000)} 秒前`
  return `${Math.floor(delta / 60000)} 分钟前`
})

const manageStatusHint = computed(() => {
  if (store.managedTrainsLoading) return '正在请求 `/vehicle/trains`'
  if (store.managedTrainsError) return '最近一次同步失败，请看上方错误提示'
  if (store.liveOnlyVehicles.length) return `有 ${store.liveOnlyVehicles.length} 列只出现在实时快照中`
  return '管理列表与实时快照已完成一次对照'
})

const lastManageActionText = computed(() => {
  const action = store.lastManageAction
  if (!action) return '暂未发送车辆管理请求'
  if (action.ok) {
    return `${manageActionLabel(action.type)}已完成${action.published === false ? '，但消息总线未发布' : ''}`
  }
  return action.reason ?? `${manageActionLabel(action.type)}失败`
})

const lastManageActionClass = computed(() => {
  const action = store.lastManageAction
  if (!action) return 'text-slate-400'
  return action.ok ? (action.published === false ? 'text-amber-300' : 'text-emerald-300') : 'text-red-300'
})

const manageResultSummary = computed(() => {
  const result = store.lastManageAction?.result
  if (!result) return ''
  const items = [
    result.vehicle_id ? `车辆 ${result.vehicle_id}` : null,
    result.train_index != null ? `槽位 ${result.train_index}` : null,
    result.position != null ? `位置 ${Math.round(result.position)} m` : null,
    result.line_id ? `线路 ${result.line_id}` : null,
  ].filter(Boolean)
  return items.join(' · ')
})

const recentControls = computed(() => {
  const all = store.controlHistory
  if (!active.value) return all.slice(0, 6)
  const own = all.filter((entry) => entry.vehicleId === active.value.vehicle_id)
  return (own.length ? own : all).slice(0, 6)
})

const lastControlFeedbackText = computed(() => {
  const latest = recentControls.value[0]
  if (!latest) return '暂未发送控制指令'
  if (latest.status === 'ok') return `${latest.label} 已执行`
  if (latest.status === 'error') return latest.error ?? `${latest.label} 失败`
  return `${latest.label} 发送中`
})

const lastControlFeedbackClass = computed(() => {
  const latest = recentControls.value[0]
  if (!latest) return 'text-slate-400'
  if (latest.status === 'ok') return 'text-emerald-300'
  if (latest.status === 'error') return 'text-red-300'
  return 'text-sky-300'
})

const brakingCurveOption = computed(() => {
  if (!active.value) {
    return {
      title: {
        text: '制动曲线',
        textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
      },
      xAxis: { show: false, type: 'value' },
      yAxis: { show: false, type: 'value' },
      series: [],
    }
  }

  const currentSpeed = Math.max(0, active.value.speed ?? 0)
  const stopDistance = Math.max(active.value.stop_distance ?? maRemaining.value ?? 220, 40)
  const speedMs = currentSpeed / 3.6
  const decel = speedMs > 0
    ? Math.max(0.35, Math.min(1.35, (speedMs * speedMs) / (2 * stopDistance)))
    : 0.45
  const points = []
  const markers = []

  for (let index = 0; index <= 20; index += 1) {
    const distance = (stopDistance / 20) * index
    const remaining = Math.max(0, stopDistance - distance)
    const speed = Math.sqrt(Math.max(0, 2 * decel * remaining)) * 3.6
    points.push([distance.toFixed(1), speed.toFixed(1)])
  }

  markers.push({
    name: '当前速度',
    xAxis: 0,
    yAxis: currentSpeed,
  })

  if (active.value.target_speed != null) {
    markers.push({
      name: '目标速度',
      xAxis: 0,
      yAxis: active.value.target_speed,
    })
  }

  return {
    title: {
      text: '制动曲线估计',
      subtext: `当前速度 ${currentSpeed} km/h · 估计减速度 ${decel.toFixed(2)} m/s²`,
      textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
      subtextStyle: { color: '#6b7280', fontSize: 11 },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      formatter: (params) => {
        const item = params?.[0]
        if (!item) return ''
        return `距离 ${item.value[0]} m<br/>估计速度 ${item.value[1]} km/h`
      },
    },
    grid: { left: 48, right: 20, top: 58, bottom: 36 },
    xAxis: {
      type: 'value',
      name: '制动距离 m',
      min: 0,
      max: Number(stopDistance.toFixed(0)),
      axisLabel: { color: '#6b7280' },
      axisLine: { lineStyle: { color: '#374151' } },
      splitLine: { lineStyle: { color: '#111827' } },
      nameTextStyle: { color: '#6b7280' },
    },
    yAxis: {
      type: 'value',
      name: '速度 km/h',
      axisLabel: { color: '#6b7280' },
      axisLine: { lineStyle: { color: '#374151' } },
      splitLine: { lineStyle: { color: '#1f2937' } },
      nameTextStyle: { color: '#6b7280' },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        data: points,
        symbol: 'none',
        lineStyle: { width: 3, color: '#22d3ee' },
        areaStyle: { color: 'rgba(34, 211, 238, 0.12)' },
        markLine: {
          symbol: 'none',
          data: active.value.target_speed != null ? [{
            yAxis: active.value.target_speed,
            lineStyle: { color: '#38bdf8', type: 'dashed' },
            label: { formatter: '目标速度', color: '#7dd3fc' },
          }] : [],
        },
        markPoint: {
          symbol: 'circle',
          symbolSize: 28,
          itemStyle: { color: '#f59e0b' },
          label: { color: '#111827', fontWeight: 'bold' },
          data: markers,
        },
      },
    ],
  }
})

function heartbeatLabel(vehicle) {
  const updatedAt = resolveVehicleTimestamp(vehicle)
  if (!updatedAt) return '等待心跳'
  const delta = Math.max(0, now.value - updatedAt)
  if (delta < 1000) return '刚刚更新'
  if (delta < 60000) return `${Math.floor(delta / 1000)} 秒前`
  return `${Math.floor(delta / 60000)} 分钟前`
}

function resolveVehicleTimestamp(vehicle) {
  if (vehicle?.updated_at != null) {
    const raw = vehicle.updated_at
    if (typeof raw === 'string') {
      const parsed = Date.parse(raw)
      if (Number.isFinite(parsed)) return parsed
    }
    const numeric = Number(raw)
    if (Number.isFinite(numeric)) return numeric > 1e12 ? numeric : numeric * 1000
  }

  if (store.protocolMessageAt) return store.protocolMessageAt
  if (store.lastTickAt) return store.lastTickAt
  return null
}

function controlStatusLabel(status) {
  if (status === 'ok') return '已执行'
  if (status === 'error') return '失败'
  return '发送中'
}

function permissionLabel(permission) {
  if (permission === 'allow') return '允许通过'
  if (permission === 'restricted') return '受限通过'
  if (permission === 'stop') return '停车'
  return permission ?? '—'
}

function permissionClass(permission) {
  if (permission === 'stop') return 'text-red-300'
  if (permission === 'restricted') return 'text-amber-300'
  if (permission === 'allow') return 'text-emerald-300'
  return 'text-slate-200'
}

function signalStateLabel(state) {
  if (state === 'red') return '红灯'
  if (state === 'yellow') return '黄灯'
  if (state === 'green') return '绿灯'
  return state ?? '—'
}

function reasonLabel(reason) {
  if (!reason) return '—'
  return {
    front_vehicle_protection: '前车防护',
    route_end: '进路终点',
    route_locked: '进路已锁闭',
    route_available: '进路可用',
  }[reason] ?? reason
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function sendManualCommand(type) {
  if (!active.value) return

  const vehicleId = active.value.vehicle_id
  const level = type === 'emergency_brake' ? 4 : Number(manualControl.level) || 1
  const command = {
    type,
    level,
    source: 'cab-panel',
    line_id: active.value.line_id ?? 'LINE-1',
    direction: manualControl.direction,
    traction_level: type === 'traction' ? level : 0,
    brake_level: type === 'brake' || type === 'emergency_brake' ? level : 0,
    label: type === 'traction'
      ? `牵引 L${level}`
      : type === 'brake'
        ? `制动 L${level}`
        : '紧急制动',
  }

  if (type !== 'emergency_brake' && !canManualControl.value) {
    ui.showToast({
      type: 'warning',
      title: `${vehicleId} 当前不是手动模式`,
      message: '普通牵引/制动按钮仅对手动模式车辆开放，请先切换车辆或调整模式。',
      duration: 3200,
    })
    return
  }

  if (type === 'emergency_brake') {
    ui.requestConfirm({
      title: `确认对 ${vehicleId} 下发紧急制动？`,
      message: '该动作会立即触发高优先级停车逻辑，建议只在演示异常或安全风险场景下执行。',
      confirmLabel: '执行紧急制动',
      cancelLabel: '取消',
      destructive: true,
      onConfirm: () => store.sendControlCommand(vehicleId, command),
    })
    return
  }

  store.sendControlCommand(vehicleId, command)
}

function sendAtoCommand() {
  if (!active.value) return

  const targetSpeed = Number(atoForm.target_speed)
  if (!Number.isFinite(targetSpeed) || targetSpeed < 0) {
    ui.showToast({
      type: 'warning',
      title: 'ATO 目标速度无效',
      message: '请输入大于等于 0 的目标速度。',
      duration: 2800,
    })
    return
  }

  const targetPosition = Number(atoForm.target_position)
  store.sendControlCommand(active.value.vehicle_id, {
    type: 'ato',
    label: `ATO ${targetSpeed} km/h`,
    source: 'cab-panel',
    line_id: active.value.line_id ?? 'LINE-1',
    traction_level: Number(atoForm.traction_level) || 0,
    brake_level: Number(atoForm.brake_level) || 0,
    target_speed: targetSpeed,
    target_position: Number.isFinite(targetPosition) ? targetPosition : undefined,
    reason: atoForm.reason?.trim() || 'cab_console_ato',
  })
}

function syncAtoFormFromActive() {
  if (!active.value) return
  atoForm.target_speed = Number(active.value.target_speed ?? active.value.speed ?? 0)
  atoForm.target_position = Number.isFinite(Number(active.value.ma_limit))
    ? Number(active.value.ma_limit)
    : null
}

async function refreshManagedTrains() {
  await store.hydrateManagedTrains()
}

async function submitAddTrain() {
  if (!canManageVehicles.value) {
    explainMissingManageEndpoint()
    return
  }
  const payload = buildAddTrainPayload()
  const response = await store.submitVehicleManage(payload)
  if (response?.ok) {
    resetManageForm()
    fillNextTrainSuggestion()
  }
}

function buildAddTrainPayload() {
  const payload = {
    type: 'add_train',
    line_id: manageForm.line_id?.trim() || 'LINE-1',
    position: Number.isFinite(Number(manageForm.position)) ? Number(manageForm.position) : 0,
  }
  if (manageForm.vehicle_id?.trim()) payload.vehicle_id = manageForm.vehicle_id.trim()
  if (Number.isFinite(Number(manageForm.train_index)) && Number(manageForm.train_index) >= 1) {
    payload.train_index = Number(manageForm.train_index)
  }
  return payload
}

function requestRemoveTrain(train) {
  if (!canManageVehicles.value) {
    explainMissingManageEndpoint()
    return
  }
  const label = train.vehicle_id ?? `槽位 ${train.train_index}`
  ui.requestConfirm({
    title: `确认删除 ${label}？`,
    message: '该操作会从后端车辆管理器中移除这辆车，并同步发布管理消息。',
    confirmLabel: '确认删除',
    cancelLabel: '取消',
    destructive: true,
    onConfirm: async () => {
      const payload = train.vehicle_id
        ? { type: 'remove_train', vehicle_id: train.vehicle_id }
        : { type: 'remove_train', train_index: train.train_index }
      await store.submitVehicleManage(payload)
      if (store.selectedVehicleId === train.vehicle_id) {
        const nextLive = store.vehicles[0]?.vehicle_id ?? null
        store.selectVehicle(nextLive)
      }
      fillNextTrainSuggestion()
    },
  })
}

function requestClearTrains() {
  if (!canManageVehicles.value) {
    explainMissingManageEndpoint()
    return
  }
  ui.requestConfirm({
    title: '确认清空所有车辆？',
    message: '这会删除当前全部激活车辆。若只是想恢复默认车辆数量，更推荐使用“重置车辆”。',
    confirmLabel: '确认清空',
    cancelLabel: '取消',
    destructive: true,
    onConfirm: async () => {
      await store.submitVehicleManage({ type: 'clear_trains' })
      fillNextTrainSuggestion()
    },
  })
}

function requestResetTrains() {
  if (!canManageVehicles.value) {
    explainMissingManageEndpoint()
    return
  }
  ui.requestConfirm({
    title: '确认重置车辆列表？',
    message: `将先清空现有车辆，再创建 ${resolveResetCount()} 列默认车辆。`,
    confirmLabel: '确认重置',
    cancelLabel: '取消',
    destructive: false,
    onConfirm: async () => {
      await store.submitVehicleManage({ type: 'reset_trains', count: resolveResetCount() })
      fillNextTrainSuggestion()
    },
  })
}

function resolveResetCount() {
  const current = store.managedTrains.length
  return current > 0 ? current : 10
}

function resetManageForm() {
  manageForm.vehicle_id = ''
  manageForm.train_index = null
  manageForm.line_id = 'LINE-1'
  manageForm.position = 0
}

function fillNextTrainSuggestion() {
  const nextIndex = resolveNextTrainIndex()
  manageForm.train_index = nextIndex
  manageForm.vehicle_id = `TRAIN-${String(nextIndex).padStart(3, '0')}`
}

function resolveNextTrainIndex() {
  const used = new Set(
    store.managedTrains
      .map((train) => Number(train.train_index))
      .filter(Number.isFinite),
  )
  let next = 1
  while (used.has(next)) next += 1
  return next
}

function manageActionLabel(type) {
  return {
    add_train: '添加车辆',
    remove_train: '删除车辆',
    clear_trains: '清空车辆',
    reset_trains: '重置车辆',
  }[type] ?? type
}

function explainMissingManageEndpoint() {
  ui.showToast({
    type: 'warning',
    title: '当前后端还没有车辆管理接口',
    message: '你现在这个后端版本缺少 /api/v1/vehicle/manage 和 /api/v1/vehicle/trains，所以前端暂时只能做兼容显示，不能直接增删车辆。',
    duration: 4200,
  })
}

function directionText(direction) {
  if (direction === 'forward') return '前进'
  if (direction === 'backward' || direction === 'reverse') return '后退'
  if (direction === 'neutral') return '空挡'
  return direction ?? '—'
}

function directionCodeLabel(directionCode) {
  if (directionCode === 1) return '前进'
  if (directionCode === -1 || directionCode === 2) return '后退'
  if (directionCode === 0) return '空挡'
  return '方向未上报'
}

function controlEntrySummary(entry) {
  if (entry.command === 'ato') {
    const parts = [
      entry.target_speed != null ? `目标 ${entry.target_speed} km/h` : null,
      entry.target_position != null ? `位置 ${Math.round(entry.target_position)} m` : null,
      `T${entry.traction_level ?? 0}`,
      `B${entry.brake_level ?? 0}`,
    ].filter(Boolean)
    return parts.join(' · ')
  }

  return [
    `level ${entry.level ?? 1}`,
    directionText(entry.direction),
  ].filter(Boolean).join(' · ')
}

function formatProtocolTimestamp(timestamp) {
  if (timestamp == null) return '等待回显'
  const numeric = Number(timestamp)
  if (!Number.isFinite(numeric)) return '等待回显'
  const value = numeric > 1e12 ? numeric : numeric * 1000
  return formatTime(value)
}
</script>
