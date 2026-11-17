/**
 * When the user last did something on the page: clicked, typed, scrolled or
 * touched. Every request to the backend reports the seconds since then in
 * IDLE_HEADER, and the backend restarts the session's idle timeout only for
 * that activity, never for a request the app sends on its own, such as a
 * poll or a refresh after a live signal. Opening the page counts as
 * activity.
 */

export const IDLE_HEADER = 'X-Glados-Idle-Seconds'

const EVENTS = ['pointerdown', 'keydown', 'wheel', 'touchstart'] as const

let lastInteraction = Date.now()
let reported = 0

function markInteraction(): void {
  lastInteraction = Date.now()
}

/** Starts listening for the user's input; returns what stops it again. */
export function installUserActivityTracking(target: Window = window): () => void {
  for (const event of EVENTS) target.addEventListener(event, markInteraction, { capture: true, passive: true })
  return () => {
    for (const event of EVENTS) target.removeEventListener(event, markInteraction, true)
  }
}

/** The time of the user's last input, in milliseconds since the epoch. */
export function lastInteractionAt(): number {
  return lastInteraction
}

/** The idle report for a request; the activity counts as reported from then on. */
export function idleHeaders(): Record<string, string> {
  reported = lastInteraction
  const seconds = Math.max(0, Math.floor((Date.now() - lastInteraction) / 1000))
  return { [IDLE_HEADER]: String(seconds) }
}

/** Whether the user did something no request has reported yet. */
export function hasUnreportedActivity(): boolean {
  return lastInteraction > reported
}
