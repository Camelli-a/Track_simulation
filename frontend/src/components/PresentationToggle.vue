<template>
  <button
    type="button"
    class="text-xs px-3 py-1.5 rounded-lg border transition-colors"
    :class="ui.presentationMode
      ? 'border-sky-600 bg-sky-950 text-sky-400'
      : 'border-gray-700 text-gray-400 hover:border-gray-500'"
    @click="ui.togglePresentation()"
  >
    {{ ui.presentationMode ? '退出演示' : '演示模式' }}
  </button>
</template>

<script setup>
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
</script>
