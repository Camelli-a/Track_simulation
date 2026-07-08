/** 线性插值 */
export function lerp(a, b, t) {
  return a + (b - a) * t
}

/** 角度插值（最短路径，度） */
export function lerpAngle(fromDeg, toDeg, t) {
  let delta = ((toDeg - fromDeg + 180) % 360) - 180
  if (delta < -180) delta += 360
  return fromDeg + delta * t
}

/** smoothstep 缓动 */
export function smoothstep(t) {
  const x = Math.min(1, Math.max(0, t))
  return x * x * (3 - 2 * x)
}

/**
 * 里程插值，支持环线回绕
 * @param {number|null} totalLength 全线长度；为 null 时线性插值
 */
export function interpolatePosition(from, to, t, totalLength = null) {
  if (from == null || to == null) return to ?? from ?? 0
  if (totalLength == null || totalLength <= 0) {
    return lerp(from, to, t)
  }

  let delta = to - from
  if (delta > totalLength / 2) delta -= totalLength
  if (delta < -totalLength / 2) delta += totalLength

  let pos = from + delta * t
  if (pos < 0) pos += totalLength
  if (pos >= totalLength) pos -= totalLength
  return pos
}
