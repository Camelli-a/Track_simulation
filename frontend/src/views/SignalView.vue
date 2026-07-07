<template>
  <div>
    <h2 class="text-xl font-semibold mb-6">信号系统</h2>

    <div v-if="store.loading" class="text-gray-400">加载中...</div>

    <template v-else-if="store.status">
      <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
        <StatusCard label="运行模式"   :value="store.status.system_mode" />
        <StatusCard label="信号灯数量" :value="store.status.lights?.length" />
      </div>

      <!-- 信号灯列表 -->
      <div class="flex flex-wrap gap-3">
        <div
          v-for="light in store.status.lights"
          :key="light.signal_id"
          class="rounded-lg bg-gray-800 px-4 py-3 text-sm flex items-center gap-2"
        >
          <span
            class="w-3 h-3 rounded-full"
            :class="{
              'bg-red-500':    light.state === 'red',
              'bg-yellow-400': light.state === 'yellow',
              'bg-green-500':  light.state === 'green',
            }"
          />
          <span class="text-gray-300">{{ light.signal_id }}</span>
          <span class="text-gray-500">{{ light.position }}m</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useSignalStore } from '@/stores/signal'
import StatusCard from '@/components/StatusCard.vue'

const store = useSignalStore()
onMounted(() => store.fetchStatus())
</script>
