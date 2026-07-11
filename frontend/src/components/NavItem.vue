<template>
  <RouterLink v-slot="{ href, navigate }" :to="to" custom>
    <a
      :href="href"
      class="group block rounded-2xl border px-3.5 py-3 transition-all duration-200"
      :class="isActive
        ? 'border-cyan-400/40 bg-cyan-400/10 text-white shadow-[0_10px_24px_rgba(34,211,238,0.12)]'
        : 'border-white/5 bg-white/[0.02] text-slate-300 hover:border-cyan-400/20 hover:bg-white/[0.05] hover:text-white'"
      @click="navigate"
    >
      <div class="flex items-center gap-3">
        <span
          class="flex h-10 w-10 items-center justify-center rounded-xl border text-base transition-colors"
          :class="isActive
            ? 'border-cyan-300/30 bg-cyan-300/10 text-cyan-100'
            : 'border-white/5 bg-slate-900/60 text-slate-400 group-hover:text-cyan-100'"
        >
          {{ icon }}
        </span>
        <div class="min-w-0">
          <p class="text-sm font-semibold tracking-wide">{{ label }}</p>
          <p class="mt-0.5 text-[11px] text-slate-500 group-hover:text-slate-400">
            {{ hint }}
          </p>
        </div>
      </div>
    </a>
  </RouterLink>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'

const props = defineProps({
  to: String,
  label: String,
  icon: { type: String, default: '•' },
  hint: { type: String, default: '' },
})
const route = useRoute()
const isActive = computed(() => route.path === props.to)
</script>
