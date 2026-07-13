import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchDashboardSnapshot, fetchStationYards } from '@/api/dashboard'

function normalizeInfrastructureSection(section = {}) {
  const sectionId = section.section_id ?? section.segment_id ?? null
  return {
    section_id: sectionId,
    segment_id: section.segment_id ?? sectionId,
    track_seg_id: section.track_seg_id ?? null,
    track_id: section.track_id ?? null,
    start: Number(section.start ?? 0),
    end: Number(section.end ?? 0),
    length_m: Number(section.length_m ?? Math.max(0, (section.end ?? 0) - (section.start ?? 0))),
    station_id: section.station_id ?? null,
    speed_limit: section.speed_limit ?? section.target_speed_limit ?? null,
    gradient: section.gradient ?? section.slope ?? null,
    stop_position: section.stop_position ?? null,
  }
}

function buildInfrastructureSections(layout) {
  const protocolSections = layout?.track_info?.sections
  if (Array.isArray(protocolSections) && protocolSections.length) {
    return protocolSections.map(normalizeInfrastructureSection)
  }
  return (layout?.blocks ?? []).map((block) =>
    normalizeInfrastructureSection({
      section_id: block.segment_id,
      segment_id: block.segment_id,
      track_seg_id: block.track_seg_id,
      track_id: block.track_id ?? null,
      start: block.start,
      end: block.end,
      length_m: block.length_m,
      station_id: block.station_id ?? null,
      speed_limit: block.speed_limit ?? null,
      gradient: block.gradient ?? null,
      stop_position: block.stop_position ?? null,
    }),
  )
}

function buildSlopeProfile(layout, infrastructureSections) {
  if (layout?.slope_profile?.length) return layout.slope_profile
  const sectionsWithGradient = infrastructureSections.filter((section) => section.gradient != null)
  if (!sectionsWithGradient.length) return []

  return sectionsWithGradient
    .flatMap((section) => ([
      { position: section.start, slope: section.gradient },
      { position: section.end, slope: section.gradient },
    ]))
    .sort((a, b) => a.position - b.position)
}

function normalizeBlockFromSection(section = {}) {
  const normalized = normalizeInfrastructureSection(section)
  return {
    segment_id: normalized.section_id,
    section_id: normalized.section_id,
    track_seg_id: normalized.track_seg_id ?? normalized.section_id,
    track_id: normalized.track_id ?? null,
    start: normalized.start,
    end: normalized.end,
    length_m: normalized.length_m,
    station_id: normalized.station_id,
    speed_limit: normalized.speed_limit,
    gradient: normalized.gradient,
    stop_position: normalized.stop_position,
  }
}

function buildStationSeedMap(stations = []) {
  const map = new Map()
  for (const station of stations ?? []) {
    const key = station?.station_id ?? station?.name ?? station?.station_name
    if (!key) continue
    map.set(key, station)
  }
  return map
}

function buildStationsFromBackend({ sections = [], yardLayout = null, localStations = [], totalLength = 5000 }) {
  const yardStations = Array.isArray(yardLayout?.stations) ? yardLayout.stations : []
  const localById = buildStationSeedMap(localStations)
  const byId = new Map()

  for (const section of sections) {
    if (!section.station_id) continue
    const current = byId.get(section.station_id) ?? {
      station_id: section.station_id,
      name: section.station_id,
      positionSamples: [],
    }
    const pos = section.stop_position ?? ((Number(section.start ?? 0) + Number(section.end ?? 0)) / 2)
    if (Number.isFinite(pos)) current.positionSamples.push(pos)
    byId.set(section.station_id, current)
  }

  for (const yardStation of yardStations) {
    const current = byId.get(yardStation.station_id) ?? {
      station_id: yardStation.station_id,
      name: yardStation.station_name ?? yardStation.station_id,
      positionSamples: [],
    }
    current.name = yardStation.station_name ?? current.name
    byId.set(yardStation.station_id, current)
  }

  const stations = [...byId.values()].map((item, index, list) => {
    const local = localById.get(item.station_id) ?? null
    const avgPosition = item.positionSamples.length
      ? item.positionSamples.reduce((sum, value) => sum + value, 0) / item.positionSamples.length
      : local?.position ?? ((index + 1) / (list.length + 1)) * totalLength

    return {
      station_id: item.station_id,
      name: local?.name ?? item.name ?? item.station_id,
      position: Number(avgPosition ?? 0),
      seg_id: local?.seg_id ?? null,
      graph_x: local?.graph_x ?? null,
      graph_y: local?.graph_y ?? null,
      platform_id: local?.platform_id ?? null,
    }
  })

  return stations.sort((a, b) => (a.position ?? 0) - (b.position ?? 0))
}

function buildSignalsFromYard({ yardLayout = null, stations = [] }) {
  const yardSignals = Array.isArray(yardLayout?.yard_signals) ? yardLayout.yard_signals : []
  if (!yardSignals.length) return []

  const stationById = new Map(stations.map((station) => [station.station_id, station]))
  return yardSignals.map((signal, index) => {
    const station = stationById.get(signal.station_id)
    const basePosition = station?.position ?? index * 1000
    return {
      signal_id: signal.signal_id,
      position: basePosition,
      station_id: signal.station_id ?? null,
      track_id: signal.track_id ?? null,
      direction: signal.direction ?? null,
      signal_type: null,
      protects_switch_id: signal.protects_switch_id ?? null,
      protects_section_id: signal.protects_section_id ?? null,
    }
  })
}

function buildTurnoutsFromYard({ yardLayout = null, stations = [], stationTransforms = null }) {
  const yardSwitches = Array.isArray(yardLayout?.yard_switches) ? yardLayout.yard_switches : []
  if (!yardSwitches.length) return []

  const stationById = new Map(stations.map((station) => [station.station_id, station]))
  return yardSwitches.map((turnout, index) => {
    const station = stationById.get(turnout.station_id)
    const basePosition = station?.position ?? index * 1000
    const transform = stationTransforms?.get(turnout.station_id) ?? null
    const projected = projectYardPoint(turnout.geometry, transform)
    return {
      turnout_id: turnout.switch_id,
      switch_id: turnout.switch_id,
      station_id: turnout.station_id ?? null,
      position: basePosition,
      track_seg_id: null,
      graph_x: projected?.x ?? station?.graph_x ?? null,
      graph_y: projected?.y ?? station?.graph_y ?? null,
      related_section: null,
      connects: turnout.connects ?? [],
      normal_to: turnout.normal_to ?? null,
      reverse_to: turnout.reverse_to ?? null,
      active_to: turnout.active_to ?? null,
    }
  })
}

function buildSignalsFromBackend({ snapshot = null, yardLayout = null, stations = [] }) {
  const snapshotSignals = Array.isArray(snapshot?.signals) ? snapshot.signals : []
  if (!snapshotSignals.length) {
    return buildSignalsFromYard({ yardLayout, stations })
  }

  const yardSignalById = new Map(
    (yardLayout?.yard_signals ?? []).map((signal) => [signal.signal_id, signal]),
  )
  const stationById = new Map(stations.map((station) => [station.station_id, station]))

  return snapshotSignals.map((signal, index) => {
    const yardSignal = yardSignalById.get(signal.signal_id) ?? null
    const station = stationById.get(signal.station_id)
    const basePosition = Number(
      signal.position
      ?? station?.position
      ?? (index + 1) * 200,
    )

    return {
      signal_id: signal.signal_id,
      position: basePosition,
      station_id: signal.station_id ?? yardSignal?.station_id ?? null,
      track_id: signal.track_id ?? yardSignal?.track_id ?? null,
      direction: signal.direction ?? yardSignal?.direction ?? null,
      signal_type: signal.signal_type ?? null,
      protects_switch_id: signal.protects_switch_id ?? yardSignal?.protects_switch_id ?? null,
      protects_section_id: signal.protects_section_id ?? yardSignal?.protects_section_id ?? null,
      geometry: yardSignal?.geometry ?? null,
    }
  })
}

function buildTurnoutsFromBackend({ snapshot = null, yardLayout = null, stations = [], stationTransforms = null }) {
  const snapshotSwitches = Array.isArray(snapshot?.switches) ? snapshot.switches : []
  if (!snapshotSwitches.length) {
    return buildTurnoutsFromYard({ yardLayout, stations, stationTransforms })
  }

  const yardSwitchById = new Map(
    (yardLayout?.yard_switches ?? []).map((turnout) => [turnout.switch_id, turnout]),
  )
  const stationById = new Map(stations.map((station) => [station.station_id, station]))

  return snapshotSwitches.map((turnout, index) => {
    const key = turnout.switch_id ?? turnout.turnout_id
    const yardSwitch = yardSwitchById.get(key) ?? null
    const station = stationById.get(turnout.station_id ?? yardSwitch?.station_id)
    const basePosition = Number(
      station?.position
      ?? (index + 1) * 200,
    )
    const stationId = turnout.station_id ?? yardSwitch?.station_id ?? null
    const transform = stationTransforms?.get(stationId) ?? null
    const projected = projectYardPoint(yardSwitch?.geometry, transform)

    return {
      turnout_id: turnout.turnout_id ?? turnout.switch_id,
      switch_id: turnout.switch_id ?? turnout.turnout_id,
      station_id: stationId,
      position: basePosition,
      track_seg_id: null,
      graph_x: projected?.x ?? station?.graph_x ?? null,
      graph_y: projected?.y ?? station?.graph_y ?? null,
      related_section: turnout.related_section ?? null,
      connects: turnout.connects ?? yardSwitch?.connects ?? [],
      normal_to: turnout.normal_to ?? yardSwitch?.normal_to ?? null,
      reverse_to: turnout.reverse_to ?? yardSwitch?.reverse_to ?? null,
      active_to: turnout.active_to
        ?? (turnout.state === 'reverse' ? turnout.reverse_to : null)
        ?? (turnout.state === 'normal' ? turnout.normal_to : null)
        ?? yardSwitch?.active_to
        ?? null,
      geometry: yardSwitch?.geometry ?? null,
    }
  })
}

const GRAPH_LEFT = 36
const GRAPH_TRACK_Y = 252

function average(values = [], fallback = 0) {
  const numeric = values.filter(Number.isFinite)
  if (!numeric.length) return fallback
  return numeric.reduce((sum, value) => sum + value, 0) / numeric.length
}

function normalizeGeometryPoints(geometry) {
  return (geometry?.points ?? [])
    .filter((point) => Array.isArray(point) && point.length >= 2)
    .map((point) => [Number(point[0]), Number(point[1])])
    .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
}

function geometryCenter(geometry) {
  const points = normalizeGeometryPoints(geometry)
  if (!points.length) return null
  return {
    x: average(points.map(([x]) => x), 0),
    y: average(points.map(([, y]) => y), 0),
  }
}

function buildYardTransforms(stations = [], yardLayout = null, totalLength = 5000) {
  const width = Math.max(640, totalLength / 8)
  const yardStationById = new Map((yardLayout?.stations ?? []).map((station) => [station.station_id, station]))
  const yardTracks = yardLayout?.yard_tracks ?? []
  const transforms = new Map()
  const laneYByTrackKey = new Map()

  for (const station of stations) {
    const centerX = GRAPH_LEFT + ((Number(station.position ?? 0) / Math.max(totalLength, 1)) * width)
    const centerY = GRAPH_TRACK_Y
    const yardStation = yardStationById.get(station.station_id) ?? null
    const tracks = yardStation?.tracks?.length
      ? yardStation.tracks
      : yardTracks.filter((track) => track.station_id === station.station_id)
    const trackCenters = tracks
      .map((track) => ({
        track_id: track.track_id,
        center: geometryCenter(track.geometry),
      }))
      .filter((item) => item.center)
    const localCenterX = average(trackCenters.map((item) => item.center.x), 140)
    const localCenterY = average(trackCenters.map((item) => item.center.y), 0)

    transforms.set(station.station_id, {
      centerX,
      centerY,
      localCenterX,
      localCenterY,
    })

    for (const item of trackCenters) {
      laneYByTrackKey.set(
        `${station.station_id}::${item.track_id}`,
        centerY + (item.center.y - localCenterY),
      )
    }
  }

  return {
    width,
    transforms,
    laneYByTrackKey,
  }
}

function projectYardPoint(point, transform) {
  if (!point || !transform) return null
  const x = Number(point.x)
  const y = Number(point.y)
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null
  return {
    x: transform.centerX + (x - transform.localCenterX),
    y: transform.centerY + (y - transform.localCenterY),
  }
}

function transformTrackPolyline(geometry, transform) {
  const points = normalizeGeometryPoints(geometry)
  if (!transform || points.length < 2) return []
  return points.map(([x, y]) => ([
    transform.centerX + (x - transform.localCenterX),
    transform.centerY + (y - transform.localCenterY),
  ]))
}

function pointOnPolyline(points, ratio) {
  if (!points?.length) return [0, 0]
  if (points.length === 1) return points[0]

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

  if (!total) return points[0]

  const target = clampedRatio * total
  let cursor = 0
  for (const segment of segments) {
    const next = cursor + segment.length
    if (target <= next || segment === segments[segments.length - 1]) {
      const localRatio = segment.length ? (target - cursor) / segment.length : 0
      return [
        segment.start[0] + (segment.end[0] - segment.start[0]) * localRatio,
        segment.start[1] + (segment.end[1] - segment.start[1]) * localRatio,
      ]
    }
    cursor = next
  }

  return points[points.length - 1]
}

function samplePolylineSegment(points, startRatio, endRatio, steps = 10) {
  if (!points?.length) return []
  const clampedStart = Math.min(1, Math.max(0, Number(startRatio ?? 0)))
  const clampedEnd = Math.min(1, Math.max(clampedStart, Number(endRatio ?? 0)))
  if (clampedEnd <= clampedStart) {
    const point = pointOnPolyline(points, clampedStart)
    return [point, point]
  }

  const sampled = []
  for (let index = 0; index <= steps; index += 1) {
    const ratio = clampedStart + ((clampedEnd - clampedStart) * index) / steps
    const point = pointOnPolyline(points, ratio)
    const last = sampled[sampled.length - 1]
    if (!last || Math.hypot(last[0] - point[0], last[1] - point[1]) > 0.4) {
      sampled.push(point)
    }
  }
  return sampled.length >= 2 ? sampled : [sampled[0], sampled[0]]
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
      return [
        x,
        start[1] + (end[1] - start[1]) * ratio,
      ]
    }
  }

  return points.reduce((best, point) => {
    if (!best) return point
    return Math.abs(point[0] - x) < Math.abs(best[0] - x) ? point : best
  }, null)
}

function edgeMeanY(points, fallback = GRAPH_TRACK_Y) {
  if (!points?.length) return fallback
  return average(points.map((point) => Number(point[1])), fallback)
}

function buildTrackGeometryMap(stations = [], yardLayout = null, transforms = new Map()) {
  const yardStationById = new Map((yardLayout?.stations ?? []).map((station) => [station.station_id, station]))
  const yardTracks = yardLayout?.yard_tracks ?? []
  const trackPolylineByKey = new Map()
  const trackSectionIdsByKey = new Map()

  for (const station of stations) {
    const yardStation = yardStationById.get(station.station_id) ?? null
    const tracks = yardStation?.tracks?.length
      ? yardStation.tracks
      : yardTracks.filter((track) => track.station_id === station.station_id)
    const transform = transforms.get(station.station_id) ?? null

    for (const track of tracks) {
      const key = `${station.station_id}::${track.track_id}`
      const points = transformTrackPolyline(track.geometry, transform)
      if (points.length >= 2) {
        trackPolylineByKey.set(key, points)
      }
      trackSectionIdsByKey.set(key, track.section_ids ?? [])
    }
  }

  return {
    trackPolylineByKey,
    trackSectionIdsByKey,
  }
}

function classifyGraphBranch(y) {
  return Math.abs(Number(y ?? GRAPH_TRACK_Y) - GRAPH_TRACK_Y) > 6 ? 'branch' : 'main'
}

function buildGraphConnectors(sortedBlocks = [], edges = []) {
  const connectors = []

  for (let index = 1; index < edges.length; index += 1) {
    const prevBlock = sortedBlocks[index - 1]
    const nextBlock = sortedBlocks[index]
    const prevEdge = edges[index - 1]
    const nextEdge = edges[index]

    const prevEnd = Number(prevBlock?.end ?? 0)
    const nextStart = Number(nextBlock?.start ?? 0)
    if (Math.abs(nextStart - prevEnd) > 1) continue

    const x1 = Number(prevEdge?.x2)
    const y1 = Number(prevEdge?.y2)
    const x2 = Number(nextEdge?.x1)
    const y2 = Number(nextEdge?.y1)
    if (![x1, y1, x2, y2].every(Number.isFinite)) continue
    if (Math.hypot(x2 - x1, y2 - y1) < 1) continue

    connectors.push({
      key: `${prevEdge.seg_id}->${nextEdge.seg_id}`,
      from_seg_id: prevEdge.seg_id,
      to_seg_id: nextEdge.seg_id,
      station_id: nextEdge.station_id ?? prevEdge.station_id ?? null,
      x1,
      y1,
      x2,
      y2,
      branch: Math.abs(y2 - y1) > 6 ? 'branch' : 'main',
    })
  }

  return connectors
}

function buildSwitchConnectors(
  stations = [],
  yardLayout = null,
  transforms = new Map(),
  trackPolylineByKey = new Map(),
  snapshotSwitches = [],
) {
  const connectors = []
  const seen = new Set()
  const yardStationById = new Map((yardLayout?.stations ?? []).map((station) => [station.station_id, station]))
  const yardSwitches = yardLayout?.yard_switches ?? []
  const snapshotSwitchById = new Map(
    (snapshotSwitches ?? []).map((turnout) => [turnout.switch_id ?? turnout.turnout_id, turnout]),
  )

  for (const station of stations) {
    const yardStation = yardStationById.get(station.station_id) ?? null
    const switchList = yardStation?.switches?.length
      ? yardStation.switches
      : yardSwitches.filter((item) => item.station_id === station.station_id)
    const transform = transforms.get(station.station_id) ?? null

    for (const turnout of switchList) {
      const liveSwitch = snapshotSwitchById.get(turnout.switch_id) ?? null
      const switchPoint = projectYardPoint(turnout.geometry, transform)
      if (!switchPoint) continue

      const activeTrackId = liveSwitch?.active_to
        ?? (liveSwitch?.state === 'reverse' ? liveSwitch?.reverse_to : null)
        ?? (liveSwitch?.state === 'normal' ? liveSwitch?.normal_to : null)
        ?? turnout.active_to
        ?? null
      const candidateTrackIds = [
        activeTrackId,
        liveSwitch?.normal_to ?? turnout.normal_to ?? null,
        liveSwitch?.reverse_to ?? turnout.reverse_to ?? null,
      ]
        .filter(Boolean)
        .filter((trackId, index, list) => list.indexOf(trackId) === index)

      const fallbackTrackIds = (liveSwitch?.connects ?? turnout.connects ?? [])
        .filter(Boolean)
        .filter((trackId, index, list) => list.indexOf(trackId) === index)

      for (const trackId of (candidateTrackIds.length ? candidateTrackIds : fallbackTrackIds)) {
        const points = trackPolylineByKey.get(`${station.station_id}::${trackId}`)
        if (!points?.length) continue

        const target = pointOnPolylineAtX(points, switchPoint.x) ?? pointOnPolyline(points, 0.5)
        if (!target) continue
        if (Math.hypot(target[0] - switchPoint.x, target[1] - switchPoint.y) < 2) continue

        const key = `${turnout.switch_id}:${trackId}:${Math.round(target[0])}:${Math.round(target[1])}`
        if (seen.has(key)) continue
        seen.add(key)

        connectors.push({
          key,
          from_seg_id: turnout.switch_id,
          to_seg_id: trackId,
          station_id: station.station_id,
          x1: switchPoint.x,
          y1: switchPoint.y,
          x2: target[0],
          y2: target[1],
          points: [
            [switchPoint.x, switchPoint.y],
            [target[0], target[1]],
          ],
          active: activeTrackId ? trackId === activeTrackId : undefined,
          branch: Math.abs(target[1] - switchPoint.y) > 6 ? 'branch' : 'main',
        })
      }
    }
  }

  return connectors
}

function buildSyntheticGraph(blocks = [], stations = [], yardLayout = null, snapshotSwitches = []) {
  if (!blocks.length) return null

  const sortedBlocks = [...blocks].sort((a, b) => (a.start ?? 0) - (b.start ?? 0))
  const totalLength = Math.max(sortedBlocks[sortedBlocks.length - 1]?.end ?? 0, 1)
  const { width, transforms, laneYByTrackKey } = buildYardTransforms(stations, yardLayout, totalLength)
  const { trackPolylineByKey, trackSectionIdsByKey } = buildTrackGeometryMap(stations, yardLayout, transforms)
  const blockPointsBySectionId = new Map()

  const blocksByTrackKey = new Map()
  for (const block of sortedBlocks) {
    if (!block.station_id || !block.track_id) continue
    const trackKey = `${block.station_id}::${block.track_id}`
    if (!trackPolylineByKey.has(trackKey)) continue
    const list = blocksByTrackKey.get(trackKey) ?? []
    list.push(block)
    blocksByTrackKey.set(trackKey, list)
  }

  for (const [trackKey, groupBlocks] of blocksByTrackKey) {
    const points = trackPolylineByKey.get(trackKey)
    if (!points?.length) continue

    const sectionOrder = trackSectionIdsByKey.get(trackKey) ?? []
    const ordered = [...groupBlocks].sort((a, b) => {
      const aSectionId = String(a.section_id ?? a.segment_id ?? '')
      const bSectionId = String(b.section_id ?? b.segment_id ?? '')
      const aIndex = sectionOrder.indexOf(aSectionId)
      const bIndex = sectionOrder.indexOf(bSectionId)
      if (aIndex >= 0 || bIndex >= 0) {
        if (aIndex < 0) return 1
        if (bIndex < 0) return -1
        if (aIndex !== bIndex) return aIndex - bIndex
      }
      return Number(a.start ?? 0) - Number(b.start ?? 0)
    })
    const totalTrackLength = Math.max(
      ordered.reduce((sum, block) => sum + Math.max(1, Number(block.end ?? 0) - Number(block.start ?? 0)), 0),
      1,
    )
    let cursor = 0

    for (const block of ordered) {
      const sectionId = String(block.section_id ?? block.segment_id ?? '')
      const blockLength = Math.max(1, Number(block.end ?? 0) - Number(block.start ?? 0))
      const startRatio = cursor / totalTrackLength
      cursor += blockLength
      const endRatio = cursor / totalTrackLength
      blockPointsBySectionId.set(sectionId, samplePolylineSegment(points, startRatio, endRatio))
    }
  }

  const edges = sortedBlocks.map((block) => {
    const start = Number(block.start ?? 0)
    const end = Number(block.end ?? start)
    const sectionId = String(block.section_id ?? block.segment_id ?? '')
    const trackPoints = blockPointsBySectionId.get(sectionId) ?? null
    const laneY = block.station_id && block.track_id
      ? laneYByTrackKey.get(`${block.station_id}::${block.track_id}`) ?? GRAPH_TRACK_Y
      : GRAPH_TRACK_Y
    const startPoint = trackPoints?.[0] ?? [GRAPH_LEFT + (start / totalLength) * width, laneY]
    const endPoint = trackPoints?.[trackPoints.length - 1] ?? [GRAPH_LEFT + (end / totalLength) * width, laneY]
    return {
      seg_id: block.track_seg_id ?? block.segment_id ?? block.section_id,
      section_id: block.section_id ?? block.segment_id ?? null,
      track_id: block.track_id ?? null,
      station_id: block.station_id ?? null,
      x1: startPoint[0],
      y1: startPoint[1],
      x2: endPoint[0],
      y2: endPoint[1],
      points: trackPoints ?? undefined,
      length_m: Math.max(0, end - start),
      branch: classifyGraphBranch(trackPoints ? edgeMeanY(trackPoints, laneY) : laneY),
    }
  })

  const placedStations = stations.map((station) => ({
    ...station,
    graph_x: station.graph_x ?? transforms.get(station.station_id)?.centerX ?? GRAPH_LEFT + ((Number(station.position ?? 0) / totalLength) * width),
    graph_y: station.graph_y ?? transforms.get(station.station_id)?.centerY ?? GRAPH_TRACK_Y,
  }))
  const connectors = [
    ...buildGraphConnectors(sortedBlocks, edges),
    ...buildSwitchConnectors(placedStations, yardLayout, transforms, trackPolylineByKey, snapshotSwitches),
  ]

  return {
    edges,
    connectors,
    total_seg_count: edges.length,
    placed_seg_count: edges.length,
    stations: placedStations,
  }
}

function hasCompatibleScale(localLayout, backendTotalLength) {
  const localTotal = Number(localLayout?.total_length_m ?? localLayout?.track_info?.total_length ?? 0)
  if (!localTotal || !backendTotalLength) return false
  const diffRatio = Math.abs(localTotal - backendTotalLength) / Math.max(localTotal, backendTotalLength)
  return diffRatio < 0.2
}

function composeLayout({ localLayout = null, snapshot = null, yardLayout = null }) {
  const backendSections = Array.isArray(snapshot?.sections) ? snapshot.sections : []
  const baseLayout = localLayout ?? {}

  if (!backendSections.length) {
    return localLayout
  }

  const blocks = backendSections.map(normalizeBlockFromSection)
  const totalLength = Math.max(...blocks.map((block) => Number(block.end ?? 0)), localLayout?.total_length_m ?? 0, 5000)
  const localStations = localLayout?.stations ?? []
  const stations = buildStationsFromBackend({
    sections: backendSections,
    yardLayout,
    localStations,
    totalLength,
  })
  const graph = buildSyntheticGraph(blocks, stations, yardLayout, snapshot?.switches ?? [])
  const resolvedStations = graph?.stations ?? stations
  const stationTransformById = new Map(
    resolvedStations.map((station) => [station.station_id, { graph_x: station.graph_x, graph_y: station.graph_y }]),
  )

  return {
    ...baseLayout,
    line_id: snapshot?.line_id ?? yardLayout?.line_id ?? baseLayout?.line_id ?? 'LINE-1',
    source: 'backend-derived',
    total_length_m: totalLength,
    stations: resolvedStations,
    blocks,
    signals: buildSignalsFromBackend({ snapshot, yardLayout, stations: resolvedStations }),
    turnouts: buildTurnoutsFromBackend({
      snapshot,
      yardLayout,
      stations: resolvedStations,
      stationTransforms: stationTransformById,
    }),
    graph,
    backend_snapshot_sections: backendSections,
    yard_layout: yardLayout ?? null,
  }
}

export const useLineLayoutStore = defineStore('lineLayout', () => {
  const layout = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const layoutSource = ref('unloaded')

  const topology = computed(() => ({
    line_id: layout.value?.line_id ?? layout.value?.track_info?.line_id ?? 'LINE-1',
    total_length_m: layout.value?.total_length_m ?? layout.value?.track_info?.total_length ?? 5000,
    stations: layout.value?.stations ?? [],
    blocks: layout.value?.blocks ?? [],
    signals: layout.value?.signals ?? [],
    turnouts: layout.value?.turnouts ?? [],
    graph: layout.value?.graph ?? null,
    yard_layout: layout.value?.yard_layout ?? null,
  }))

  const infrastructureSections = computed(() =>
    buildInfrastructureSections(layout.value)
  )

  const totalLength = computed(() => topology.value.total_length_m)
  const lineId = computed(() => topology.value.line_id)
  const stations = computed(() => topology.value.stations)
  const blocks = computed(() => topology.value.blocks)
  const signals = computed(() => topology.value.signals)
  const turnouts = computed(() => topology.value.turnouts)
  const yardLayout = computed(() => topology.value.yard_layout)
  const slopeProfile = computed(() =>
    buildSlopeProfile(layout.value, infrastructureSections.value)
  )
  const graph = computed(() => topology.value.graph)
  const rawBlocks = computed(() => topology.value.blocks)

  async function loadLocalLayout() {
    const res = await fetch('/data/line-layout.json')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  }

  async function loadBackendSeeds() {
    const [snapshotResult, yardResult] = await Promise.allSettled([
      fetchDashboardSnapshot(),
      fetchStationYards({ suppressErrorLog: true }),
    ])

    return {
      snapshot: snapshotResult.status === 'fulfilled' ? snapshotResult.value : null,
      yardLayout: yardResult.status === 'fulfilled' ? yardResult.value : null,
    }
  }

  async function loadLayout() {
    if (layout.value) return layout.value
    loading.value = true
    error.value = null

    try {
      const [localResult, backendResult] = await Promise.allSettled([
        loadLocalLayout(),
        loadBackendSeeds(),
      ])

      const localLayout = localResult.status === 'fulfilled' ? localResult.value : null
      const backendSeeds = backendResult.status === 'fulfilled'
        ? backendResult.value
        : { snapshot: null, yardLayout: null }

      layout.value = composeLayout({
        localLayout,
        snapshot: backendSeeds.snapshot,
        yardLayout: backendSeeds.yardLayout,
      })

      layoutSource.value = layout.value?.source
        ?? (backendSeeds.snapshot?.sections?.length ? 'backend-derived' : 'local-static')

      if (!layout.value) {
        throw new Error('layout_unavailable')
      }

      return layout.value
    } catch (e) {
      error.value = e.message
      console.error('[LineLayout] load failed', e)
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    layout,
    loading,
    error,
    layoutSource,
    topology,
    infrastructureSections,
    lineId,
    totalLength,
    stations,
    blocks,
    signals,
    turnouts,
    yardLayout,
    slopeProfile,
    graph,
    rawBlocks,
    loadLayout,
  }
})
