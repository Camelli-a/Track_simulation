import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getSignalStatus, getSignalLights } from '@/api/signal'
import { normalizeSignalStatus, normalizeSignalLight } from '@/adapters/signalApi'

export const useSignalStore = defineStore('signal', () => {
  const status  = ref(null)
  const lights  = ref([])
  const loading = ref(false)

  async function fetchStatus() {
    loading.value = true
    try {
      status.value = normalizeSignalStatus(await getSignalStatus())
    }
    finally { loading.value = false }
  }

  async function fetchLights() {
    const raw = await getSignalLights()
    lights.value = (raw ?? []).map(normalizeSignalLight)
  }

  return { status, lights, loading, fetchStatus, fetchLights }
})
