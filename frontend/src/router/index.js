import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/layouts/DefaultLayout.vue'),
    children: [
      { path: '', redirect: '/line' },
      {
        path: 'line',
        component: () => import('@/views/DashboardView.vue'),
        meta: {
          title: '全线态势',
          section: '线路底座',
          subtitle: '把线路、信号、联锁和 MA 放在同一工作台里，先判断全线正在发生什么。',
          opsHint: '先看线路主视图，再看分区占用、联锁冲突和时间轴；站序图支持点击车站下钻站场。',
        },
      },
      {
        path: 'cab',
        component: () => import('@/views/VehicleView.vue'),
        meta: {
          title: '列车驾驶室',
          section: '车端状态',
          subtitle: '聚焦单车驾驶与监督，查看速度、MA、制动曲线和控制反馈。',
          opsHint: '先选车，再核对速度与 MA 裕量；普通牵引/制动只对手动模式车辆开放。',
        },
      },
      {
        path: 'power',
        component: () => import('@/views/PowerView.vue'),
        meta: {
          title: '供电与故障',
          section: '边界约束',
          subtitle: '围绕网压健康、分车负荷、回馈制动和故障回放观察供电边界。',
          opsHint: '先看电压趋势，再看分车功率排行和故障前后对比，快速判断影响范围。',
        },
      },
      { path: 'dashboard', redirect: '/line' },
      { path: 'track', redirect: '/line' },
      { path: 'signal', redirect: '/line' },
      { path: 'vehicle', redirect: '/cab' },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = to.meta?.title ? `${to.meta.title} | 轨道仿真系统` : '轨道仿真系统'
})

export default router
