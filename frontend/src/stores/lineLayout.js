import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useLineLayoutStore = defineStore('lineLayout', () => {
  const layout = ref(null)
  const loading = ref(false)
  const error = ref(null)

  const totalLength = computed(() => layout.value?.total_length_m ?? 5000)
  const stations = computed(() => layout.value?.stations ?? [])
  const blocks = computed(() => layout.value?.blocks ?? [])
  const signals = computed(() => layout.value?.signals ?? [])
  const turnouts = computed(() => layout.value?.turnouts ?? [])
  const slopeProfile = computed(() => layout.value?.slope_profile ?? [])
  const graph = computed(() => layout.value?.graph ?? null)
  const rawBlocks = computed(() => layout.value?.blocks ?? [])

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
