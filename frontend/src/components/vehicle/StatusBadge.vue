<template>
  <!-- 状态徽章：显示一个布尔字段的开/关状态 -->
  <div class="app-metric-tile flex items-center gap-2 py-2">
    <span
      class="h-2 w-2 shrink-0 rounded-full transition-colors"
      :class="active ? 'bg-current' : 'bg-slate-700'"
      :style="active ? {} : {}"
    />
    <div>
      <p class="app-metric-label leading-none">{{ label }}</p>
      <p
        class="mt-1 text-sm font-medium transition-colors"
        :class="active ? activeClass : 'text-slate-500'"
      >
        {{ active ? '开' : '关' }}
      </p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: {
    type: String,
    required: true,
  },
  active: {
    type: Boolean,
    default: false,
  },
  /** Tailwind 颜色类，激活时文字颜色，默认 emerald */
  activeClass: {
    type: String,
    default: 'text-emerald-300',
  },
})
</script>
