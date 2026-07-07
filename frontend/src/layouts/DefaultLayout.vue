<template>
  <div class="flex h-screen bg-gray-950 text-gray-100">
    <!-- 侧边导航 -->
    <aside class="w-48 flex-shrink-0 bg-gray-900 flex flex-col py-6 px-3 gap-2">
      <h1 class="text-sm font-bold text-gray-400 px-3 mb-4 tracking-widest uppercase">
        轨道仿真系统
      </h1>
      <NavItem to="/power"   label="⚡ 供电仿真" />
      <NavItem to="/vehicle" label="🚆 车辆仿真" />
      <NavItem to="/track"   label="🛤️ 轨道仿真" />
      <NavItem to="/signal"  label="🚦 信号系统" />
    </aside>

    <!-- 主内容区 -->
    <main class="flex-1 overflow-auto p-6">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { RouterView } from 'vue-router'
import NavItem from '@/components/NavItem.vue'
</script>
