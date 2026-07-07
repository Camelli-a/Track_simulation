import http from './index'

export const getPowerStatus  = ()            => http.get('/power/status')
export const getPowerHistory = (limit = 100) => http.get('/power/history', { params: { limit } })
