import { computed } from 'vue'
import { useSimulationStore } from '@/stores/simulation'

export function useFocusedVehicle() {
  const simulation = useSimulationStore()

  const focusedVehicle = computed(() => simulation.selectedVehicle)
  const focusedVehicleId = computed(() => simulation.selectedVehicleId)

  return {
    focusedVehicle,
    focusedVehicleId,
    selectVehicle: simulation.selectVehicle,
  }
}
