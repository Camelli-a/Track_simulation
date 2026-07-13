import http from '@/api/index'

/**
 * REST 调试兜底：获取一帧 dashboard_snapshot
 */
export function fetchDashboardSnapshot() {
  return http.get('/dashboard/snapshot')
}

export function fetchDashboardSceneState() {
  return http.get('/dashboard/scene-state')
}

export function fetchStationYards(options = {}) {
  return http.get('/dashboard/stations/yards', options)
}

export function fetchStationYardsV2(options = {}) {
  return http.get('/dashboard/stations/yards/v2', options)
}

export function fetchLineLayout(options = {}) {
  return http.get('/dashboard/line-layout', options)
}

/**
 * 手动触发后端发布当前 track_info 到消息总线
 */
export function publishTrackInfo() {
  return http.post('/dashboard/publish-track-info')
}
