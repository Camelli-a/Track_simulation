import { getStationYardOverride, stationYardConfig } from '@/config/stationYards'

export function buildStationYardSnapshot({
  station,
  range,
  stations = [],
  layout = null,
  infrastructureSections = [],
  segments = [],
  signals = [],
  turnouts = [],
  vehicles = [],
}) {
  const defaults = stationYardConfig.defaults ?? {}
  const explicitYard = resolveExplicitStationYard(layout, station?.station_id)
  const override = getStationYardOverride(station?.station_id)
  const yard = mergeYardDefinitions(explicitYard, override)

  const graphEdges = layout?.graph?.edges ?? []
  const platforms = layout?.platforms ?? []
  const edgeBySegId = new Map(graphEdges.map((edge) => [Number(edge.seg_id), edge]))

  const platformEntries = resolvePlatformEntries(platforms, station, yard)
  const platformSegIds = new Set(
    platformEntries
      .map((platform) => Number(platform.seg_id))
      .filter(Number.isFinite),
  )

  const stationWindow = resolveStationGraphWindow(station, stations, graphEdges, yard, defaults)
  const seedEdgeSegIds = resolveSeedEdgeSegIds({
    station,
    platformSegIds,
    graphEdges,
    stationWindow,
    yard,
  })

  const localTurnouts = resolveLocalTurnouts({
    turnouts,
    seedEdgeSegIds,
    stationWindow,
    yard,
  })

  const localEdgeSegIds = resolveLocalEdgeSegIds({
    seedEdgeSegIds,
    localTurnouts,
    yard,
  })

  const localEdges = graphEdges
    .filter((edge) => localEdgeSegIds.has(Number(edge.seg_id)))
    .sort((a, b) => {
      const yDiff = (a.y1 ?? 0) - (b.y1 ?? 0)
      if (Math.abs(yDiff) > 1) return yDiff
      return (a.x1 ?? 0) - (b.x1 ?? 0)
    })

  const viewBox = resolveViewBox(localEdges, station, defaults)
  const liveSegments = resolveLiveSegments(segments, localEdgeSegIds)
  const liveSegmentByTrackSegId = new Map(
    liveSegments.map((segment) => [Number(resolveTrackSegId(segment)), normalizeSegment(segment)]),
  )

  const liveEdgeStates = localEdges
    .map((edge) => {
      const segment = liveSegmentByTrackSegId.get(Number(edge.seg_id))
      return segment ? { edge, segment } : null
    })
    .filter(Boolean)

  const platformEdges = localEdges.filter((edge) => platformSegIds.has(Number(edge.seg_id)))
  const platformLabels = resolvePlatformLabels(platformEdges, platformEntries, yard)
  const segmentLabelMarkers = resolveSegmentLabelMarkers(localEdges, liveSegmentByTrackSegId, station)

  const localSignals = resolveLocalSignals({
    signals,
    yard,
    station,
    range,
    localEdgeSegIds,
    localTurnouts,
    infrastructureSections,
    edgeBySegId,
    defaults,
  })

  const turnoutSignalPairs = resolveTurnoutSignalPairs({
    turnouts: localTurnouts,
    signals: localSignals,
    yard,
    defaults,
  })

  const localSignalMarkers = localSignals
    .map((signal) => decorateSignalMarker(signal, turnoutSignalPairs.pairs, turnoutSignalPairs.guardKeys, station))
    .sort((a, b) => (a.x ?? 0) - (b.x ?? 0))

  const localTurnoutsWithGuards = localTurnouts.map((turnout) => ({
    ...turnout,
    guardSignalIds: turnoutSignalPairs.byTurnout.get(turnoutKey(turnout)) ?? [],
  }))

  const guardSignals = localSignalMarkers.filter((signal) => signal.isGuardSignal)
  const turnoutBranchLines = resolveTurnoutBranchLines(localTurnoutsWithGuards, edgeBySegId)

  const localVehicles = resolveLocalVehicles(vehicles, liveSegments)
  const vehicleMarkers = localVehicles
    .map((vehicle, index) => {
      const projection = projectVehicle(vehicle, liveSegments, edgeBySegId)
      if (!projection) return null

      const upperTrack = projection.y <= (station?.graph_y ?? 252)
      const labelOffset = upperTrack ? -12 - (index % 2) * 8 : 16 + (index % 2) * 8

      return {
        ...vehicle,
        x: projection.x,
        y: projection.y,
        labelY: projection.y + labelOffset,
      }
    })
    .filter(Boolean)

  return {
    platformEntries,
    platformTrackLabel: platformLabels.map((label) => label.text).join(' / ') || '未匹配',
    localEdges,
    platformEdges,
    platformLabels,
    segmentLabelMarkers,
    viewBox,
    gridXs: createGrid(viewBox.minX, viewBox.maxX, 24),
    gridYs: createGrid(viewBox.minY, viewBox.maxY, 22),
    liveEdgeStates,
    occupiedSegments: liveSegments.filter((segment) => segment.occupied),
    localSignals,
    turnoutBranchLines,
    turnoutSignalPairs: turnoutSignalPairs.pairs,
    guardSignals,
    localSignalMarkers,
    localTurnoutsWithGuards,
    localVehicles,
    vehicleMarkers,
    orderedSignals: [...guardSignals].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)),
    orderedTurnouts: [...localTurnoutsWithGuards].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)),
    orderedVehicles: [...localVehicles].sort((a, b) =>
      Math.abs((a.position ?? 0) - (station?.position ?? 0))
      - Math.abs((b.position ?? 0) - (station?.position ?? 0)),
    ),
    guardCoverageText: buildGuardCoverageText(localTurnoutsWithGuards),
    throatSummaryText: buildThroatSummaryText(localTurnoutsWithGuards),
    vehicleSummaryText: buildVehicleSummaryText(localVehicles, station),
  }
}

function resolveExplicitStationYard(layout, stationId) {
  const yards = layout?.station_yards ?? layout?.track_info?.station_yards ?? []
  if (Array.isArray(yards)) {
    return yards.find((yard) => yard.station_id === stationId) ?? null
  }
  return yards?.[stationId] ?? null
}

function mergeYardDefinitions(explicitYard, override) {
  if (!explicitYard && !override) return {}
  return {
    ...(explicitYard ?? {}),
    ...(override ?? {}),
  }
}

function resolvePlatformEntries(platforms, station, yard) {
  if (Array.isArray(yard.platforms) && yard.platforms.length) {
    return yard.platforms
  }

  const byPosition = platforms.filter((platform) =>
    Math.abs((platform.position_m ?? 0) - (station?.position ?? 0)) <= 0.5,
  )

  if (byPosition.length) return byPosition

  return platforms.filter((platform) => Number(platform.seg_id) === Number(station?.seg_id))
}

function resolveStationGraphWindow(station, stations, graphEdges, yard, defaults) {
  if (yard.graphWindow?.minX != null && yard.graphWindow?.maxX != null) {
    return {
      minX: yard.graphWindow.minX,
      maxX: yard.graphWindow.maxX,
    }
  }

  const sortedStations = [...(stations ?? [])]
    .filter((item) => item?.graph_x != null)
    .sort((a, b) => (a.graph_x ?? 0) - (b.graph_x ?? 0))
  const index = sortedStations.findIndex((item) => item.station_id === station?.station_id)

  const prev = index > 0 ? sortedStations[index - 1] : null
  const next = index >= 0 && index < sortedStations.length - 1 ? sortedStations[index + 1] : null
  const graphX = station?.graph_x ?? 0
  const padding = defaults.graphPaddingX ?? 48

  const minX = prev?.graph_x != null ? (prev.graph_x + graphX) / 2 : graphX - padding
  const maxX = next?.graph_x != null ? (graphX + next.graph_x) / 2 : graphX + padding

  if (Number.isFinite(minX) && Number.isFinite(maxX) && maxX > minX) {
    return { minX, maxX }
  }

  const xs = graphEdges.flatMap((edge) => [edge.x1, edge.x2]).filter(Number.isFinite)
  return {
    minX: xs.length ? Math.min(...xs) : graphX - padding,
    maxX: xs.length ? Math.max(...xs) : graphX + padding,
  }
}

function resolveSeedEdgeSegIds({ station, platformSegIds, graphEdges, stationWindow, yard }) {
  const ids = new Set(
    (yard.edgeSegIds ?? yard.edge_seg_ids ?? [])
      .map((value) => Number(value))
      .filter(Number.isFinite),
  )

  for (const value of platformSegIds) ids.add(Number(value))

  const stationSegId = Number(station?.seg_id)
  if (Number.isFinite(stationSegId)) ids.add(stationSegId)

  for (const edge of graphEdges) {
    if (intersectsWindow(edge, stationWindow.minX, stationWindow.maxX) && platformSegIds.has(Number(edge.seg_id))) {
      ids.add(Number(edge.seg_id))
    }
  }

  if (!ids.size) {
    for (const edge of graphEdges) {
      if (intersectsWindow(edge, stationWindow.minX, stationWindow.maxX)) {
        ids.add(Number(edge.seg_id))
      }
    }
  }

  return ids
}

function resolveLocalTurnouts({ turnouts, seedEdgeSegIds, stationWindow, yard }) {
  const explicitIds = new Set(
    (yard.turnoutIds ?? yard.turnout_ids ?? [])
      .map(String),
  )

  return turnouts
    .filter((turnout) => {
      if (explicitIds.size && explicitIds.has(String(turnout.turnout_id))) return true

      const segIds = [turnout.merge_seg_id, turnout.normal_seg, turnout.reverse_seg]
        .map((value) => Number(value))
        .filter(Number.isFinite)
      const touchesSeed = segIds.some((segId) => seedEdgeSegIds.has(segId))
      const insideWindow = turnout.graph_x != null
        && turnout.graph_x >= stationWindow.minX
        && turnout.graph_x <= stationWindow.maxX

      return touchesSeed || insideWindow
    })
    .sort((a, b) => (a.graph_x ?? 0) - (b.graph_x ?? 0))
}

function resolveLocalEdgeSegIds({ seedEdgeSegIds, localTurnouts, yard }) {
  const ids = new Set(seedEdgeSegIds)

  for (const value of yard.section_ids ?? []) {
    const numeric = Number(value)
    if (Number.isFinite(numeric)) ids.add(numeric)
  }

  for (const turnout of localTurnouts) {
    for (const value of [turnout.merge_seg_id, turnout.normal_seg, turnout.reverse_seg]) {
      const numeric = Number(value)
      if (Number.isFinite(numeric)) ids.add(numeric)
    }
  }

  return ids
}

function resolveViewBox(localEdges, station, defaults) {
  const xs = localEdges.flatMap((edge) => [edge.x1, edge.x2, station?.graph_x ?? 0]).filter(Number.isFinite)
  const ys = localEdges.flatMap((edge) => [edge.y1, edge.y2, station?.graph_y ?? 252]).filter(Number.isFinite)

  const padX = defaults.graphPaddingX ?? 48
  const padY = defaults.graphPaddingY ?? 42
  const minX = (xs.length ? Math.min(...xs) : (station?.graph_x ?? 0)) - 14
  const maxX = (xs.length ? Math.max(...xs) : (station?.graph_x ?? 0)) + 14
  const minY = (ys.length ? Math.min(...ys) : (station?.graph_y ?? 252)) - padY
  const maxY = (ys.length ? Math.max(...ys) : (station?.graph_y ?? 252)) + padY

  return {
    minX,
    maxX,
    minY,
    maxY,
    width: Math.max(140, maxX - minX),
    height: Math.max(120, maxY - minY),
  }
}

function resolveLiveSegments(segments, localEdgeSegIds) {
  return segments
    .filter((segment) => {
      const trackSegId = Number(resolveTrackSegId(segment))
      return Number.isFinite(trackSegId) && localEdgeSegIds.has(trackSegId)
    })
    .map(normalizeSegment)
}

function resolvePlatformLabels(platformEdges, platformEntries, yard) {
  const explicitTracks = Array.isArray(yard.tracks) ? yard.tracks : []
  const labelBySegId = new Map()

  for (const track of explicitTracks) {
    const label = track.label ?? track.name
    if (!label) continue
    for (const segId of track.segIds ?? track.seg_ids ?? []) {
      const numeric = Number(segId)
      if (Number.isFinite(numeric)) labelBySegId.set(numeric, label)
    }
  }

  const sortedPlatforms = [...platformEntries].sort((a, b) => Number(a.seg_id) - Number(b.seg_id))

  return platformEdges.map((edge, index) => {
    const segId = Number(edge.seg_id)
    const mappedIndex = sortedPlatforms.findIndex((platform) => Number(platform.seg_id) === segId)
    const fallbackLabel = `P${mappedIndex >= 0 ? mappedIndex + 1 : index + 1}`

    return {
      seg_id: edge.seg_id,
      x: (edge.x1 + edge.x2) / 2,
      y: Math.min(edge.y1, edge.y2) - 8,
      text: labelBySegId.get(segId) ?? fallbackLabel,
    }
  })
}

function resolveSegmentLabelMarkers(localEdges, liveSegmentByTrackSegId, station) {
  return localEdges
    .filter((edge) => Math.abs((edge.x2 ?? 0) - (edge.x1 ?? 0)) >= 8)
    .map((edge, index) => {
      const segment = liveSegmentByTrackSegId.get(Number(edge.seg_id)) ?? null
      const upperTrack = ((edge.y1 ?? 0) + (edge.y2 ?? 0)) / 2 <= (station?.graph_y ?? 252)
      const baseOffset = upperTrack ? -5.5 : 9.5
      const offset = baseOffset + ((index % 2) * (upperTrack ? -2 : 2))

      return {
        seg_id: edge.seg_id,
        x: (edge.x1 + edge.x2) / 2,
        y: ((edge.y1 + edge.y2) / 2) + offset,
        aspect: segment?.aspect ?? edge.branch ?? 'green',
        occupied: Boolean(segment?.occupied),
      }
    })
}

function resolveLocalSignals({
  signals,
  yard,
  station,
  range,
  localEdgeSegIds,
  localTurnouts,
  infrastructureSections,
  edgeBySegId,
  defaults,
}) {
  const explicitIds = new Set((yard.signalIds ?? yard.signal_ids ?? []).map(String))
  const guardDistance = yard.signalGuardDistanceM ?? defaults.signalGuardDistanceM ?? 260

  return signals
    .map((signal) => {
      const mountTrackSegId = resolveSignalTrackSegId(signal, infrastructureSections)
      const touchesEdge = Number.isFinite(mountTrackSegId) && localEdgeSegIds.has(Number(mountTrackSegId))
      const nearTurnout = localTurnouts.some((turnout) =>
        Math.abs((turnout.position ?? 0) - (signal.position ?? 0)) <= guardDistance,
      )
      const insideRange = signal.position != null
        && signal.position >= (range?.start ?? 0) - guardDistance
        && signal.position <= (range?.end ?? 0) + guardDistance

      if (!explicitIds.size && !touchesEdge && !nearTurnout && !insideRange) return null
      if (explicitIds.size && !explicitIds.has(String(signal.signal_id))) return null

      const edge = Number.isFinite(mountTrackSegId) ? edgeBySegId.get(Number(mountTrackSegId)) : null
      if (!edge) return null

      const projection = projectPositionOnEdge(signal.position, edge, infrastructureSections, mountTrackSegId)
      const upperTrack = projection.y <= (station?.graph_y ?? 252)
      const facing = resolveSignalFacing(signal)
      const labelOffset = upperTrack ? -16 : 22

      return {
        ...signal,
        key: `${signal.signal_id}-${signal.position}`,
        mountTrackSegId,
        facing,
        x: projection.x,
        anchorY: projection.y,
        mastBaseY: projection.y + (upperTrack ? -8 : 8),
        headY: projection.y + (upperTrack ? -10 : 10),
        labelX: projection.x,
        labelY: projection.y + labelOffset,
      }
    })
    .filter(Boolean)
}

function resolveTurnoutSignalPairs({ turnouts, signals, yard, defaults }) {
  const explicitSignalMap = new Map()
  for (const signal of signals) {
    for (const turnoutId of signal.protects_turnout_ids ?? []) {
      const key = String(turnoutId)
      const list = explicitSignalMap.get(key) ?? []
      list.push(signal)
      explicitSignalMap.set(key, list)
    }
  }

  const pairs = []
  const byTurnout = new Map()
  const guardDistance = yard.signalGuardDistanceM ?? defaults.signalGuardDistanceM ?? 260

  for (const turnout of turnouts) {
    const turnoutId = String(turnout.turnout_id)
    let selected = explicitSignalMap.get(turnoutId) ?? []

    if (!selected.length && Array.isArray(turnout.approach_signal_ids)) {
      selected = signals.filter((signal) => turnout.approach_signal_ids.includes(signal.signal_id))
    }

    if (!selected.length) {
      const candidates = signals
        .filter((signal) => Math.abs((signal.position ?? 0) - (turnout.position ?? 0)) <= guardDistance)
        .sort((a, b) =>
          Math.abs((a.position ?? 0) - (turnout.position ?? 0))
          - Math.abs((b.position ?? 0) - (turnout.position ?? 0)),
        )

      const left = candidates.find((signal) => (signal.x ?? 0) <= (turnout.graph_x ?? 0))
      const right = candidates.find((signal) => (signal.x ?? 0) > (turnout.graph_x ?? 0))
      selected = [left, right].filter(Boolean)
    }

    byTurnout.set(turnoutKey(turnout), [...new Set(selected.map((signal) => signal.signal_id))])

    for (const signal of selected) {
      pairs.push({
        turnoutKey: turnoutKey(turnout),
        signalKey: signal.key,
        turnout,
        signal,
      })
    }
  }

  return {
    pairs,
    byTurnout,
    guardKeys: new Set(pairs.map((pair) => pair.signalKey)),
  }
}

function decorateSignalMarker(signal, pairs, guardKeys, station) {
  const guardedTurnouts = pairs
    .filter((pair) => pair.signalKey === signal.key)
    .map((pair) => `W${pair.turnout.turnout_id}`)

  const upperTrack = signal.anchorY <= (station?.graph_y ?? 252)
  return {
    ...signal,
    mastBaseY: signal.anchorY + (upperTrack ? -8 : 8),
    headY: signal.anchorY + (upperTrack ? -10 : 10),
    labelY: signal.anchorY + (upperTrack ? -16 : 21),
    guardsText: guardedTurnouts.join(' / '),
    isGuardSignal: guardKeys.has(signal.key),
  }
}

function resolveTurnoutBranchLines(turnouts, edgeBySegId) {
  const lines = []
  const seen = new Set()

  for (const turnout of turnouts) {
    const turnoutX = Number(turnout.graph_x)
    const turnoutY = Number(turnout.graph_y)
    if (!Number.isFinite(turnoutX) || !Number.isFinite(turnoutY)) continue

    for (const [role, segId] of [
      ['merge', turnout.merge_seg_id],
      ['normal', turnout.normal_seg],
      ['reverse', turnout.reverse_seg],
    ]) {
      const edge = edgeBySegId.get(Number(segId))
      if (!edge) continue

      const target = resolveTurnoutBranchTarget(turnoutX, turnoutY, edge)
      if (!target) continue

      const lineKey = `${turnout.turnout_id}:${target.x}:${target.y}`
      if (seen.has(lineKey)) continue
      seen.add(lineKey)

      const activeRole = isReverseState(turnout.state) ? 'reverse' : 'normal'
      lines.push({
        key: lineKey,
        turnout_id: turnout.turnout_id,
        x1: turnoutX,
        y1: turnoutY,
        x2: target.x,
        y2: target.y,
        role,
        active: role === activeRole,
        locked: Boolean(turnout.locked),
      })
    }
  }

  return lines
}

function resolveTurnoutBranchTarget(turnoutX, turnoutY, edge) {
  const candidates = [
    { x: Number(edge.x1), y: Number(edge.y1) },
    { x: Number(edge.x2), y: Number(edge.y2) },
  ].filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))

  const offLevel = candidates.filter((point) => Math.abs(point.y - turnoutY) > 1)
  if (!offLevel.length) return null

  return offLevel.reduce((best, point) => {
    if (!best) return point
    const bestDistance = Math.abs(best.x - turnoutX)
    const pointDistance = Math.abs(point.x - turnoutX)
    return pointDistance > bestDistance ? point : best
  }, null)
}

function resolveLocalVehicles(vehicles, liveSegments) {
  return vehicles.filter((vehicle) =>
    liveSegments.some((segment) =>
      vehicle.position != null
      && vehicle.position >= (segment.start ?? 0)
      && vehicle.position <= (segment.end ?? 0),
    ),
  )
}

function normalizeSegment(segment) {
  const occupied = Boolean(segment.occupied)
  return {
    ...segment,
    occupied,
    aspect: segment.aspect ?? (occupied ? 'red' : 'green'),
  }
}

function resolveTrackSegId(item) {
  const numeric = Number(item?.track_seg_id ?? item?.seg_id ?? item?.segment_id)
  return Number.isFinite(numeric) ? numeric : null
}

function resolveSignalTrackSegId(signal, infrastructureSections) {
  const segId = Number(signal?.seg_id ?? signal?.track_seg_id)
  if (Number.isFinite(segId)) return segId

  const section = infrastructureSections.find((item) =>
    signal?.position != null
    && signal.position >= (item.start ?? 0) - 0.5
    && signal.position <= (item.end ?? 0) + 0.5,
  )

  return section ? Number(section.track_seg_id) : null
}

function projectPositionOnEdge(position, edge, infrastructureSections, mountTrackSegId) {
  const section = infrastructureSections.find((item) => Number(item.track_seg_id) === Number(mountTrackSegId))
  const start = section?.start ?? 0
  const end = section?.end ?? start
  const ratio = end !== start
    ? clamp((position - start) / (end - start), 0, 1)
    : 0.5

  return {
    x: lerp(edge.x1, edge.x2, ratio),
    y: lerp(edge.y1, edge.y2, ratio),
  }
}

function projectVehicle(vehicle, liveSegments, edgeBySegId) {
  const section = liveSegments.find((segment) =>
    vehicle.position != null
    && vehicle.position >= (segment.start ?? 0)
    && vehicle.position <= (segment.end ?? 0),
  )

  if (!section) return null

  const edge = edgeBySegId.get(Number(section.track_seg_id))
  if (!edge) return null

  const ratio = section.end !== section.start
    ? clamp((vehicle.position - section.start) / (section.end - section.start), 0, 1)
    : 0.5

  return {
    x: lerp(edge.x1, edge.x2, ratio),
    y: lerp(edge.y1, edge.y2, ratio),
  }
}

function resolveSignalFacing(signal) {
  if (signal.facing) return signal.facing
  if (signal.direction === '0x55') return 'right'
  if (signal.direction === '0xaa') return 'left'
  return 'unknown'
}

function isReverseState(state) {
  return state === 'reverse' || state === 'diverging'
}

function turnoutKey(turnout) {
  const position = Number(turnout?.position)
  if (!Number.isFinite(position)) return null
  return `${turnout.turnout_id}-${Math.round(position)}`
}

function intersectsWindow(edge, minX, maxX) {
  const edgeMin = Math.min(edge.x1, edge.x2)
  const edgeMax = Math.max(edge.x1, edge.x2)
  return edgeMax >= minX && edgeMin <= maxX
}

function createGrid(start, end, step) {
  const values = []
  const first = Math.floor(start / step) * step
  for (let cursor = first; cursor <= end; cursor += step) {
    values.push(cursor)
  }
  return values
}

function buildGuardCoverageText(turnouts) {
  if (!turnouts.length) return '当前无道岔'
  const covered = turnouts.filter((turnout) => turnout.guardSignalIds.length).length
  return `${covered} / ${turnouts.length} 组已匹配防护`
}

function buildThroatSummaryText(turnouts) {
  if (!turnouts.length) return '无咽喉展开'
  const lockedCount = turnouts.filter((turnout) => turnout.locked).length
  return `${turnouts.length} 组道岔，锁闭 ${lockedCount} 组`
}

function buildVehicleSummaryText(vehicles, station) {
  if (!vehicles.length) return '当前无车'
  const insideCount = vehicles.filter((vehicle) =>
    Math.abs((vehicle.position ?? 0) - (station?.position ?? 0)) < 80,
  ).length
  return `${vehicles.length} 列可见，站内 ${insideCount} 列`
}

function lerp(start, end, ratio) {
  return start + (end - start) * ratio
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}
