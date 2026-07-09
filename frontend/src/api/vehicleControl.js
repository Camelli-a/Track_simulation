import http from '@/api/index'

/**
 * 发送控车指令（手动停车 / 紧急制动）
 * C 同学后续转发至 ZMQ driver_input 或 A 组 train_state 输入
 */
export function sendVehicleControl({ vehicle_id, command, level = 1, source = 'hmi' }) {
  return http.post('/vehicle/control', {
    vehicle_id,
    command,
    level,
    source,
  })
}
