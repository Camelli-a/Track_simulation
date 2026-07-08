/** 北京地铁9号线 · 线路示意图坐标换算 */
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
  const fullNames = {
    GGZ: '郭公庄',
    FSP: '丰台科技园',
    KYL: '科怡路',
    FTN: '丰台南路',
    FTD: '丰台东大街',
    QLZ: '七里庄',
    LLQ: '六里桥',
    LLE: '六里桥东',
    BWR: '北京西站',
    JBG: '军事博物馆',
    BDZ: '白堆子',
    BQS: '白石桥南',
    GTG: '国家图书馆',
  }
  return fullNames[name] ?? name
}

export function aspectColor(aspect) {
  if (aspect === 'red') return '#ef4444'
  if (aspect === 'yellow') return '#eab308'
  return '#34d399'
}

/** 列车标记横向错开，避免重叠 */
export function trainLane(index) {
  return (index % 3) - 1
}
