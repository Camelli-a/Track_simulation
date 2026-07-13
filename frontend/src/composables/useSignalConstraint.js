import { computed } from 'vue'
import { useSimulationStore } from '@/stores/simulation'

export function useSignalConstraint() {
  const simulation = useSimulationStore()
  const vehicle = computed(() => simulation.selectedVehicle)
  const authority = computed(() => simulation.selectedVehicleAuthority)
  const trackSegments = computed(() => simulation.trackSegments)
  const signals = computed(() => simulation.signals)
  const turnouts = computed(() => simulation.turnouts)
  const routeResults = computed(() => simulation.routeResults)

  const selectedRouteResult = computed(() =>
    routeResults.value.find((result) => result.vehicle_id === vehicle.value?.vehicle_id) ?? null
  )

  const protectedSignal = computed(() => {
    if (!vehicle.value) return null
    const currentPosition = Number(vehicle.value.position ?? 0)
    const aheadSignals = signals.value
      .map((signal) => ({ signal, delta: Number(signal.position ?? 0) - currentPosition }))
      .filter((item) => item.delta >= -60)
      .sort((a, b) => a.delta - b.delta)
    return aheadSignals[0]?.signal ?? null
  })

  const forwardSegments = computed(() => {
    if (!vehicle.value) return []
    const currentPosition = Number(vehicle.value.position ?? 0)
    const maLimit = Number(vehicle.value.ma_limit ?? vehicle.value.position ?? 0)
    return trackSegments.value
      .filter((segment) => {
        const start = Number(segment.start ?? 0)
        const end = Number(segment.end ?? start)
        return end >= currentPosition - 50 && start <= maLimit + 120
      })
      .sort((a, b) => Number(a.start ?? 0) - Number(b.start ?? 0))
      .slice(0, 6)
  })

  const relatedTurnouts = computed(() => {
    if (!vehicle.value) return []
    const currentPosition = Number(vehicle.value.position ?? 0)
    const maLimit = Number(vehicle.value.ma_limit ?? vehicle.value.position ?? 0)
    return turnouts.value
      .filter((turnout) => {
        const position = Number(turnout.position ?? 0)
        return position >= currentPosition - 120 && position <= maLimit + 150
      })
      .sort((a, b) => Number(a.position ?? 0) - Number(b.position ?? 0))
      .slice(0, 5)
  })

  const interlockingConflicts = computed(() =>
    [...protocolRouteConflicts(routeResults.value), ...heuristicConflicts(trackSegments.value, signals.value, turnouts.value)].slice(0, 12)
  )

  const constraintChain = computed(() => {
    if (!vehicle.value) return []

    return [
      {
        key: 'vehicle',
        title: `${vehicle.value.vehicle_id} 当前状态`,
        value: `${Math.round(vehicle.value.position ?? 0)} m · ${Math.round(vehicle.value.speed ?? 0)} km/h`,
        detail: `${modeLabel(vehicle.value.mode)} · ${permissionLabel(vehicle.value.ma_permission ?? vehicle.value.permission)}`,
        level: vehicle.value.emergency_brake ? 'error' : 'info',
      },
      {
        key: 'segment',
        title: forwardSegments.value.length ? `前方 ${forwardSegments.value.length} 个区段` : '前方区段',
        value: forwardSegments.value.length
          ? forwardSegments.value.map((segment) => segment.segment_id).join(' / ')
          : '暂无区段映射',
        detail: forwardSegments.value.length
          ? `${forwardSegments.value.filter((segment) => segment.occupied).length} 个占用 · ${forwardSegments.value.filter((segment) => segment.locked).length} 个锁闭`
          : '当前没有落到可讲解的区段链',
        level: forwardSegments.value.some((segment) => segment.occupied) ? 'warn' : 'info',
      },
      {
        key: 'signal',
        title: protectedSignal.value ? `防护信号 ${protectedSignal.value.signal_id}` : '防护信号',
        value: protectedSignal.value ? signalStateLabel(protectedSignal.value.signal_state ?? protectedSignal.value.state) : '未找到前方信号',
        detail: protectedSignal.value ? `${permissionLabel(protectedSignal.value.permission)} · ${Math.round(protectedSignal.value.position ?? 0)} m` : '当前数据还不足以稳定映射防护信号',
        level: protectedSignal.value?.state === 'red' || protectedSignal.value?.signal_state === 'red' ? 'warn' : 'info',
      },
      {
        key: 'turnout',
        title: relatedTurnouts.value.length ? `关联道岔 ${relatedTurnouts.value.length} 组` : '关联道岔',
        value: relatedTurnouts.value.length
          ? relatedTurnouts.value.map((turnout) => turnout.turnout_id).join(' / ')
          : '当前 MA 范围内未找到已映射道岔',
        detail: relatedTurnouts.value.length
          ? relatedTurnouts.value.map((turnout) => `${turnout.turnout_id} ${turnoutStateLabel(turnout.state)}${turnout.locked ? ' · 锁闭' : ' · 解锁'}`).join('；')
          : '可继续补强静态线路映射或后端 route 字段',
        level: relatedTurnouts.value.some((turnout) => !turnout.locked) ? 'warn' : 'info',
      },
      {
        key: 'route',
        title: selectedRouteResult.value?.route_id ? `进路 ${selectedRouteResult.value.route_id}` : '进路结果',
        value: selectedRouteResult.value
          ? selectedRouteResult.value.allowed ? '联锁通过' : '联锁未通过'
          : (vehicle.value.ma_route_id ?? '未上报进路'),
        detail: selectedRouteResult.value
          ? reasonLabel(selectedRouteResult.value.reason)
          : (vehicle.value.ma_reason ? `当前 MA 原因：${reasonLabel(vehicle.value.ma_reason)}` : '当前还没有这辆车的 route_result 结果'),
        level: selectedRouteResult.value && !selectedRouteResult.value.allowed ? 'error' : 'info',
      },
      {
        key: 'ma',
        title: 'MA 结果',
        value: vehicle.value.ma_limit != null
          ? `MA ${Math.round(vehicle.value.ma_limit)} m`
          : '暂无 MA',
        detail: vehicle.value.distance_to_ma != null
          ? `剩余 ${Math.max(0, vehicle.value.distance_to_ma).toFixed(1)} m · 信号 ${signalStateLabel(vehicle.value.ma_signal_state ?? vehicle.value.signal_state)}`
          : '当前还没有距离 MA 的明确值',
        level: vehicle.value.distance_to_ma != null && vehicle.value.distance_to_ma < 120 ? 'warn' : 'info',
      },
    ]
  })

  const maReasonSummary = computed(() => buildMaReasonSummary(vehicle.value, authority.value))

  const summaryCards = computed(() => {
    const current = vehicle.value
    if (!current) return []
    return [
      {
        label: '运行许可',
        value: permissionLabel(current.ma_permission ?? current.permission),
        hint: '当前信号与 MA 给出的直接运行结论',
      },
      {
        label: '信号状态',
        value: signalStateLabel(current.ma_signal_state ?? current.signal_state),
        hint: '当前主约束信号显示',
      },
      {
        label: '距离 MA',
        value: current.distance_to_ma != null ? `${Math.max(0, current.distance_to_ma).toFixed(1)} m` : '—',
        hint: '当前授权边界剩余距离',
      },
      {
        label: '约束原因',
        value: reasonLabel(current.ma_reason),
        hint: '来自 MA / 进路结果的主要约束来源',
      },
      {
        label: '前车保护',
        value: current.ma_front_vehicle_id ?? '无前车',
        hint: current.ma_safe_distance != null ? `安全间距 ${current.ma_safe_distance} m` : '当前未上报安全间距',
      },
      {
        label: '联锁冲突',
        value: `${interlockingConflicts.value.length} 项`,
        hint: interlockingConflicts.value.length ? '建议优先阅读右侧冲突列表' : '当前未见显著冲突',
      },
    ]
  })

  return {
    vehicle,
    authority,
    trackSegments,
    signals,
    turnouts,
    routeResults,
    selectedRouteResult,
    protectedSignal,
    forwardSegments,
    relatedTurnouts,
    interlockingConflicts,
    constraintChain,
    maReasonSummary,
    summaryCards,
  }
}

function protocolRouteConflicts(routeResults) {
  return routeResults
    .filter((result) => !result.allowed)
    .map((result) => ({
      id: `route-${result.vehicle_id}-${result.route_id}`,
      level: 'high',
      kind: '协议进路冲突',
      title: `${result.vehicle_id ?? '未知列车'} 的 ${result.route_id ?? '未命名进路'} 不满足联锁条件`,
      turnoutLabel: result.required_switch_id ?? '未上报道岔',
      segmentLabel: result.locked_by_route_id ? `被进路 ${result.locked_by_route_id} 占用/锁闭` : '需结合区段状态继续核对',
      signalLabel: result.current_position
        ? `当前 ${turnoutStateLabel(result.current_position)} → 需要 ${turnoutStateLabel(result.required_position)}`
        : '未上报当前位置',
      detail: `后端返回原因：${reasonLabel(result.reason)}。建议优先核对 ${result.required_switch_id ?? '对应道岔'} 的锁闭方和所需位置。`,
    }))
}

function heuristicConflicts(trackSegments, signals, turnouts) {
  const segmentsByTrackId = new Map()
  for (const segment of trackSegments) {
    const key = segment.track_seg_id ?? segment.segment_id
    const list = segmentsByTrackId.get(key) ?? []
    list.push(segment)
    segmentsByTrackId.set(key, list)
  }

  const occupiedSegments = trackSegments.filter((segment) => segment.occupied)
  const conflicts = []

  for (const turnout of turnouts) {
    const activeTrackId = isReverseState(turnout.state) ? turnout.reverse_seg : turnout.normal_seg
    const inactiveTrackId = isReverseState(turnout.state) ? turnout.normal_seg : turnout.reverse_seg
    const activeSegments = segmentsByTrackId.get(activeTrackId) ?? []
    const inactiveSegments = segmentsByTrackId.get(inactiveTrackId) ?? []
    const mergeSegments = segmentsByTrackId.get(turnout.merge_seg_id) ?? []
    const nearbySignals = signals.filter((signal) => Math.abs(Number(signal.position ?? 0) - Number(turnout.position ?? 0)) <= 260)

    const activeOccupied = activeSegments.find((segment) => segment.occupied)
    const inactiveOccupied = inactiveSegments.find((segment) => segment.occupied)
    const mergeOccupied = mergeSegments.find((segment) => segment.occupied)
    const permissiveSignal = nearbySignals.find((signal) => (signal.state ?? signal.signal_state) !== 'red')

    if (!turnout.locked && (activeOccupied || inactiveOccupied || mergeOccupied)) {
      conflicts.push({
        id: `unlock-occ-${turnout.turnout_id}`,
        level: 'high',
        kind: '道岔解锁占用',
        title: `道岔 ${turnout.turnout_id} 解锁时邻近区段仍被占用`,
        turnoutLabel: turnout.turnout_id,
        segmentLabel: [activeOccupied, inactiveOccupied, mergeOccupied].filter(Boolean).map((segment) => segment.segment_id).join(' / '),
        signalLabel: nearbySignals.length ? nearbySignals.map((signal) => signal.signal_id).join(' / ') : '附近无已映射信号',
        detail: `当前道岔处于${turnoutStateLabel(turnout.state)}且未锁闭，但关联的进路区段仍有占用，建议先确认占用列车和进路释放条件。`,
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
        signalLabel: `${permissiveSignal.signal_id} · ${signalStateLabel(permissiveSignal.state ?? permissiveSignal.signal_state)}`,
        detail: `道岔邻近区段存在占用，但附近信号仍显示${signalStateLabel(permissiveSignal.state ?? permissiveSignal.signal_state)}，这通常意味着联锁约束和显示条件没有完全闭合。`,
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
        detail: '反位道岔切向侧线时，另一分支区段仍处于占用状态，建议检查是否还有列车尾部未出清或进路未完全释放。',
      })
    }
  }

  for (const segment of occupiedSegments) {
    if (segment.aspect === 'red') continue
    const relatedSignal = nearestSignal(signals, segment.start)
    conflicts.push({
      id: `occupied-aspect-${segment.segment_id}`,
      level: 'high',
      kind: '区段显示异常',
      title: `占用分区 ${segment.segment_id} 的显示未落至红灯`,
      turnoutLabel: nearestTurnoutLabel(turnouts, segment),
      segmentLabel: `${segment.segment_id} · ${Math.round(segment.start ?? 0)}-${Math.round(segment.end ?? 0)} m`,
      signalLabel: relatedSignal ? `${relatedSignal.signal_id} · ${signalStateLabel(relatedSignal.state ?? relatedSignal.signal_state)}` : '未找到前方信号',
      detail: `该分区已经被 ${segment.occupied_by ?? '列车'} 占用，但显示仍为${signalStateLabel(segment.aspect)}，建议核对区段占用继电条件和信号防护逻辑。`,
    })
  }

  return conflicts
}

function buildMaReasonSummary(vehicle, authority) {
  if (!vehicle) return null

  const reason = authority?.reason ?? vehicle.ma_reason
  if (vehicle.emergency_brake) {
    return {
      title: '当前已进入 ATP 保护结果态',
      detail: `${vehicle.vehicle_id} 已经抢权紧急制动，此时 MA 页面重点不再是“还能不能走”，而是“为什么会走到 ATP 兜底”。`,
      bullets: [
        `当前距离 MA：${vehicle.distance_to_ma != null ? `${Math.max(0, vehicle.distance_to_ma).toFixed(1)} m` : '—'}`,
        `当前信号状态：${signalStateLabel(vehicle.ma_signal_state ?? vehicle.signal_state)}`,
        `当前约束原因：${reasonLabel(reason)}`,
      ],
    }
  }

  if (reason === 'front_vehicle_protection') {
    return {
      title: 'MA 主要受前车保护约束',
      detail: '当前授权边界更像是跟车保护结果，核心不是站台停车点，而是前车位置和安全间距。',
      bullets: [
        `前车：${vehicle.ma_front_vehicle_id ?? '—'}`,
        `安全间距：${vehicle.ma_safe_distance != null ? `${vehicle.ma_safe_distance} m` : '—'}`,
        `剩余 MA：${vehicle.distance_to_ma != null ? `${Math.max(0, vehicle.distance_to_ma).toFixed(1)} m` : '—'}`,
      ],
    }
  }

  if (reason === 'route_end' || (vehicle.ma_signal_state ?? vehicle.signal_state) === 'red') {
    return {
      title: 'MA 主要受前方信号 / 进路终点约束',
      detail: '当前车辆更接近“看到停车点或红灯后按授权边界停车”的典型信号约束逻辑。',
      bullets: [
        `信号状态：${signalStateLabel(vehicle.ma_signal_state ?? vehicle.signal_state)}`,
        `MA 边界：${vehicle.ma_limit != null ? `${Math.round(vehicle.ma_limit)} m` : '—'}`,
        `剩余距离：${vehicle.distance_to_ma != null ? `${Math.max(0, vehicle.distance_to_ma).toFixed(1)} m` : '—'}`,
      ],
    }
  }

  if (reason === 'route_locked') {
    return {
      title: 'MA 主要受锁闭进路约束',
      detail: '当前更应结合右侧联锁冲突 / 进路不满足列表，看是进路未建立、道岔位置不符，还是锁闭未释放。',
      bullets: [
        `进路：${vehicle.ma_route_id ?? '—'}`,
        `原因：${reasonLabel(reason)}`,
        `运行许可：${permissionLabel(vehicle.ma_permission ?? vehicle.permission)}`,
      ],
    }
  }

  return {
    title: 'MA 当前处于常规监督状态',
    detail: '现有数据没有显示出特别突出的单一约束源，通常意味着车辆正在按既有进路和速度约束运行。',
    bullets: [
      `进路：${vehicle.ma_route_id ?? '—'}`,
      `信号状态：${signalStateLabel(vehicle.ma_signal_state ?? vehicle.signal_state)}`,
      `运行许可：${permissionLabel(vehicle.ma_permission ?? vehicle.permission)}`,
    ],
  }
}

function nearestSignal(signals, position) {
  let best = null
  let bestDistance = Number.POSITIVE_INFINITY
  for (const signal of signals) {
    const distance = Math.abs(Number(signal.position ?? 0) - Number(position ?? 0))
    if (distance < bestDistance) {
      best = signal
      bestDistance = distance
    }
  }
  return best
}

function nearestTurnoutLabel(turnouts, segment) {
  let best = null
  let bestDistance = Number.POSITIVE_INFINITY
  const center = (Number(segment.start ?? 0) + Number(segment.end ?? 0)) / 2
  for (const turnout of turnouts) {
    const distance = Math.abs(Number(turnout.position ?? 0) - center)
    if (distance < bestDistance) {
      best = turnout
      bestDistance = distance
    }
  }
  return best ? best.turnout_id : '未关联'
}

function isReverseState(state) {
  return state === 'reverse' || state === 'diverging'
}

function turnoutStateLabel(state) {
  return isReverseState(state) ? '反位' : '定位'
}

function signalStateLabel(state) {
  return { red: '红灯', yellow: '黄灯', green: '绿灯' }[state] ?? state ?? '—'
}

function permissionLabel(permission) {
  if (permission === 'allow') return '允许通过'
  if (permission === 'restricted') return '受限通过'
  if (permission === 'stop') return '停车'
  return permission ?? '—'
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

function modeLabel(mode) {
  if (mode === 'manual') return '手动驾驶'
  if (mode === 'ato') return 'ATO 自动'
  if (mode === 'atp') return 'ATP 监督'
  if (mode === 'emergency') return '紧急模式'
  return mode ?? '—'
}
