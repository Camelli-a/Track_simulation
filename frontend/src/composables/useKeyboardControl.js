import { onMounted, onBeforeUnmount } from 'vue'

/** F3.1 键盘 Mock 控车：↑牵引 ↓制动 Space 紧急制动（前端占位，待接后端指令 API） */
export function useKeyboardControl(store) {
  function onKeydown(e) {
    if (!store.selectedVehicleId) return
    if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return

    const id = store.selectedVehicleId
    let cmd = null

    if (e.key === 'ArrowUp') cmd = { type: 'traction', level: 1, source: 'keyboard' }
    else if (e.key === 'ArrowDown') cmd = { type: 'brake', level: 1, source: 'keyboard' }
    else if (e.key === ' ') { cmd = { type: 'emergency_brake', level: 1, source: 'keyboard' }; e.preventDefault() }
    else return

    if (store.selectedVehicle?.mode && store.selectedVehicle.mode !== 'manual') return

    store.sendControlCommand(id, cmd)
  }

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
}
