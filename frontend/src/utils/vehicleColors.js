const PALETTE = [
  '#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6',
  '#06b6d4', '#f97316', '#84cc16', '#e11d48', '#6366f1',
  '#14b8a6', '#a855f7', '#0ea5e9', '#d946ef', '#65a30d',
]

const assigned = new Map()

/** 按车辆 ID 首次出现顺序分配颜色，支持动态 N 车 */
export function getVehicleColor(vehicleId) {
  if (!assigned.has(vehicleId)) {
    assigned.set(vehicleId, PALETTE[assigned.size % PALETTE.length])
  }
  return assigned.get(vehicleId)
}

/** 移除已下线的车辆颜色缓存（可选，避免长期运行 ID 膨胀） */
export function pruneVehicleColors(activeIds) {
  const active = new Set(activeIds)
  for (const id of assigned.keys()) {
    if (!active.has(id)) assigned.delete(id)
  }
}
