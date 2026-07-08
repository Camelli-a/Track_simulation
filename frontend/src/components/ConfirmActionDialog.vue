<template>
  <div v-if="dialog" class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/70 px-4 backdrop-blur-sm">
    <div class="w-full max-w-md rounded-3xl border border-white/10 bg-slate-950/95 p-6 shadow-[0_30px_80px_rgba(2,6,23,0.5)]">
      <p class="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-200/70">
        轻量确认
      </p>
      <h3 class="mt-3 text-lg font-semibold text-white">{{ dialog.title }}</h3>
      <p class="mt-3 text-sm leading-6 text-slate-300">
        {{ dialog.message }}
      </p>

      <div class="mt-6 flex items-center justify-end gap-3">
        <button
          type="button"
          class="rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-300 hover:text-white"
          @click="$emit('cancel')"
        >
          {{ dialog.cancelLabel }}
        </button>
        <button
          type="button"
          class="rounded-xl px-4 py-2 text-sm font-medium text-white"
          :class="dialog.destructive ? 'bg-red-600 hover:bg-red-500' : 'bg-sky-600 hover:bg-sky-500'"
          @click="$emit('confirm')"
        >
          {{ dialog.confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  dialog: { type: Object, default: null },
})

defineEmits(['confirm', 'cancel'])
</script>
