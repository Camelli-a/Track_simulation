import http from './index'

export const getTrackStatus   = () => http.get('/track/status')
export const getTrackSegments = () => http.get('/track/segments')
