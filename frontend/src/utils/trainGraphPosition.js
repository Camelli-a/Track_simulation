/** 将列车里程映射到拓扑图上的坐标（含边方向角） */
export function locateTrainOnGraph(vehicle, blocks, graphEdges) {
  if (!blocks?.length || !graphEdges?.length) return null

  const block = blocks.find(
    (b) => vehicle.position >= b.start && vehicle.position < b.end
  )
  if (!block) return null

  const edge = graphEdges.find((e) => e.seg_id === block.track_seg_id)
  if (!edge) return null

  const span = Math.max(1, block.end - block.start)
  const ratio = Math.min(1, Math.max(0, (vehicle.position - block.start) / span))

  const dx = edge.x2 - edge.x1
  const dy = edge.y2 - edge.y1
  const angle = (Math.atan2(dy, dx) * 180) / Math.PI

  return {
    x: edge.x1 + dx * ratio,
    y: edge.y1 + dy * ratio,
    angle,
    seg_id: edge.seg_id,
    edge,
  }
}

/** 里程映射到拓扑边（用于 MA 终点、信号机等） */
export function locatePositionOnGraph(position, blocks, graphEdges) {
  if (!blocks?.length || !graphEdges?.length) return null
  const block = blocks.find((b) => position >= b.start && position < b.end)
  if (!block) {
    if (position >= blocks[blocks.length - 1]?.end) {
      return locatePositionOnGraph(blocks[blocks.length - 1].end - 0.1, blocks, graphEdges)
    }
    return null
  }
  const edge = graphEdges.find((e) => e.seg_id === block.track_seg_id)
  if (!edge) return null
  const span = Math.max(1, block.end - block.start)
  const ratio = Math.min(1, Math.max(0, (position - block.start) / span))
  const dx = edge.x2 - edge.x1
  const dy = edge.y2 - edge.y1
  return {
    x: edge.x1 + dx * ratio,
    y: edge.y1 + dy * ratio,
    angle: (Math.atan2(dy, dx) * 180) / Math.PI,
    seg_id: edge.seg_id,
    edge,
  }
}

/** 沿闭塞分区链构建 MA 进路折线（按里程顺序经过各 Seg 拐点） */
export function buildMaPathOnGraph(fromPos, toPos, blocks, graphEdges) {
  if (fromPos == null || toPos == null || !blocks?.length || !graphEdges?.length) return []
  const lo = Math.min(fromPos, toPos)
  const hi = Math.max(fromPos, toPos)
  if (hi - lo < 1) return []

  const sorted = [...blocks].sort((a, b) => a.start - b.start)
  const pathBlocks = sorted.filter((b) => b.end > lo && b.start < hi)
  const edgeMap = new Map(graphEdges.map((e) => [e.seg_id, e]))
  const points = []

  function pushPoint(pos) {
    const p = locatePositionOnGraph(pos, blocks, graphEdges)
    if (!p) return
    const last = points[points.length - 1]
    if (last && Math.hypot(last.x - p.x, last.y - p.y) < 0.8) return
    points.push(p)
  }

  pushPoint(lo)

  for (const b of pathBlocks) {
    const edge = edgeMap.get(b.track_seg_id)
    const prev = points[points.length - 1]
    if (edge && prev && prev.seg_id !== b.track_seg_id) {
      const entryPos = Math.max(lo, b.start)
      const entry = locatePositionOnGraph(entryPos, blocks, graphEdges)
      if (entry?.seg_id === b.track_seg_id) {
        const jp = { x: edge.x1, y: edge.y1, angle: entry.angle, seg_id: b.track_seg_id }
        if (Math.hypot((prev.x ?? 0) - jp.x, (prev.y ?? 0) - jp.y) >= 0.8) points.push(jp)
      }
    }
    if (b.end > lo + 0.5 && b.end < hi - 0.5) pushPoint(b.end)
  }

  pushPoint(hi)
  return points
}

/** MA 进路覆盖的 Seg ID 集合 */
export function buildMaPathSegIds(fromPos, toPos, blocks) {
  if (fromPos == null || toPos == null || !blocks?.length) return new Set()
  const lo = Math.min(fromPos, toPos)
  const hi = Math.max(fromPos, toPos)
  const ids = new Set()
  for (const b of blocks) {
    if (b.end > lo && b.start < hi) ids.add(b.track_seg_id)
  }
  return ids
}

/** 信号机映射到拓扑坐标，轨道法向偏移 */
export function locateSignalOnGraph(signal, blocks, graphEdges, offset = 11) {
  const base = locatePositionOnGraph(signal.position, blocks, graphEdges)
  if (!base) return null
  const rad = (base.angle * Math.PI) / 180
  return {
    ...signal,
    x: base.x + Math.sin(rad) * offset,
    y: base.y - Math.cos(rad) * offset,
    track_x: base.x,
    track_y: base.y,
    angle: base.angle,
    seg_id: base.seg_id,
  }
}

export function signalLampColor(state) {
  if (state === 'red') return '#ef4444'
  if (state === 'yellow') return '#eab308'
  return '#22c55e'
}

export function signalTypeLabel(type) {
  if (type === 2) return '出站'
  if (type === 3) return '防护'
  return '区间'
}

/** 根据逻辑区段占用状态，给拓扑边着色 */
export function edgeAspect(segId, segments, blocks) {
  const relatedBlocks = (blocks ?? []).filter((b) => b.track_seg_id === segId)
  const relatedSegs = (segments ?? []).filter((s) =>
    relatedBlocks.some((b) => b.segment_id === s.segment_id)
  )

  if (relatedSegs.some((s) => s.occupied || s.aspect === 'red')) return 'red'
  if (relatedSegs.some((s) => s.aspect === 'yellow')) return 'yellow'
  return 'green'
}

export function edgeStroke(aspect) {
  if (aspect === 'red') return '#ef4444'
  if (aspect === 'yellow') return '#eab308'
  return '#22c55e'
}

export function edgeBedStroke(aspect) {
  if (aspect === 'red') return '#450a0a'
  if (aspect === 'yellow') return '#422006'
  return '#064e3b'
}

/** 列车标记沿轨道错开，避免重叠 */
export function spreadTrainMarkers(markers, minDist = 14) {
  const sorted = [...markers].sort((a, b) => a.y - b.y || a.x - b.x)
  const placed = []
  for (const m of sorted) {
    let ox = 0
    let oy = 0
    for (const p of placed) {
      const dist = Math.hypot(p.x + (p.offsetX ?? 0) - (m.x + ox), p.y + (p.offsetY ?? 0) - (m.y + oy))
      if (dist < minDist) {
        ox += minDist * 0.6
        oy -= minDist * 0.3
      }
    }
    placed.push({ ...m, offsetX: ox, offsetY: oy })
  }
  return placed
}
