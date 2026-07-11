import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

function normalizeInfrastructureSection(section = {}) {
  const sectionId = section.section_id ?? section.segment_id ?? null
  return {
    section_id: sectionId,
    segment_id: section.segment_id ?? sectionId,
    track_seg_id: section.track_seg_id ?? null,
    start: section.start ?? 0,
    end: section.end ?? 0,
    length_m: section.length_m ?? Math.max(0, (section.end ?? 0) - (section.start ?? 0)),
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

export const useLineLayoutStore = defineStore('lineLayout', () => {
  const layout = ref(null)
  const loading = ref(false)
  const error = ref(null)

  const topology = computed(() => ({
    total_length_m: layout.value?.total_length_m ?? layout.value?.track_info?.total_length ?? 5000,
    stations: layout.value?.stations ?? [],
    blocks: layout.value?.blocks ?? [],
    signals: layout.value?.signals ?? [],
    turnouts: layout.value?.turnouts ?? [],
    graph: layout.value?.graph ?? null,
  }))

  const infrastructureSections = computed(() =>
    buildInfrastructureSections(layout.value)
  )

  const totalLength = computed(() => topology.value.total_length_m)
  const stations = computed(() => topology.value.stations)
  const blocks = computed(() => topology.value.blocks)
  const signals = computed(() => topology.value.signals)
  const turnouts = computed(() => topology.value.turnouts)
  const slopeProfile = computed(() =>
    buildSlopeProfile(layout.value, infrastructureSections.value)
  )
  const graph = computed(() => topology.value.graph)
  const rawBlocks = computed(() => topology.value.blocks)

  async function loadLayout() {
    if (layout.value) return layout.value
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/data/line-layout.json')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      layout.value = await res.json()
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
    topology,
    infrastructureSections,
    totalLength,
    stations,
    blocks,
    signals,
    turnouts,
    slopeProfile,
    graph,
    rawBlocks,
    loadLayout,
  }
})
