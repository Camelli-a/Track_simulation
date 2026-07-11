import http from './index'

export const getVehicleStatus  = ()            => http.get('/vehicle/status')
export const getVehicleHistory = (limit = 100) => http.get('/vehicle/history', { params: { limit } })
export const getManagedTrains = ()            => http.get('/vehicle/trains', { suppressErrorLog: true })

export function manageVehicle(payload) {
  return http.post('/vehicle/manage', payload, { suppressErrorLog: true })
}
