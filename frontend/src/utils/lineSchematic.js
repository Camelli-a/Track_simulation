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

const stationNameMap = {
  GGZ: '郭公庄（换乘房山线）',
  FSP: '丰台科技园',
  KYL: '科怡路',
  FTN: '丰台南路（换乘16号线）',
  FTD: '丰台东大街',
  QLZ: '七里庄（换乘14号线）',
  LLQ: '六里桥（换乘10号线）',
  LLE: '六里桥东',
  BWR: '北京西站（换乘7号线，可出站换乘国铁）',
  JBG: '军事博物馆（换乘1号线/八通线）',
  BDZ: '白堆子',
  BQS: '白石桥南（换乘6号线）',
  GTG: '国家图书馆（换乘4号线大兴线、16号线）',
}

export function stationLabel(name) {
  return stationNameMap[name] ?? name
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
