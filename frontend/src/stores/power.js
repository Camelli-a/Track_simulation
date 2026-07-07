import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getPowerStatus, getPowerHistory } from '@/api/power'

export const usePowerStore = defineStore('power', () => {
  const status  = ref(null)
  const history = ref([])
  const loading = ref(false)

  async function fetchStatus() {
    loading.value = true
    try { status.value = await getPowerStatus() }
    finally { loading.value = false }
  }

  async function fetchHistory(limit = 100) {
    history.value = await getPowerHistory(limit)
  }

  return { status, history, loading, fetchStatus, fetchHistory }
})
