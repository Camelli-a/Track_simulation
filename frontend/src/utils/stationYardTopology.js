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
  const backendDriven = buildBackendStationYardSnapshot({
    station,
    range,
    infrastructureSections,
    layout,
    segments,
    signals,
    turnouts,
    vehicles,
  })

  if (backendDriven) return backendDriven

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

function buildBackendStationYardSnapshot({
  station,
  range,
  infrastructureSections = [],
  layout = null,
  segments = [],
  signals = [],
  turnouts = [],
  vehicles = [],
}) {
  const yardLayout = layout?.yard_layout ?? null
  if (!yardLayout) return null

  const yardStation = resolveBackendYardStation(yardLayout, station?.station_id)
  if (!yardStation) return null

  const trackPool = resolveBackendYardCollection(yardStation.tracks, yardLayout.yard_tracks, station?.station_id)
  const sectionPool = resolveBackendYardCollection(yardStation.sections, yardLayout.yard_sections, station?.station_id)
  const signalPool = resolveBackendYardCollection(yardStation.signals, yardLayout.yard_signals, station?.station_id)
  const switchPool = resolveBackendYardCollection(yardStation.switches, yardLayout.yard_switches, station?.station_id)

  if (!trackPool.length && !sectionPool.length) return null

  const liveSegments = (segments ?? []).map(normalizeSegment)
  const liveSegmentById = new Map(
    liveSegments.map((segment) => [String(segment.section_id ?? segment.segment_id), segment]),
  )
  const infraBySectionId = new Map(
    (infrastructureSections ?? []).map((section) => [String(section.section_id ?? section.segment_id), section]),
  )
  const dynamicSignalById = new Map(
    (signals ?? []).map((signal) => [String(signal.signal_id), signal]),
  )
  const dynamicTurnoutById = new Map(
    (turnouts ?? []).map((turnout) => [String(turnout.turnout_id ?? turnout.switch_id), turnout]),
  )
  const trackById = new Map(
    trackPool.map((track) => [String(track.track_id), track]),
  )

  const localEdges = sectionPool
    .map((section) => {
      const track = trackById.get(String(section.track_id))
      const points = normalizePolylinePoints(track?.geometry ?? section.geometry)
      if (points.length < 2) return null

      const live = liveSegmentById.get(String(section.section_id)) ?? infraBySectionId.get(String(section.section_id)) ?? {}
      const first = points[0]
      const last = points[points.length - 1]

      return {
        seg_id: String(section.section_id),
        section_id: String(section.section_id),
        track_id: section.track_id ?? track?.track_id ?? null,
        x1: first[0],
        y1: first[1],
        x2: last[0],
        y2: last[1],
        points,
        branch: trackBranchForType(track?.track_type),
        track_type: track?.track_type ?? 'unknown',
        track_name: track?.track_name ?? section.track_id ?? section.section_id,
        start: Number(live.start ?? section.start ?? range?.start ?? 0),
        end: Number(live.end ?? section.end ?? range?.end ?? 0),
      }
    })
    .filter(Boolean)
    .sort((a, b) => {
      const yDiff = (a.y1 ?? 0) - (b.y1 ?? 0)
      if (Math.abs(yDiff) > 1) return yDiff
      return (a.x1 ?? 0) - (b.x1 ?? 0)
    })

  if (!localEdges.length) return null

  const stationCenterY = resolveBackendStationCenterY(localEdges)
  const liveEdgeStates = localEdges.map((edge) => ({
    edge,
    segment: liveSegmentById.get(edge.section_id)
      ?? normalizeSegment({
        section_id: edge.section_id,
        start: edge.start,
        end: edge.end,
        occupied: false,
        aspect: 'green',
      }),
  }))

  const platformEdges = localEdges.filter((edge) => isPlatformTrackType(edge.track_type))
  const platformLabels = platformEdges.map((edge) => {
    const midpoint = pointOnPolyline(edge.points, 0.5)
    const upperTrack = midpoint.y <= stationCenterY
    return {
      seg_id: edge.section_id,
      x: midpoint.x,
      y: midpoint.y + (upperTrack ? -10 : 14),
      text: simplifyTrackLabel(edge.track_name, edge.track_id),
    }
  })

  const segmentLabelMarkers = localEdges.map((edge, index) => {
    const segment = liveEdgeStates.find((item) => item.edge.section_id === edge.section_id)?.segment ?? null
    const midpoint = pointOnPolyline(edge.points, 0.5)
    const upperTrack = midpoint.y <= stationCenterY
    return {
      seg_id: edge.section_id,
      x: midpoint.x,
      y: midpoint.y + (upperTrack ? -4.5 - (index % 2) * 2 : 9 + (index % 2) * 2),
      aspect: segment?.aspect ?? edge.branch ?? 'green',
      occupied: Boolean(segment?.occupied),
    }
  })

  const localSignalsRaw = signalPool
    .map((seed) => {
      const dyn = dynamicSignalById.get(String(seed.signal_id)) ?? {}
      const point = normalizePointGeometry(seed.geometry)
      const edge = findBackendEdgeForSignal({
        signal: dyn,
        seed,
        edges: localEdges,
      })

      const anchor = edge
        ? pointOnPolylineAtX(edge.points, point?.x)
        : null

      const mastX = point?.x ?? anchor?.x
      const anchorY = anchor?.y ?? point?.y ?? stationCenterY
      const headY = point?.y ?? anchorY - 10
      const upperTrack = headY <= anchorY
      const position = Number(
        dyn.position
        ?? inferEdgeMidPosition(edge)
        ?? station?.position
        ?? range?.start
        ?? 0,
      )

      if (!Number.isFinite(mastX) || !Number.isFinite(anchorY)) return null

      return {
        ...seed,
        ...dyn,
        key: `${seed.signal_id}-${position}`,
        signal_id: seed.signal_id,
        station_id: dyn.station_id ?? seed.station_id ?? station?.station_id ?? null,
        track_id: dyn.track_id ?? seed.track_id ?? edge?.track_id ?? null,
        position,
        state: dyn.state ?? dyn.signal_state ?? 'unknown',
        signal_state: dyn.signal_state ?? dyn.state ?? 'unknown',
        protects_switch_id: dyn.protects_switch_id ?? seed.protects_switch_id ?? null,
        protects_section_id: dyn.protects_section_id ?? seed.protects_section_id ?? edge?.section_id ?? null,
        protects_turnout_ids: [dyn.protects_switch_id ?? seed.protects_switch_id].filter(Boolean),
        direction: dyn.direction ?? seed.direction ?? null,
        facing: resolveSignalFacing(dyn.direction ?? seed.direction),
        x: mastX,
        anchorY,
        mastBaseY: anchorY + (upperTrack ? -8 : 8),
        headY,
        labelY: headY + (upperTrack ? -7 : 15),
      }
    })
    .filter(Boolean)

  const localTurnouts = switchPool
    .map((seed) => {
      const dyn = dynamicTurnoutById.get(String(seed.switch_id)) ?? dynamicTurnoutById.get(String(seed.turnout_id ?? seed.switch_id)) ?? {}
      const point = normalizePointGeometry(seed.geometry)
      const relatedEdge = findBackendEdgeForTurnout({
        turnout: dyn,
        seed,
        edges: localEdges,
      })
      const edgeMidpoint = relatedEdge ? pointOnPolyline(relatedEdge.points, 0.5) : null
      const position = Number(
        inferBackendTurnoutPosition(dyn, relatedEdge)
        ?? station?.position
        ?? range?.start
        ?? 0,
      )

      return {
        ...seed,
        ...dyn,
        turnout_id: dyn.turnout_id ?? seed.switch_id,
        switch_id: seed.switch_id,
        position,
        graph_x: point?.x ?? edgeMidpoint?.x ?? 0,
        graph_y: point?.y ?? edgeMidpoint?.y ?? stationCenterY,
        state: dyn.state ?? dyn.position ?? 'normal',
        locked: Boolean(dyn.locked),
      }
    })
    .filter((turnout) => Number.isFinite(turnout.graph_x) && Number.isFinite(turnout.graph_y))

  const turnoutSignalPairs = resolveTurnoutSignalPairs({
    turnouts: localTurnouts,
    signals: localSignalsRaw,
    yard: {},
    defaults: { signalGuardDistanceM: 260 },
  })

  const localSignalMarkers = localSignalsRaw
    .map((signal) => decorateSignalMarker(signal, turnoutSignalPairs.pairs, turnoutSignalPairs.guardKeys, { graph_y: stationCenterY }))
    .sort((a, b) => (a.x ?? 0) - (b.x ?? 0))

  const localTurnoutsWithGuards = localTurnouts.map((turnout) => ({
    ...turnout,
    guardSignalIds: turnoutSignalPairs.byTurnout.get(turnoutKey(turnout)) ?? [],
  }))

  const guardSignalsBase = localSignalMarkers.filter((signal) => signal.isGuardSignal)
  const guardSignals = guardSignalsBase.length ? guardSignalsBase : localSignalMarkers
  const turnoutBranchLines = buildBackendTurnoutBranchLines(localTurnoutsWithGuards, trackPool)

  const localVehicles = vehicles.filter((vehicle) =>
    isVehicleInStationRange(vehicle, range, station?.station_id),
  )

  const vehicleMarkers = localVehicles
    .map((vehicle, index) => {
      const projection = projectVehicleOnBackendYard(vehicle, localEdges)
      if (!projection) return null

      const upperTrack = projection.y <= stationCenterY
      return {
        ...vehicle,
        x: projection.x,
        y: projection.y,
        labelY: projection.y + (upperTrack ? -12 - (index % 2) * 8 : 16 + (index % 2) * 8),
      }
    })
    .filter(Boolean)

  const viewBox = resolveBackendViewBox({
    edges: localEdges,
    signals: localSignalMarkers,
    turnouts: localTurnoutsWithGuards,
    vehicles: vehicleMarkers,
  })

  return {
    platformEntries: trackPool,
    platformTrackLabel: platformLabels.map((label) => label.text).join(' / ') || trackPool.map((track) => simplifyTrackLabel(track.track_name, track.track_id)).join(' / '),
    localEdges,
    platformEdges,
    platformLabels,
    segmentLabelMarkers,
    viewBox,
    gridXs: createGrid(viewBox.minX, viewBox.maxX, 24),
    gridYs: createGrid(viewBox.minY, viewBox.maxY, 22),
    liveEdgeStates,
    occupiedSegments: liveEdgeStates.filter((item) => item.segment.occupied).map((item) => item.segment),
    localSignals: localSignalMarkers,
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

function resolveBackendYardStation(yardLayout, stationId) {
  return (yardLayout?.stations ?? []).find((station) => station.station_id === stationId) ?? null
}

function resolveBackendYardCollection(localCollection, globalCollection, stationId) {
  if (Array.isArray(localCollection) && localCollection.length) return localCollection
  return (globalCollection ?? []).filter((item) => item.station_id === stationId)
}

function normalizePolylinePoints(geometry) {
  const points = geometry?.points ?? []
  return points
    .filter((point) => Array.isArray(point) && point.length >= 2)
    .map((point) => [Number(point[0]), Number(point[1])])
    .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
}

function normalizePointGeometry(geometry) {
  if (Number.isFinite(Number(geometry?.x)) && Number.isFinite(Number(geometry?.y))) {
    return { x: Number(geometry.x), y: Number(geometry.y) }
  }

  const points = normalizePolylinePoints(geometry)
  if (!points.length) return null
  return { x: points[0][0], y: points[0][1] }
}

function trackBranchForType(trackType) {
  if (trackType === 'main' || trackType === 'platform') return 'main'
  return 'branch'
}

function isPlatformTrackType(trackType) {
  return ['main', 'platform', 'arrival_departure'].includes(trackType)
}

function simplifyTrackLabel(trackName, trackId) {
  if (trackName) return trackName.replace(/^Track\s+/i, 'T')
  return trackId ?? 'Track'
}

function resolveBackendStationCenterY(edges) {
  const ys = edges.flatMap((edge) => edge.points.map((point) => point[1]))
  if (!ys.length) return 0
  return ys.reduce((sum, value) => sum + value, 0) / ys.length
}

function pointOnPolyline(points, ratio) {
  if (!points?.length) return { x: 0, y: 0 }
  if (points.length === 1) return { x: points[0][0], y: points[0][1] }

  const lengths = []
  let total = 0
  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index]
    const end = points[index + 1]
    const length = Math.hypot(end[0] - start[0], end[1] - start[1])
    lengths.push(length)
    total += length
  }

  if (!total) return { x: points[0][0], y: points[0][1] }

  const target = clamp(ratio, 0, 1) * total
  let cursor = 0
  for (let index = 0; index < lengths.length; index += 1) {
    const next = cursor + lengths[index]
    if (target <= next || index === lengths.length - 1) {
      const localRatio = lengths[index] ? (target - cursor) / lengths[index] : 0
      return {
        x: lerp(points[index][0], points[index + 1][0], localRatio),
        y: lerp(points[index][1], points[index + 1][1], localRatio),
      }
    }
    cursor = next
  }

  const last = points[points.length - 1]
  return { x: last[0], y: last[1] }
}

function pointOnPolylineAtX(points, x) {
  if (!points?.length) return null
  if (!Number.isFinite(x)) return pointOnPolyline(points, 0.5)

  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index]
    const end = points[index + 1]
    const minX = Math.min(start[0], end[0])
    const maxX = Math.max(start[0], end[0])

    if (x >= minX && x <= maxX) {
      const ratio = maxX !== minX ? (x - start[0]) / (end[0] - start[0]) : 0.5
      return {
        x,
        y: lerp(start[1], end[1], ratio),
      }
    }
  }

  const closest = points.reduce((best, point) => {
    if (!best) return point
    return Math.abs(point[0] - x) < Math.abs(best[0] - x) ? point : best
  }, null)

  return closest ? { x: closest[0], y: closest[1] } : null
}

function findBackendEdgeForSignal({ signal, seed, edges }) {
  const sectionId = signal.section_id ?? seed.protects_section_id ?? null
  if (sectionId) {
    const edge = edges.find((item) => String(item.section_id) === String(sectionId))
    if (edge) return edge
  }

  const trackId = signal.track_id ?? seed.track_id ?? null
  if (trackId) {
    const edge = edges.find((item) => String(item.track_id) === String(trackId))
    if (edge) return edge
  }

  return null
}

function inferEdgeMidPosition(edge) {
  if (!edge) return null
  if (Number.isFinite(edge.start) && Number.isFinite(edge.end)) {
    return (edge.start + edge.end) / 2
  }
  return null
}

function findBackendEdgeForTurnout({ turnout, seed, edges }) {
  const relatedSection = turnout.related_section ?? seed.related_section ?? null
  if (relatedSection) {
    const edge = edges.find((item) => String(item.section_id) === String(relatedSection))
    if (edge) return edge
  }

  const activeTrackId = turnout.reverse_to ?? turnout.normal_to ?? seed.reverse_to ?? seed.normal_to ?? null
  if (activeTrackId) {
    const edge = edges.find((item) => String(item.track_id) === String(activeTrackId))
    if (edge) return edge
  }

  const connectTrackId = (turnout.connects ?? seed.connects ?? [])[0] ?? null
  if (connectTrackId) {
    return edges.find((item) => String(item.track_id) === String(connectTrackId)) ?? null
  }

  return null
}

function inferBackendTurnoutPosition(turnout, edge) {
  if (Number.isFinite(turnout.position)) return Number(turnout.position)
  if (!edge) return null
  return inferEdgeMidPosition(edge)
}

function buildBackendTurnoutBranchLines(turnouts, tracks) {
  const trackById = new Map(
    (tracks ?? []).map((track) => [String(track.track_id), normalizePolylinePoints(track.geometry)]),
  )
  const lines = []
  const seen = new Set()

  for (const turnout of turnouts) {
    const activeTrackId = isReverseState(turnout.state)
      ? (turnout.reverse_to ?? null)
      : (turnout.normal_to ?? null)

    for (const trackId of turnout.connects ?? []) {
      const points = trackById.get(String(trackId)) ?? []
      if (points.length < 2) continue

      const target = pointOnPolylineAtX(points, turnout.graph_x) ?? pointOnPolyline(points, 0.5)
      const key = `${turnout.turnout_id}:${trackId}:${target.x}:${target.y}`
      if (seen.has(key)) continue
      seen.add(key)

      lines.push({
        key,
        turnout_id: turnout.turnout_id,
        x1: turnout.graph_x,
        y1: turnout.graph_y,
        x2: target.x,
        y2: target.y,
        role: trackId === turnout.reverse_to ? 'reverse' : (trackId === turnout.normal_to ? 'normal' : 'branch'),
        active: activeTrackId != null && String(activeTrackId) === String(trackId),
        locked: Boolean(turnout.locked),
      })
    }
  }

  return lines
}

function isVehicleInStationRange(vehicle, range, stationId) {
  if (vehicle.station_id && stationId && vehicle.station_id === stationId) return true
  if (vehicle.position == null) return false
  return vehicle.position >= (range?.start ?? 0) - 1 && vehicle.position <= (range?.end ?? 0) + 1
}

function projectVehicleOnBackendYard(vehicle, edges) {
  const sectionEdge = edges.find((edge) =>
    Number.isFinite(edge.start)
    && Number.isFinite(edge.end)
    && vehicle.position != null
    && vehicle.position >= edge.start
    && vehicle.position <= edge.end,
  )

  const trackEdge = !sectionEdge && vehicle.track_id
    ? edges.find((edge) => String(edge.track_id) === String(vehicle.track_id))
    : null

  const edge = sectionEdge ?? trackEdge
  if (!edge) return null

  const ratio = Number.isFinite(edge.start) && Number.isFinite(edge.end) && edge.end !== edge.start
    ? clamp((vehicle.position - edge.start) / (edge.end - edge.start), 0, 1)
    : 0.5

  return pointOnPolyline(edge.points, ratio)
}

function resolveBackendViewBox({ edges, signals, turnouts, vehicles }) {
  const xs = [
    ...edges.flatMap((edge) => edge.points.map((point) => point[0])),
    ...signals.flatMap((signal) => [signal.x ?? 0]),
    ...turnouts.flatMap((turnout) => [turnout.graph_x ?? 0]),
    ...vehicles.flatMap((vehicle) => [vehicle.x ?? 0]),
  ].filter(Number.isFinite)

  const ys = [
    ...edges.flatMap((edge) => edge.points.map((point) => point[1])),
    ...signals.flatMap((signal) => [signal.headY ?? signal.anchorY ?? 0, signal.labelY ?? 0]),
    ...turnouts.flatMap((turnout) => [turnout.graph_y ?? 0]),
    ...vehicles.flatMap((vehicle) => [vehicle.y ?? 0, vehicle.labelY ?? 0]),
  ].filter(Number.isFinite)

  const minX = (xs.length ? Math.min(...xs) : 0) - 20
  const maxX = (xs.length ? Math.max(...xs) : 280) + 20
  const minY = (ys.length ? Math.min(...ys) : 80) - 18
  const maxY = (ys.length ? Math.max(...ys) : 180) + 18

  return {
    minX,
    maxX,
    minY,
    maxY,
    width: Math.max(140, maxX - minX),
    height: Math.max(120, maxY - minY),
  }
}
