/** 将列车里程映射到拓扑图上的坐标（含边方向角） */
function edgePolylinePoints(edge) {
  if (Array.isArray(edge?.points) && edge.points.length >= 2) {
    return edge.points
  }
  return [
    [Number(edge?.x1 ?? 0), Number(edge?.y1 ?? 0)],
    [Number(edge?.x2 ?? 0), Number(edge?.y2 ?? 0)],
  ]
}

function pointAlongEdge(edge, ratio) {
  const points = edgePolylinePoints(edge)
  if (points.length < 2) {
    return {
      x: Number(edge?.x1 ?? 0),
      y: Number(edge?.y1 ?? 0),
      angle: 0,
    }
  }

  const clampedRatio = Math.min(1, Math.max(0, Number(ratio ?? 0)))
  const segments = []
  let total = 0

  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index]
    const end = points[index + 1]
    const length = Math.hypot(end[0] - start[0], end[1] - start[1])
    segments.push({ start, end, length })
    total += length
  }

  if (!total) {
    const [x, y] = points[0]
    const [nx, ny] = points[points.length - 1]
    return {
      x,
      y,
      angle: (Math.atan2(ny - y, nx - x) * 180) / Math.PI,
    }
  }

  const target = clampedRatio * total
  let cursor = 0

  for (const segment of segments) {
    const next = cursor + segment.length
    if (target <= next || segment === segments[segments.length - 1]) {
      const localRatio = segment.length ? (target - cursor) / segment.length : 0
      const x = segment.start[0] + (segment.end[0] - segment.start[0]) * localRatio
      const y = segment.start[1] + (segment.end[1] - segment.start[1]) * localRatio
      return {
        x,
        y,
        angle: (Math.atan2(segment.end[1] - segment.start[1], segment.end[0] - segment.start[0]) * 180) / Math.PI,
      }
    }
    cursor = next
  }

  const last = points[points.length - 1]
  const prev = points[points.length - 2]
  return {
    x: last[0],
    y: last[1],
    angle: (Math.atan2(last[1] - prev[1], last[0] - prev[0]) * 180) / Math.PI,
  }
}

export function locateTrainOnGraph(vehicle, blocks, graphEdges, options = {}) {
  if (!blocks?.length || !graphEdges?.length) return null

  const candidateBlocks = findCandidateBlocksForVehicle(vehicle, blocks)
  if (!candidateBlocks.length) return null

  const edgeBySegId = new Map(graphEdges.map((edge) => [String(edge.seg_id), edge]))
  const preferredSegId = options.preferredSegId != null ? String(options.preferredSegId) : null
  const prevPoint = options.prevPoint ?? null

  const candidates = candidateBlocks
    .map((block) => projectBlockCandidate(vehicle.position, block, edgeBySegId))
    .filter(Boolean)

  if (!candidates.length) return null

  const chosen = chooseBestCandidate(candidates, { preferredSegId, prevPoint })
  return chosen
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
  const point = pointAlongEdge(edge, ratio)
  return {
    x: point.x,
    y: point.y,
    angle: point.angle,
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
        const edgeStart = pointAlongEdge(edge, 0)
        const jp = { x: edgeStart.x, y: edgeStart.y, angle: entry.angle, seg_id: b.track_seg_id }
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
  const edgeBySegId = new Map(graphEdges.map((edge) => [String(edge.seg_id), edge]))
  const candidates = findCandidateBlocksForVehicle(
    {
      position: signal.position,
      section_id: signal.section_id ?? signal.protects_section_id ?? null,
      track_id: signal.track_id ?? null,
    },
    blocks,
  )
    .map((block) => projectBlockCandidate(signal.position, block, edgeBySegId))
    .filter(Boolean)
  const base = candidates[0] ?? locatePositionOnGraph(signal.position, blocks, graphEdges)
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
  if (aspect === 'red') return '#fb7185'
  if (aspect === 'yellow') return '#f59e0b'
  return '#38bdf8'
}

export function findCandidateBlocksForVehicle(vehicle, blocks) {
  const position = Number(vehicle?.position)
  if (!Number.isFinite(position)) return []

  const matched = blocks.filter((block) => position >= block.start && position < block.end)
  if (!matched.length) return []

  const sectionId = vehicle?.section_id != null ? String(vehicle.section_id) : null
  if (sectionId) {
    const sectionMatched = matched.filter((block) => String(block.section_id ?? block.segment_id) === sectionId)
    if (sectionMatched.length) return sectionMatched
  }

  const trackId = vehicle?.track_id != null ? String(vehicle.track_id) : null
  if (trackId) {
    const trackMatched = matched.filter((block) => String(block.track_id ?? '') === trackId)
    if (trackMatched.length) return trackMatched
  }

  return matched
}

function projectBlockCandidate(position, block, edgeBySegId) {
  const edge = edgeBySegId.get(String(block.track_seg_id))
  if (!edge) return null

  const span = Math.max(1, Number(block.end) - Number(block.start))
  const ratio = Math.min(1, Math.max(0, (position - Number(block.start)) / span))
  const point = pointAlongEdge(edge, ratio)

  return {
    x: point.x,
    y: point.y,
    angle: point.angle,
    seg_id: edge.seg_id,
    edge,
    block,
  }
}

function chooseBestCandidate(candidates, { preferredSegId = null, prevPoint = null } = {}) {
  if (preferredSegId) {
    const sameSeg = candidates.find((candidate) => String(candidate.seg_id) === preferredSegId)
    if (sameSeg) return sameSeg
  }

  if (prevPoint) {
    const ranked = [...candidates].sort((a, b) => {
      const distA = Math.hypot(a.x - prevPoint.x, a.y - prevPoint.y)
      const distB = Math.hypot(b.x - prevPoint.x, b.y - prevPoint.y)
      if (Math.abs(distA - distB) > 0.001) return distA - distB
      return String(a.seg_id).localeCompare(String(b.seg_id))
    })
    return ranked[0]
  }

  return [...candidates].sort((a, b) => {
    const yA = Math.abs(a.y)
    const yB = Math.abs(b.y)
    if (Math.abs(yA - yB) > 0.001) return yA - yB
    return String(a.seg_id).localeCompare(String(b.seg_id))
  })[0]
}

export function edgeBedStroke(aspect) {
  if (aspect === 'red') return '#4c0519'
  if (aspect === 'yellow') return '#451a03'
  return '#082f49'
}

/** 列车标记沿轨道错开，避免重叠 */
export function spreadTrainMarkers(markers, minDist = 14) {
  const sorted = [...markers].sort(
    (a, b) => a.y - b.y || a.x - b.x || String(a.vehicle_id).localeCompare(String(b.vehicle_id)),
  )
  const clusters = []

  for (const marker of sorted) {
    let matchedCluster = null
    for (const cluster of clusters) {
      if (cluster.some((item) => Math.hypot(item.x - marker.x, item.y - marker.y) < minDist)) {
        matchedCluster = cluster
        break
      }
    }
    if (matchedCluster) {
      matchedCluster.push(marker)
    } else {
      clusters.push([marker])
    }
  }

  return clusters.flatMap((cluster) => {
    if (cluster.length === 1) {
      const item = cluster[0]
      return [{ ...item, offsetX: 0, offsetY: 0 }]
    }

    const ordered = [...cluster].sort((a, b) =>
      String(a.vehicle_id).localeCompare(String(b.vehicle_id)),
    )

    return ordered.map((item, index) => {
      const slot = index - (ordered.length - 1) / 2
      const rad = ((item.angle ?? 0) * Math.PI) / 180
      const normalX = -Math.sin(rad)
      const normalY = Math.cos(rad)
      const spread = slot * minDist * 0.9
      return {
        ...item,
        offsetX: normalX * spread,
        offsetY: normalY * spread,
      }
    })
  })
}
