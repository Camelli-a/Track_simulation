<template>
  <div class="app-metric-tile">
    <p class="app-metric-label">{{ label }}</p>
    <p class="mt-1 truncate text-sm text-slate-200" :title="String(value ?? '—')">{{ value ?? '—' }}</p>
  </div>
</template>

<script setup>
defineProps({
  label: {
    type: String,
    required: true,
  },
  value: {
    type: [String, Number, Boolean],
    default: '—',
  },
})
</script>
