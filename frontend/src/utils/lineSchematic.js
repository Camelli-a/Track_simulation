/** 通用线路示意图坐标换算 */
export function positionToRatio(position, totalLength) {
  if (!totalLength) return 0
  return Math.min(1, Math.max(0, position / totalLength))
}

export function positionToX(position, totalLength, padX, drawWidth) {
  return padX + positionToRatio(position, totalLength) * drawWidth
}

export function positionToY(position, totalLength, padY, drawHeight) {
  return padY + positionToRatio(position, totalLength) * drawHeight
}

export function stationLabel(name) {
  return name
}

export function aspectColor(aspect) {
  if (aspect === 'red') return '#fb7185'
  if (aspect === 'yellow') return '#f59e0b'
  return '#38bdf8'
}

/** 列车标记横向错开，避免重叠 */
export function trainLane(index) {
  return (index % 3) - 1
}
