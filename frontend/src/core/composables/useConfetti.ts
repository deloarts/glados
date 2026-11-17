import type { Options as ConfettiOptions } from 'canvas-confetti'

/** Viewport coordinates, in pixels. */
export interface ConfettiOrigin {
  x: number
  y: number
}

/**
 * Last known pointer position, in viewport (client) coordinates. Kept as a
 * plain variable rather than a ref, it is only ever read at the moment a
 * burst fires, so there is nothing to react to and no reason to pay for
 * reactivity on every mouse move.
 */
let pointer: ConfettiOrigin | null = null
let tracking = false

/** Above OpenVue's dialog/overlay layer, which tops out around 1100. */
const Z_INDEX = 10000

function trackPointer(): void {
  if (tracking || typeof window === 'undefined') return
  tracking = true

  const remember = (event: PointerEvent): void => {
    pointer = { x: event.clientX, y: event.clientY }
  }

  // `pointerdown` as well as `pointermove` so a tap on a touch screen, which
  // never hovers, still gives us an origin.
  window.addEventListener('pointermove', remember, { passive: true })
  window.addEventListener('pointerdown', remember, { passive: true })
}

function canRender(): boolean {
  if (typeof window === 'undefined' || typeof document === 'undefined') return false

  // No real 2D canvas in jsdom under vitest, where the animation would throw.
  try {
    return Boolean(document.createElement('canvas').getContext?.('2d'))
  } catch {
    return false
  }
}

/**
 * Translate viewport pixels into the 0–1 fractions `canvas-confetti` expects,
 * falling back to the middle of the screen when the pointer position is
 * unknown, a keyboard-triggered action, for instance.
 */
function toOrigin(point: ConfettiOrigin | null): ConfettiOptions['origin'] {
  if (!point) return { x: 0.5, y: 0.5 }

  return {
    x: point.x / window.innerWidth,
    y: point.y / window.innerHeight,
  }
}

export function useConfetti() {
  trackPointer()

  /**
   * Fire a radial burst of confetti outwards from the mouse cursor.
   *
   * Two overlapping shots: a dense, slower core followed by a faster, finer
   * ring, which reads as an explosion rather than a single flat pop. Pass an
   * `origin` in viewport pixels to burst somewhere other than the cursor.
   *
   * canvas-confetti is loaded on demand rather than bundled with the app: it
   * is a decorative extra that most sessions never trigger.
   */
  async function celebrate(origin?: ConfettiOrigin): Promise<void> {
    if (!canRender()) return

    try {
      const { default: confetti } = await import('canvas-confetti')

      const shared: ConfettiOptions = {
        origin: toOrigin(origin ?? pointer),
        spread: 360,
        zIndex: Z_INDEX,
        colors: ['#22c55e', '#3b82f6', '#f59e0b', '#ec4899', '#a855f7'],
        // canvas-confetti honours the OS reduced-motion setting for us.
        disableForReducedMotion: true,
      }

      void confetti({ ...shared, particleCount: 70, startVelocity: 28, scalar: 1, ticks: 110 })
      void confetti({ ...shared, particleCount: 45, startVelocity: 50, scalar: 0.75, ticks: 140 })
    } catch {
      // Never let a decorative animation break the action that triggered it,
      // whether the chunk fails to load or the animation itself throws.
    }
  }

  /** Stop any running burst and clear the canvas. */
  async function stop(): Promise<void> {
    const { default: confetti } = await import('canvas-confetti')
    confetti.reset()
  }

  return { celebrate, stop }
}
