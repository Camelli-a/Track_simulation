import http from './index'

export const getSignalStatus = () => http.get('/signal/status')
export const getSignalLights = () => http.get('/signal/lights')
