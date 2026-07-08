import { onMounted, onBeforeUnmount } from 'vue'
import { useSimulationStore } from '@/stores/simulation'

/** 子系统页面共用：仅读取全局仿真状态 */
export function usePageSimulation() {
  return useSimulationStore()
}

/** 布局级连接：整个应用生命周期内保持 WebSocket */
export function useLayoutSimulation() {
  const store = useSimulationStore()

  onMounted(() => store.connect())
  onBeforeUnmount(() => store.disconnect())

  return store
}
