<template>
  <div class="app-panel text-center">
    <p class="app-section-kicker">数据等待中</p>
    <h3 class="mt-3 text-lg font-semibold text-slate-100">{{ title }}</h3>
    <p class="mx-auto mt-3 max-w-2xl text-sm leading-7 text-slate-400">
      {{ description }}
    </p>
    <p v-if="nextStep" class="mx-auto mt-5 max-w-xl rounded-full border border-sky-900/40 bg-sky-950/25 px-4 py-2 text-xs leading-5 text-sky-300">
      下一步：{{ nextStep }}
    </p>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, required: true },
  nextStep: { type: String, default: '' },
})
</script>
