<!-- 通用状态数值卡片 -->
<template>
  <div class="app-stat-card">
    <p class="app-stat-label">{{ label }}</p>
    <p class="app-stat-value">
      {{ value }}
      <span v-if="unit" class="ml-1 text-sm font-normal text-slate-400">{{ unit }}</span>
    </p>
    <div class="mt-3 h-px bg-gradient-to-r from-cyan-300/25 via-white/8 to-transparent" />
  </div>
</template>

<script setup>
defineProps({
  label: String,
  value: [String, Number],
  unit:  String,
})
</script>
