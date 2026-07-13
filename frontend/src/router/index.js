import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/layouts/DefaultLayout.vue'),
    children: [
      { path: '', redirect: '/line' },
      {
        path: 'line',
        component: () => import('@/views/OverviewView.vue'),
        meta: {
          title: '全线态势',
          section: '线路底座',
          subtitle: '把线路、信号、联锁和 MA 放在同一工作台里，先判断全线正在发生什么。',
          opsHint: '先看线路主视图，再看分区占用、联锁冲突和时间轴；站序图支持点击车站下钻站场。',
        },
      },
      {
        path: 'cab',
        component: () => import('@/views/StoppingControlView.vue'),
        meta: {
          title: '停车控制',
          section: '车端状态',
          subtitle: '聚焦单车停车控制与诊断，查看场景关键指标、控制来源、ATP 保护和停车结果。',
          opsHint: '先从运行总览页选中车辆，再在这里核对速度、MA、控制来源和 ATP 介入情况。',
        },
      },
      {
        path: 'signal',
        component: () => import('@/views/SignalConstraintView.vue'),
        meta: {
          title: '信号与联锁',
          section: '线路约束',
          subtitle: '解释当前车辆为什么收到现在这条 MA，信号、区段、道岔和进路哪一环在约束它。',
          opsHint: '先看信号约束摘要，再看前方约束链和联锁冲突列表，最后用 MA 来源解释组织讲解。',
        },
      },
      {
        path: 'fault',
        component: () => import('@/views/FaultInjectionView.vue'),
        meta: {
          title: '故障注入与演示控制',
          section: '演示控制',
          subtitle: '聚焦异常触发、演示动作和结果确认，把“怎么触发”和“触发后发生了什么”放在同一页。',
          opsHint: '优先使用已接后端的真实演示动作；待后端补接口的注入项当前只做能力占位和对接提示。',
        },
      },
      {
        path: 'power',
        component: () => import('@/views/PowerView.vue'),
        meta: {
          title: '供电页（兼容）',
          section: '兼容入口',
          subtitle: '保留旧版供电监测页面，便于迁移期间对照使用。',
          opsHint: '该页面当前不在主导航中；若需保留供电视角，可后续再并入新的四页结构。',
        },
      },
      { path: 'dashboard', redirect: '/line' },
      { path: 'track', redirect: '/line' },
      {
        path: 'vehicle',
        component: () => import('@/views/VehicleView.vue'),
        meta: {
          title: '列车驾驶室（旧版）',
          section: '兼容入口',
          subtitle: '保留旧版车辆管理与控车页面，便于迁移期间对照使用。',
          opsHint: '该页面仍保留旧的车辆管理和控车逻辑，后续会逐步并入新的停车控制页。',
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
