import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/layouts/DefaultLayout.vue'),
    children: [
      { path: '',          redirect: '/dashboard' },
      {
        path: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: {
          title: 'OCC 调度中心',
          section: '全局总览',
          subtitle: '观察全线列车、供电、告警与调度态势。',
          opsHint: '先确认连接和告警，再切换沙盘模式查看当前运行区段。',
        },
      },
      {
        path: 'power',
        component: () => import('@/views/PowerView.vue'),
        meta: {
          title: '供电仿真',
          section: '供电监视',
          subtitle: '关注接触网电压、电流和多车牵引负荷。',
          opsHint: '优先观察电压波动与故障态，再结合车辆负荷判断影响范围。',
        },
      },
      {
        path: 'vehicle',
        component: () => import('@/views/VehicleView.vue'),
        meta: {
          title: '车辆仿真',
          section: '列车控制',
          subtitle: '查看 ATP/ATO/手动模式下的列车状态与停车精度。',
          opsHint: '键盘控车仅在本页生效，且只对手动模式车辆启用。',
        },
      },
      {
        path: 'track',
        component: () => import('@/views/TrackView.vue'),
        meta: {
          title: '轨道仿真',
          section: '线路态势',
          subtitle: '查看区段占用、车站分布与线路剖面。',
          opsHint: '切换电子地图、站序图和里程展开，可快速定位区段问题。',
        },
      },
      {
        path: 'signal',
        component: () => import('@/views/SignalView.vue'),
        meta: {
          title: '信号系统',
          section: '联锁与授权',
          subtitle: '检查闭塞、信号机、道岔和各车移动授权。',
          opsHint: '先看联锁与道岔，再核对 MA 剩余距离是否充足。',
        },
      },
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
