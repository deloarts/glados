import { getCurrentInstance, getCurrentScope, onBeforeUnmount, onMounted, onScopeDispose } from 'vue'

const MINUTE_MS = 60_000

/**
 * Calls `onTick` once when it starts, then at every full minute of the
 * wall clock, for displays that only change once a minute (a clock icon, a
 * "worked so far today" figure). One timer is armed for the next minute
 * boundary and re-armed from the current time after each tick, so the
 * ticks stay on the boundary instead of drifting, and there is no
 * per-second polling. Browsers throttle timers in background tabs, so a
 * tab becoming visible again ticks at once and re-aligns the timer.
 *
 * Inside a component it starts on mount and stops before unmount, so the
 * first render never depends on the time. Outside one it starts right away
 * and stops with the surrounding effect scope.
 */
export function useMinuteTick(onTick: () => void): void {
  let timer: ReturnType<typeof setTimeout> | null = null
  let running = false

  function clearTimer(): void {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  function arm(): void {
    clearTimer()
    const delay = MINUTE_MS - (Date.now() % MINUTE_MS)
    timer = setTimeout(() => {
      timer = null
      onTick()
      arm()
    }, delay)
  }

  function onVisibilityChange(): void {
    if (!running || document.visibilityState !== 'visible') return
    onTick()
    arm()
  }

  function start(): void {
    if (running) return
    running = true
    onTick()
    arm()
    document.addEventListener('visibilitychange', onVisibilityChange)
  }

  function stop(): void {
    running = false
    clearTimer()
    document.removeEventListener('visibilitychange', onVisibilityChange)
  }

  if (getCurrentInstance()) {
    onMounted(start)
    onBeforeUnmount(stop)
  } else {
    start()
    if (getCurrentScope()) onScopeDispose(stop)
  }
}
