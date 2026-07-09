/** 合并静态线路布局与 WebSocket 动态 tick */
export function mergeSegments(staticBlocks, dynamicSegments) {
  if (!staticBlocks?.length) return dynamicSegments ?? []
  if (!dynamicSegments?.length) {
    return staticBlocks.map((b) => ({
      segment_id: b.segment_id,
      start: b.start,
      end: b.end,
      occupied: false,
      aspect: 'green',
      condition: 'normal',
      occupied_by: null,
    }))
  }

  const dynamicMap = new Map(dynamicSegments.map((s) => [s.segment_id, s]))

  return staticBlocks.map((b) => {
    const dyn = dynamicMap.get(b.segment_id)
    if (dyn) return { ...b, ...dyn, start: b.start, end: b.end }
    return {
      segment_id: b.segment_id,
      start: b.start,
      end: b.end,
      track_seg_id: b.track_seg_id,
      occupied: false,
      aspect: 'green',
      condition: 'normal',
      occupied_by: null,
    }
  })
}

/** 按位置将动态占用状态映射到静态区段（后端只推 position 时使用） */
export function overlayOccupancy(staticBlocks, vehicles) {
  return staticBlocks.map((b) => {
    const occupant = vehicles.find((v) => v.position >= b.start && v.position < b.end)
    if (occupant) {
      return {
        ...b,
        occupied: true,
        aspect: 'red',
        occupied_by: occupant.vehicle_id,
      }
    }
    const near = vehicles.some((v) => v.position >= b.start - 200 && v.position < b.end)
    return {
      ...b,
      occupied: false,
      aspect: near ? 'yellow' : 'green',
      occupied_by: null,
    }
  })
}

/** 静态信号机位置 + 动态状态 */
export function mergeSignals(staticSignals, dynamicSignals) {
  if (!staticSignals?.length) return dynamicSignals ?? []
  const stateMap = new Map((dynamicSignals ?? []).map((s) => [s.signal_id, s.state]))
  return staticSignals.map((s) => ({
    ...s,
    signal_type: s.signal_type ?? null,
    state: stateMap.get(s.signal_id) ?? 'green',
  }))
}

/** 静态道岔 + 动态锁闭/状态（协议 switches → turnouts） */
export function mergeTurnouts(staticTurnouts, dynamicTurnouts) {
  if (!staticTurnouts?.length) return dynamicTurnouts ?? []
  const dynMap = new Map(
    (dynamicTurnouts ?? []).map((t) => [t.turnout_id ?? t.switch_id, t])
  )
  return staticTurnouts.map((t) => {
    const dyn = dynMap.get(t.turnout_id)
    return {
      turnout_id: t.turnout_id,
      position: t.position,
      track_seg_id: t.track_seg_id,
      graph_x: t.graph_x,
      graph_y: t.graph_y,
      merge_seg_id: t.merge_seg_id ?? null,
      normal_seg: t.normal_seg ?? null,
      reverse_seg: t.reverse_seg ?? null,
      state: dyn?.state ?? 'normal',
      locked: dyn?.locked ?? false,
      related_section: dyn?.related_section ?? t.related_section ?? null,
    }
  })
}
