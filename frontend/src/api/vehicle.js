import http from './index'

export const getVehicleStatus  = ()            => http.get('/vehicle/status')
export const getVehicleHistory = (limit = 100) => http.get('/vehicle/history', { params: { limit } })
