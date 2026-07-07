<template>
  <div class="space-y-5">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-xl font-semibold">供电仿真</h2>
        <p class="text-sm text-gray-500 mt-1">
          接触网 1500V 直流 · 多车累加能耗与再生制动仿真（F2.3）
        </p>
      </div>
      <ConnectionBadge :connected="store.connected" :data-stale="store.dataStale" />
    </header>

    <div v-if="!store.power" class="text-gray-500">等待供电数据...</div>

    <template v-else>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatusCard label="接触网电压" :value="store.power.voltage.toFixed(1)" unit="V" />
        <StatusCard label="总电流" :value="store.power.current.toFixed(1)" unit="A" />
        <StatusCard label="牵引功率" :value="store.power.power.toFixed(1)" unit="kW" />
        <StatusCard
          label="供电状态"
          :value="store.power.is_fault ? '故障' : '正常'"
        />
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5 flex flex-col items-center">
          <p class="text-xs text-gray-500 self-start mb-2">网压实时仪表</p>
          <VoltageGauge
            :voltage="store.power.voltage"
            :is-fault="store.power.is_fault"
          />
          <p class="text-xs text-gray-600 mt-2 text-center">
            多车加速时电压跌落 · 再生制动时电压回升
          </p>
        </div>
        <div class="lg:col-span-2 rounded-2xl bg-gray-900 border border-gray-800 p-4">
          <VoltageChart
            :voltage-history="store.voltageHistory"
            :time-labels="store.timeLabels"
          />
        </div>
      </div>

      <!-- 各车能耗贡献 -->
      <div class="rounded-2xl bg-gray-900 border border-gray-800 p-5">
        <h3 class="text-sm font-semibold text-gray-300 mb-4">各车瞬时牵引负荷估算</h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div
            v-for="v in store.vehicles"
            :key="v.vehicle_id"
            class="rounded-xl bg-gray-950 border border-gray-800 p-4"
          >
            <div class="flex items-center gap-2 mb-3">
              <span class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: store.vehicleColor(v.vehicle_id) }" />
              <span class="font-medium">{{ v.vehicle_id }}</span>
              <span v-if="v.emergency_brake" class="text-[10px] px-1.5 py-0.5 rounded bg-red-900 text-red-300">EB</span>
            </div>
            <div class="space-y-1 text-xs">
              <div class="flex justify-between">
                <span class="text-gray-500">速度</span>
                <span class="text-gray-300">{{ v.speed }} km/h</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">加速度</span>
                <span class="text-gray-300">{{ v.acceleration }} m/s²</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">累计能耗</span>
                <span class="text-gray-300">{{ v.energy_kwh?.toFixed(1) }} kWh</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">估算功率</span>
                <span class="text-sky-400">{{ estimatePower(v).toFixed(0) }} kW</span>
              </div>
            </div>
            <div class="mt-3 h-1.5 rounded-full bg-gray-800 overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-200"
                :style="{
                  width: `${Math.min(100, v.speed)}%`,
                  backgroundColor: store.vehicleColor(v.vehicle_id),
                }"
              />
            </div>
          </div>
        </div>
        <p v-if="!store.vehicles.length" class="text-sm text-gray-600 text-center py-6">暂无在线车辆</p>
      </div>

      <div class="rounded-2xl bg-gray-900 border border-gray-800 p-4">
        <EChartsContainer :option="powerBreakdownOption" height="260px" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { usePageSimulation } from '@/composables/usePageSimulation'
import StatusCard from '@/components/StatusCard.vue'
import VoltageGauge from '@/components/VoltageGauge.vue'
import VoltageChart from '@/components/VoltageChart.vue'
import EChartsContainer from '@/components/EChartsContainer.vue'
import ConnectionBadge from '@/components/ConnectionBadge.vue'

const store = usePageSimulation()

function estimatePower(v) {
  return Math.max(0, v.speed * 4.5 + Math.abs(v.acceleration) * 80)
}

const powerBreakdownOption = computed(() => ({
  title: {
    text: '多车功率占比',
    textStyle: { color: '#9ca3af', fontSize: 13, fontWeight: 'normal' },
  },
  tooltip: {
    trigger: 'item',
    backgroundColor: '#1f2937',
    borderColor: '#374151',
    textStyle: { color: '#e5e7eb' },
  },
  series: [{
    type: 'pie',
    radius: ['40%', '65%'],
    label: { color: '#9ca3af', fontSize: 11 },
    data: store.vehicles.map((v) => ({
      name: v.vehicle_id,
      value: estimatePower(v),
      itemStyle: { color: store.vehicleColor(v.vehicle_id) },
    })),
  }],
}))
</script>
