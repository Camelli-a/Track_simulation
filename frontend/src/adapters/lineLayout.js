function buildSegmentMetaMap(infrastructureSections = []) {
  const map = new Map()
  for (const section of infrastructureSections ?? []) {
    const key = section.section_id ?? section.segment_id
    if (key != null) map.set(key, section)
  }
  return map
}

function normalizeMergedSegment(base = {}, dyn = {}, meta = {}) {
  const segmentId = dyn.segment_id ?? dyn.section_id ?? base.segment_id ?? meta.segment_id ?? meta.section_id
  const occupied = Boolean(dyn.occupied ?? base.occupied)

  return {
    ...base,
    ...meta,
    ...dyn,
    section_id: dyn.section_id ?? meta.section_id ?? base.section_id ?? segmentId,
    segment_id: segmentId,
    track_seg_id: base.track_seg_id ?? meta.track_seg_id ?? dyn.track_seg_id ?? null,
    track_id: dyn.track_id ?? meta.track_id ?? base.track_id ?? null,
    start: base.start ?? meta.start ?? dyn.start ?? 0,
    end: base.end ?? meta.end ?? dyn.end ?? 0,
    occupied,
    aspect: dyn.aspect ?? meta.aspect ?? (occupied ? 'red' : 'green'),
    condition: dyn.condition ?? meta.condition ?? 'normal',
    occupied_by: dyn.occupied_by ?? dyn.vehicle_id ?? base.occupied_by ?? meta.occupied_by ?? null,
    locked: Boolean(dyn.locked ?? meta.locked ?? base.locked),
    locked_by_route_id:
      dyn.locked_by_route_id
      ?? meta.locked_by_route_id
      ?? base.locked_by_route_id
      ?? null,
    station_id: dyn.station_id ?? meta.station_id ?? base.station_id ?? null,
    speed_limit: dyn.speed_limit ?? meta.speed_limit ?? base.speed_limit ?? null,
    gradient: dyn.gradient ?? meta.gradient ?? base.gradient ?? null,
    stop_position: dyn.stop_position ?? meta.stop_position ?? base.stop_position ?? null,
  }
}

/** 合并静态拓扑、业务元数据与动态区段状态 */
export function mergeSegments(staticBlocks, dynamicSegments, infrastructureSections = []) {
  const metaMap = buildSegmentMetaMap(infrastructureSections)

  if (!staticBlocks?.length) {
    return (dynamicSegments ?? []).map((segment) =>
      normalizeMergedSegment({}, segment, metaMap.get(segment.segment_id ?? segment.section_id)),
    )
  }

  if (!dynamicSegments?.length) {
    return staticBlocks.map((block) =>
      normalizeMergedSegment(
        block,
        {},
        metaMap.get(block.segment_id ?? block.section_id),
      ),
    )
  }

  const dynamicMap = new Map(
    dynamicSegments.map((segment) => [segment.segment_id ?? segment.section_id, segment]),
  )

  return staticBlocks.map((block) => {
    const dyn = dynamicMap.get(block.segment_id)
    const meta = metaMap.get(block.segment_id)
    return normalizeMergedSegment(block, dyn, meta)
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
  const stateMap = new Map((dynamicSignals ?? []).map((signal) => [signal.signal_id, signal]))
  return staticSignals.map((s) => ({
    ...s,
    ...(stateMap.get(s.signal_id) ?? {}),
    signal_type: s.signal_type ?? stateMap.get(s.signal_id)?.signal_type ?? null,
    state: stateMap.get(s.signal_id)?.state ?? 'green',
    signal_state: stateMap.get(s.signal_id)?.signal_state ?? stateMap.get(s.signal_id)?.state ?? 'green',
    permission: stateMap.get(s.signal_id)?.permission ?? null,
    route_id: stateMap.get(s.signal_id)?.route_id ?? null,
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
      switch_id: dyn?.switch_id ?? t.switch_id ?? t.turnout_id,
      station_id: dyn?.station_id ?? t.station_id ?? null,
      connects: dyn?.connects ?? t.connects ?? [],
      normal_to: dyn?.normal_to ?? t.normal_to ?? null,
      reverse_to: dyn?.reverse_to ?? t.reverse_to ?? null,
      active_to: dyn?.active_to ?? t.active_to ?? null,
      state: dyn?.state ?? 'normal',
      locked: dyn?.locked ?? false,
      related_section: dyn?.related_section ?? t.related_section ?? null,
      locked_by_route_id: dyn?.locked_by_route_id ?? null,
      reason: dyn?.reason ?? null,
    }
  })
}
