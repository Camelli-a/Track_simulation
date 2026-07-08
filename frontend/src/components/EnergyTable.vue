<!-- 多车能耗对比表 -->
<template>
  <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5 h-full">
    <h3 class="text-sm font-semibold text-gray-300 mb-4">多车运行状态</h3>
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-gray-500 text-xs border-b border-gray-800">
            <th class="text-left py-2 pr-3 font-medium">车辆</th>
            <th class="text-right py-2 px-2 font-medium">模式</th>
            <th class="text-right py-2 px-2 font-medium">速度</th>
            <th class="text-right py-2 px-2 font-medium">位置</th>
            <th class="text-right py-2 px-2 font-medium">限速</th>
            <th class="text-right py-2 px-2 font-medium">MA 终点</th>
            <th class="text-right py-2 pl-2 font-medium">能耗</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="v in vehicles"
            :key="v.vehicle_id"
            class="border-b border-gray-800/60 last:border-0"
          >
            <td class="py-2.5 pr-3">
              <span class="inline-flex items-center gap-2">
                <span class="w-2 h-2 rounded-full shrink-0" :style="{ backgroundColor: color(v.vehicle_id) }" />
                <span class="font-medium text-gray-200">{{ v.vehicle_id }}</span>
                <span
                  v-if="v.emergency_brake"
                  class="text-[10px] px-1.5 py-0.5 rounded bg-red-900 text-red-300"
                >EB</span>
              </span>
            </td>
            <td class="text-right py-2.5 px-2 text-gray-400 text-xs">
              {{ modeLabel(v.mode) }}
            </td>
            <td class="text-right py-2.5 px-2 text-gray-300">{{ v.speed }} km/h</td>
            <td class="text-right py-2.5 px-2 text-gray-400">{{ v.position }} m</td>
            <td class="text-right py-2.5 px-2 text-amber-400/80">
              {{ v.target_speed != null ? `${v.target_speed} km/h` : '—' }}
            </td>
            <td class="text-right py-2.5 px-2 text-gray-400">
              {{ v.ma_limit != null ? `${v.ma_limit} m` : '—' }}
            </td>
            <td class="text-right py-2.5 pl-2 text-gray-300">
              {{ v.energy_kwh != null ? `${v.energy_kwh.toFixed(1)} kWh` : '—' }}
            </td>
          </tr>
          <tr v-if="!vehicles.length">
            <td colspan="7" class="py-6 text-center text-gray-600">等待数据...</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { modeLabel } from '@/adapters/simulation'

defineProps({
  vehicles: { type: Array, default: () => [] },
  color: { type: Function, required: true },
})
</script>
