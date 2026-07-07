import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getSignalStatus, getSignalLights } from '@/api/signal'

export const useSignalStore = defineStore('signal', () => {
  const status  = ref(null)
  const lights  = ref([])
  const loading = ref(false)

  async function fetchStatus() {
    loading.value = true
    try { status.value = await getSignalStatus() }
    finally { loading.value = false }
  }

  async function fetchLights() {
    lights.value = await getSignalLights()
  }

  return { status, lights, loading, fetchStatus, fetchLights }
})
