import http from '@/api/index'

/**
 * 发送控车指令。
 * 兼容手动牵引/制动/紧急制动，也兼容后端已经支持的 ATO 目标速度/目标位置参数。
 */
export function sendVehicleControl(payload) {
  const {
    vehicle_id,
    command,
    level = 1,
    source = 'hmi',
    line_id = 'LINE-1',
    direction = 'forward',
    traction_level = 0,
    brake_level = 0,
    target_speed,
    target_position,
    reason,
  } = payload

  return http.post('/vehicle/control', {
    vehicle_id,
    line_id,
    command,
    level,
    source,
    direction,
    traction_level,
    brake_level,
    ...(target_speed != null ? { target_speed } : {}),
    ...(target_position != null ? { target_position } : {}),
    ...(reason ? { reason } : {}),
  })
}
