<!-- 通用状态数值卡片 -->
<template>
  <div class="rounded-xl bg-gray-800 p-4">
    <p class="text-xs text-gray-400 mb-1">{{ label }}</p>
    <p class="text-2xl font-bold">
      {{ value }}
      <span v-if="unit" class="text-sm font-normal text-gray-400 ml-1">{{ unit }}</span>
    </p>
  </div>
</template>

<script setup>
defineProps({
  label: String,
  value: [String, Number],
  unit:  String,
})
</script>
