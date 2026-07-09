<template>
  <div class="fixed bottom-4 right-4 z-[90] flex w-full max-w-sm flex-col gap-3">
    <div
      v-for="toast in toasts"
      :key="toast.id"
      class="rounded-2xl border px-4 py-3 shadow-[0_18px_32px_rgba(2,6,23,0.35)] backdrop-blur"
      :class="toastClass(toast.type)"
    >
      <div class="flex items-start gap-3">
        <div class="mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full" :class="dotClass(toast.type)" />
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium text-white">{{ toast.title }}</p>
          <p v-if="toast.message" class="mt-1 text-xs leading-5 text-slate-300">
            {{ toast.message }}
          </p>
        </div>
        <button
          type="button"
          class="text-xs text-slate-400 hover:text-white"
          @click="$emit('dismiss', toast.id)"
        >
          关闭
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  toasts: { type: Array, default: () => [] },
})

defineEmits(['dismiss'])

function toastClass(type) {
  if (type === 'error') return 'border-red-500/25 bg-red-950/80'
  if (type === 'success') return 'border-emerald-500/25 bg-emerald-950/70'
  if (type === 'warn') return 'border-amber-500/25 bg-amber-950/80'
  return 'border-sky-500/25 bg-sky-950/75'
}

function dotClass(type) {
  if (type === 'error') return 'bg-red-400'
  if (type === 'success') return 'bg-emerald-400'
  if (type === 'warn') return 'bg-amber-400'
  return 'bg-sky-400'
}
</script>
