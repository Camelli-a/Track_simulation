<template>
  <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
    <div class="mb-4 flex items-center justify-between">
      <div>
        <h3 class="text-sm font-semibold text-gray-200">全局事件时间线</h3>
        <p class="mt-1 text-xs text-gray-500">记录最近发生的告警、模式切换和关键运行事件</p>
      </div>
      <span class="text-xs text-gray-500">{{ events.length }} 条</span>
    </div>

    <div v-if="!events.length" class="rounded-xl border border-dashed border-gray-800 bg-gray-950/50 px-4 py-8 text-center text-sm text-gray-600">
      暂无关键事件，系统正在稳定运行
    </div>

    <div v-else class="space-y-2.5 max-h-[28rem] overflow-y-auto pr-1">
      <button
        v-for="event in events"
        :key="event.id"
        type="button"
        class="w-full rounded-xl border px-4 py-3 text-left transition-colors"
        :class="rowClass(event)"
        @click="handleSelect(event)"
      >
        <div class="flex items-start gap-3">
          <div class="mt-0.5 shrink-0">
            <span class="block h-2.5 w-2.5 rounded-full" :class="dotClass(event.level)" />
          </div>

          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-medium text-gray-100">{{ event.title }}</span>
              <span v-if="event.source" class="rounded-full border border-gray-700 bg-gray-950 px-2 py-0.5 text-[10px] uppercase tracking-wide text-gray-400">
                {{ event.source }}
              </span>
              <span v-if="event.vehicleId" class="rounded-full px-2 py-0.5 text-[10px] font-medium" :style="vehicleBadgeStyle(event.vehicleId)">
                {{ event.vehicleId }}
              </span>
            </div>

            <p v-if="event.detail" class="mt-1 text-xs leading-5 text-gray-400">
              {{ event.detail }}
            </p>

            <div class="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-gray-500">
              <span>{{ formatTime(event.at) }}</span>
              <span>{{ levelLabel(event.level) }}</span>
              <span v-if="event.vehicleId" class="text-sky-400">
                点击可聚焦该列车
              </span>
            </div>
          </div>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  events: { type: Array, default: () => [] },
  selectedVehicleId: { type: String, default: null },
  color: { type: Function, default: null },
})

const emit = defineEmits(['select'])

function handleSelect(event) {
  if (!event.vehicleId) return
  emit('select', event.vehicleId)
}

function rowClass(event) {
  const selected = event.vehicleId && event.vehicleId === props.selectedVehicleId
  if (selected) return 'border-sky-700 bg-sky-950/30'
  if (event.level === 'error') return 'border-red-900/60 bg-red-950/20 hover:bg-red-950/30'
  if (event.level === 'warn') return 'border-amber-900/60 bg-amber-950/20 hover:bg-amber-950/30'
  return 'border-gray-800 bg-gray-950/40 hover:bg-gray-950/70'
}

function dotClass(level) {
  if (level === 'error') return 'bg-red-400'
  if (level === 'warn') return 'bg-amber-400'
  return 'bg-sky-400'
}

function levelLabel(level) {
  if (level === 'error') return '严重'
  if (level === 'warn') return '提醒'
  return '信息'
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function vehicleBadgeStyle(vehicleId) {
  const color = props.color?.(vehicleId)
  if (!color) return {}
  return {
    color,
    backgroundColor: `${color}22`,
    border: `1px solid ${color}44`,
  }
}
</script>
