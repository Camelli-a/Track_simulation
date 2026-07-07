import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  const presentationMode = ref(false)

  function togglePresentation() {
    presentationMode.value = !presentationMode.value
    if (presentationMode.value) {
      document.documentElement.requestFullscreen?.().catch(() => {})
    } else if (document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {})
    }
  }

  return { presentationMode, togglePresentation }
})
