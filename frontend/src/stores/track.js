import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getTrackStatus, getTrackSegments } from '@/api/track'

export const useTrackStore = defineStore('track', () => {
  const status   = ref(null)
  const segments = ref([])
  const loading  = ref(false)

  async function fetchStatus() {
    loading.value = true
    try { status.value = await getTrackStatus() }
    finally { loading.value = false }
  }

  async function fetchSegments() {
    segments.value = await getTrackSegments()
  }

  return { status, segments, loading, fetchStatus, fetchSegments }
})
