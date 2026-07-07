import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/layouts/DefaultLayout.vue'),
    children: [
      { path: '',          redirect: '/power' },
      { path: 'power',     component: () => import('@/views/PowerView.vue'),   meta: { title: '供电仿真' } },
      { path: 'vehicle',   component: () => import('@/views/VehicleView.vue'), meta: { title: '车辆仿真' } },
      { path: 'track',     component: () => import('@/views/TrackView.vue'),   meta: { title: '轨道仿真' } },
      { path: 'signal',    component: () => import('@/views/SignalView.vue'),  meta: { title: '信号系统' } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
