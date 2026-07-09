import { onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { useUiStore } from '@/stores/ui'

/** F3.1 键盘 Mock 控车：↑牵引 ↓制动 Space 紧急制动（前端占位，待接后端指令 API） */
export function useKeyboardControl(store) {
  const route = useRoute()
  const ui = useUiStore()

  function isEditableTarget(target) {
    if (!(target instanceof HTMLElement)) return false
    if (target.isContentEditable) return true
    return ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'].includes(target.tagName)
  }

  function onKeydown(e) {
    if (route.path !== '/vehicle') return
    if (!store.selectedVehicleId) return
    if (e.altKey || e.ctrlKey || e.metaKey) return
    if (isEditableTarget(e.target)) return

    const id = store.selectedVehicleId
    let cmd = null

    if (e.key === 'ArrowUp') cmd = { type: 'traction', level: 1, source: 'keyboard' }
    else if (e.key === 'ArrowDown') cmd = { type: 'brake', level: 1, source: 'keyboard' }
    else if (e.key === ' ' || e.code === 'Space') cmd = { type: 'emergency_brake', level: 1, source: 'keyboard' }
    else return

    e.preventDefault()

    if (store.selectedVehicle?.mode && store.selectedVehicle.mode !== 'manual') return

    if (cmd.type === 'emergency_brake') {
      ui.requestConfirm({
        title: `确认对 ${id} 下发紧急制动？`,
        message: '紧急制动会立即触发高优先级停车逻辑，建议仅在演示异常或安全风险场景下执行。',
        confirmLabel: '执行紧急制动',
        cancelLabel: '取消',
        destructive: true,
        onConfirm: () => store.sendControlCommand(id, cmd),
      })
      return
    }

    store.sendControlCommand(id, cmd)
  }

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
}
