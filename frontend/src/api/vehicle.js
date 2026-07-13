import http from './index'

export const getVehicleStatus  = ()            => http.get('/vehicle/status')
export const getVehicleHistory = (limit = 100) => http.get('/vehicle/history', { params: { limit } })
export const getManagedTrains = ()            => http.get('/vehicle/trains', { suppressErrorLog: true })

export function manageVehicle(payload) {
  return http.post('/vehicle/manage', payload, { suppressErrorLog: true })
}

// ---------------------------------------------------------------------------
// Driver Desk — 司机台状态接口
// GET /api/v1/vehicle/driver-desk           → 所有车辆
// GET /api/v1/vehicle/driver-desk/:id       → 单辆车
// ---------------------------------------------------------------------------
export const getAllDriverDesk = () =>
  http.get('/vehicle/driver-desk', { suppressErrorLog: true })

export const getDriverDesk = (vehicleId) =>
  http.get(`/vehicle/driver-desk/${vehicleId}`, { suppressErrorLog: true })

// ---------------------------------------------------------------------------
// Trip Status — 行驶状态接口（预留，后端实现后启用）
// GET /api/v1/vehicle/trip-status/:id
// 返回字段：from_station, to_station, distance_to_next_m, segment_length_m,
//           traveled_m, direction, speed_kmh, is_stopped
// ---------------------------------------------------------------------------
export const getTripStatus = (vehicleId) =>
  http.get(`/vehicle/trip-status/${vehicleId}`, { suppressErrorLog: true })
