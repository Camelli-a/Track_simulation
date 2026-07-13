import http from '@/api/index'

export function getDriverDeskSimStatus() {
  return http.get('/driver-desk-sim/status', { suppressErrorLog: true })
}

export function startDriverDeskSim(payload) {
  return http.post('/driver-desk-sim/start', payload)
}

export function stopDriverDeskSim() {
  return http.post('/driver-desk-sim/stop', {})
}

export function updateDriverDeskSimInput(updates) {
  return http.patch('/driver-desk-sim/input', { updates })
}

export function pulseDriverDeskSim(fieldName, durationMs = null) {
  return http.post('/driver-desk-sim/pulse', {
    field_name: fieldName,
    ...(durationMs != null ? { duration_ms: durationMs } : {}),
  })
}
