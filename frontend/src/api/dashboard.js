import http from '@/api/index'

/**
 * REST 调试兜底：获取一帧 dashboard_snapshot
 */
export function fetchDashboardSnapshot() {
  return http.get('/dashboard/snapshot')
}
