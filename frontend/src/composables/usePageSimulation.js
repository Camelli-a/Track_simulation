import { onMounted, onBeforeUnmount } from 'vue'
import { useSimulationStore } from '@/stores/simulation'

/** 子系统页面共用：进入时确保 WebSocket 已连接 */
export function usePageSimulation() {
  const store = useSimulationStore()

  onMounted(() => {
    if (!store.connected) store.connect()
  })

  return store
}

/** 布局级连接：整个应用生命周期内保持 WebSocket */
export function useLayoutSimulation() {
  const store = useSimulationStore()

  onMounted(() => store.connect())
  onBeforeUnmount(() => store.disconnect())

  return store
}
