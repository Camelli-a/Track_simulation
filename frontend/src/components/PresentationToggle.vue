<template>
  <button
    type="button"
    class="inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-medium tracking-wide transition-all duration-200"
    :class="ui.presentationMode
      ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-100'
      : 'border-white/10 bg-white/[0.03] text-slate-300 hover:border-cyan-400/30 hover:text-white'"
    @click="ui.togglePresentation()"
  >
    <span class="text-sm">{{ ui.presentationMode ? '◱' : '⤢' }}</span>
    {{ ui.presentationMode ? '退出演示' : '演示模式' }}
  </button>
</template>

<script setup>
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
</script>
