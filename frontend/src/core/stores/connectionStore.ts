import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'

// Unauthenticated, so a logged-out tab gets a real answer instead of a 401
// that would trip sessionExpired() in a loop.
const PROBE_URL = `${import.meta.env.VITE_API_URL ?? ''}/health`

// One failure is not an outage: a phone waking its radio often times out
// once, which looks exactly like an unreachable server.
const FAILURE_THRESHOLD = 2

// Jittered, so clients do not retry in lockstep after a deploy.
const PROBE_DELAYS_MS = [2000, 5000, 10000, 30000]
const PROBE_JITTER_RATIO = 0.2
const PROBE_TIMEOUT_MS = 10000

/**
 * App-wide "can we reach the server" state.
 *
 * Detection is passive: the api interceptor reports every request's
 * outcome, and nothing is polled while healthy, since a heartbeat would keep
 * a mobile radio awake. Probing starts only once offline, when no other
 * traffic may be left, and stops at the first success.
 */
export const useConnectionStore = defineStore('connection', () => {
  const isOffline = ref(false)
  // Drives the footer's retry affordance; a probe in flight shows as
  // "Reconnecting…" rather than an idle button the user may click again.
  const isProbing = ref(false)

  // Plain closure state; none of this drives a template.
  let failures = 0
  let attempt = 0
  let probeTimeout: ReturnType<typeof setTimeout> | null = null

  function clearPendingProbe(): void {
    if (probeTimeout !== null) {
      clearTimeout(probeTimeout)
      probeTimeout = null
    }
  }

  function scheduleProbe(): void {
    // Mobile browsers freeze background timers, so probing resumes when the
    // tab returns.
    if (probeTimeout !== null || document.visibilityState === 'hidden') return

    const index = Math.min(attempt, PROBE_DELAYS_MS.length - 1)
    const base = PROBE_DELAYS_MS[index] ?? PROBE_DELAYS_MS[0]!
    attempt++
    const jitter = base * PROBE_JITTER_RATIO
    const delay = base + (Math.random() * 2 - 1) * jitter

    probeTimeout = setTimeout(() => {
      probeTimeout = null
      void probe()
    }, delay)
  }

  /** Marks the connection healthy and stops any recovery probing. */
  function reportSuccess(): void {
    failures = 0
    attempt = 0
    clearPendingProbe()
    isOffline.value = false
  }

  /**
   * Reports a request that never reached the server. Only flips the state
   * once FAILURE_THRESHOLD of them land in a row.
   */
  function reportFailure(): void {
    failures++
    if (failures < FAILURE_THRESHOLD) return

    if (!isOffline.value) {
      isOffline.value = true
      attempt = 0
    }
    scheduleProbe()
  }

  async function probe(): Promise<void> {
    // A probe is already in flight; it reschedules itself on failure, so
    // dropping this one keeps the chain intact rather than doubling it.
    if (isProbing.value) return
    isProbing.value = true

    try {
      // Bare axios, not the app's api instance: this must not carry the
      // Authorization header or go through the 401 -> sessionExpired
      // interceptor, and it must not recurse back into this store.
      await axios.get(PROBE_URL, { timeout: PROBE_TIMEOUT_MS })
      reportSuccess()
    } catch (error) {
      // Any answer at all, a 503 included, proves the network path is up.
      // The server being unhappy is a different problem from it being
      // unreachable, and not one the footer speaks to.
      if (axios.isAxiosError(error) && error.response) reportSuccess()
      else reportFailure()
    } finally {
      isProbing.value = false
    }
  }

  /**
   * Manual retry, from the footer. Drops back to the shortest delay so a
   * user who knows their wifi is back does not wait out a 30s step.
   */
  function retryNow(): void {
    clearPendingProbe()
    attempt = 0
    void probe()
  }

  function handleOffline(): void {
    // `navigator.onLine === false` is trustworthy and skips the threshold.
    // The reverse is not, which is why nothing here treats `online` as
    // proof of health; it only means an interface exists, not that
    // anything is reachable, so handleOnline probes instead of asserting.
    failures = FAILURE_THRESHOLD
    isOffline.value = true
    attempt = 0
    scheduleProbe()
  }

  function handleOnline(): void {
    if (isOffline.value) retryNow()
  }

  function handleVisibilityChange(): void {
    if (document.visibilityState === 'hidden') {
      clearPendingProbe()
      return
    }
    if (isOffline.value) retryNow()
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('offline', handleOffline)
    window.addEventListener('online', handleOnline)
    document.addEventListener('visibilitychange', handleVisibilityChange)
  }

  return {
    isOffline,
    isProbing,
    reportSuccess,
    reportFailure,
    retryNow,
  }
})
