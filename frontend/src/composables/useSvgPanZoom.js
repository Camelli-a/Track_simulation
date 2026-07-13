import { ref, computed, onBeforeUnmount } from 'vue'

/**
 * SVG viewBox 平移/缩放（滚轮缩放 · 拖拽平移）
 */
export function useSvgPanZoom(getBaseViewBox) {
  const panX = ref(0)
  const panY = ref(0)
  const zoom = ref(1)
  const dragging = ref(false)
  const lastPt = ref(null)
  const containerSize = ref({ w: 800, h: 400 })

  const viewBoxString = computed(() => {
    const base = getBaseViewBox()
    const w = base.width / zoom.value
    const h = base.height / zoom.value
    const cx = base.x + base.width / 2
    const cy = base.y + base.height / 2
    const x = cx - w / 2 + panX.value
    const y = cy - h / 2 + panY.value
    return `${x} ${y} ${w} ${h}`
  })

  function setContainer(el) {
    if (el) {
      containerSize.value = { w: el.clientWidth || 800, h: el.clientHeight || 400 }
    }
  }

  function reset() {
    panX.value = 0
    panY.value = 0
    zoom.value = 1
  }

  /** 将世界坐标 (viewBox) 点居中到视口 */
  function panToWorld(wx, wy) {
    const base = getBaseViewBox()
    const cx = base.x + base.width / 2
    const cy = base.y + base.height / 2
    panX.value = wx - cx
    panY.value = wy - cy
  }

  /** 平滑平移到目标（每帧调用，factor 0~1） */
  function smoothPanToWorld(wx, wy, factor = 0.14) {
    const base = getBaseViewBox()
    const cx = base.x + base.width / 2
    const cy = base.y + base.height / 2
    const tx = wx - cx
    const ty = wy - cy
    panX.value += (tx - panX.value) * factor
    panY.value += (ty - panY.value) * factor
  }

  function onWheel(event) {
    event.preventDefault()
    const factor = event.deltaY > 0 ? 0.92 : 1.08
    zoom.value = Math.min(5, Math.max(0.35, zoom.value * factor))
  }

  function onPointerMove(event) {
    if (!dragging.value || !lastPt.value) return
    const base = getBaseViewBox()
    const { w, h } = containerSize.value
    const scaleX = base.width / zoom.value / w
    const scaleY = base.height / zoom.value / h
    panX.value -= (event.clientX - lastPt.value.x) * scaleX
    panY.value -= (event.clientY - lastPt.value.y) * scaleY
    lastPt.value = { x: event.clientX, y: event.clientY }
  }

  function onPointerUp() {
    dragging.value = false
    lastPt.value = null
    window.removeEventListener('mousemove', onPointerMove)
    window.removeEventListener('mouseup', onPointerUp)
  }

  function onPointerDown(event) {
    if (event.button !== 0) return
    const target = event.target
    if (target?.closest?.('[data-pan-ignore="true"]')) return
    setContainer(event.currentTarget)
    dragging.value = true
    lastPt.value = { x: event.clientX, y: event.clientY }
    window.addEventListener('mousemove', onPointerMove)
    window.addEventListener('mouseup', onPointerUp)
  }

  onBeforeUnmount(onPointerUp)

  return {
    viewBoxString,
    zoom,
    panX,
    panY,
    dragging,
    reset,
    panToWorld,
    smoothPanToWorld,
    onWheel,
    onPointerDown,
    onPointerMove,
    onPointerUp,
  }
}
