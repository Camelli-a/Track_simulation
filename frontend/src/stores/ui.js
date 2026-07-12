import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  const presentationMode = ref(false)
  const navOpen = ref(false)
  const sceneLabel = ref('全局总览')
  const toasts = ref([])
  const confirmDialog = ref(null)

  let toastCounter = 0

  function togglePresentation() {
    presentationMode.value = !presentationMode.value
    if (presentationMode.value) {
      navOpen.value = false
      document.documentElement.requestFullscreen?.().catch(() => {})
    } else if (document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {})
    }
  }

  function toggleNav() {
    navOpen.value = !navOpen.value
  }

  function closeNav() {
    navOpen.value = false
  }

  function setSceneLabel(label) {
    sceneLabel.value = label
  }

  function showToast({
    type = 'info',
    title,
    message = '',
    duration = 2600,
  }) {
    toastCounter += 1
    const id = `toast-${Date.now()}-${toastCounter}`
    toasts.value = [...toasts.value, { id, type, title, message }]
    if (duration > 0) {
      window.setTimeout(() => dismissToast(id), duration)
    }
    return id
  }

  function dismissToast(id) {
    toasts.value = toasts.value.filter((toast) => toast.id !== id)
  }

  function requestConfirm({
    title,
    message,
    confirmLabel = '确认',
    cancelLabel = '取消',
    destructive = false,
    onConfirm = null,
  }) {
    confirmDialog.value = {
      title,
      message,
      confirmLabel,
      cancelLabel,
      destructive,
      onConfirm,
    }
  }

  async function confirmPending() {
    const pending = confirmDialog.value
    confirmDialog.value = null
    await pending?.onConfirm?.()
  }

  function cancelConfirm() {
    confirmDialog.value = null
  }

  return {
    presentationMode,
    navOpen,
    sceneLabel,
    toasts,
    confirmDialog,
    togglePresentation,
    toggleNav,
    closeNav,
    setSceneLabel,
    showToast,
    dismissToast,
    requestConfirm,
    confirmPending,
    cancelConfirm,
  }
})
