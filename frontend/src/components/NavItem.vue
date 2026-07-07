<template>
  <RouterLink
    :to="to"
    class="block rounded-lg px-3 py-2 text-sm font-medium transition-colors"
    :class="isActive
      ? 'bg-blue-600 text-white'
      : 'text-gray-400 hover:bg-gray-800 hover:text-white'"
  >
    {{ label }}
  </RouterLink>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'

const props = defineProps({ to: String, label: String })
const route = useRoute()
const isActive = computed(() => route.path === props.to)
</script>
