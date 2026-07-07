import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getVehicleStatus, getVehicleHistory } from '@/api/vehicle'

export const useVehicleStore = defineStore('vehicle', () => {
  const status  = ref(null)
  const history = ref([])
  const loading = ref(false)

  async function fetchStatus() {
    loading.value = true
    try { status.value = await getVehicleStatus() }
    finally { loading.value = false }
  }

  async function fetchHistory(limit = 100) {
    history.value = await getVehicleHistory(limit)
  }

  return { status, history, loading, fetchStatus, fetchHistory }
})
