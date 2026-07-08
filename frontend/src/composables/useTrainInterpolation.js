import { ref, watch, onBeforeUnmount, toValue } from 'vue'
import { interpolatePosition, lerp, smoothstep } from '@/utils/interpolate'

/**
 * WebSocket tick 之间用 rAF 平滑插值列车位置 / MA
 * @param {import('vue').MaybeRefOrGetter<Array>} vehiclesSource
 * @param {{ totalLength?: import('vue').MaybeRefOrGetter<number|null>, paused?: import('vue').MaybeRefOrGetter<boolean>, durationMs?: number }} options
 */
export function useTrainInterpolation(vehiclesSource, options = {}) {
  const defaultDuration = options.durationMs ?? 200
  const displayVehicles = ref([])
  const animating = ref(false)

  const states = new Map()
  let rafId = null
  let lastTickAt = 0

  function currentList() {
    return toValue(vehiclesSource) ?? []
  }

  function rebuildStatic() {
    displayVehicles.value = currentList().map((v) => ({ ...v }))
    animating.value = false
  }

  function onTick(newList) {
    const now = performance.now()
    const interval = lastTickAt
      ? Math.max(80, Math.min(500, now - lastTickAt))
      : defaultDuration
    lastTickAt = now

    const ids = new Set()
    for (const v of newList) {
      ids.add(v.vehicle_id)
      const prev = states.get(v.vehicle_id)
      states.set(v.vehicle_id, {
        from: prev?.to ?? v,
        to: v,
        startAt: now,
        duration: interval,
      })
    }
    for (const id of [...states.keys()]) {
      if (!ids.has(id)) states.delete(id)
    }

    if (!rafId) rafId = requestAnimationFrame(tick)
  }

  function tick() {
    if (toValue(options.paused)) {
      rebuildStatic()
      rafId = null
      return
    }

    const now = performance.now()
    const totalLength = toValue(options.totalLength)
    const list = []
    let still = false

    for (const [, s] of states) {
      const rawT = s.duration <= 0 ? 1 : Math.min(1, (now - s.startAt) / s.duration)
      const t = smoothstep(rawT)
      const from = s.from
      const to = s.to

      const position = interpolatePosition(from.position, to.position, t, totalLength)
      let ma_limit = to.ma_limit
      if (from.ma_limit != null && to.ma_limit != null) {
        ma_limit = lerp(from.ma_limit, to.ma_limit, t)
      }

      list.push({ ...to, position, ma_limit })
      if (rawT < 1) still = true
    }

    displayVehicles.value = list
    animating.value = still
    rafId = still ? requestAnimationFrame(tick) : null
  }

  watch(
    vehiclesSource,
    (list) => {
      if (!list?.length) {
        states.clear()
        displayVehicles.value = []
        animating.value = false
        return
      }
      onTick(list)
    },
    { deep: true, immediate: true },
  )

  watch(
    () => toValue(options.paused),
    (paused) => {
      if (paused) {
        if (rafId) {
          cancelAnimationFrame(rafId)
          rafId = null
        }
        rebuildStatic()
      }
    },
  )

  onBeforeUnmount(() => {
    if (rafId) cancelAnimationFrame(rafId)
  })

  return { displayVehicles, animating }
}
