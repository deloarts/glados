import { computed, ref } from 'vue'

import { useEasterEggs } from '@/core/composables/useEasterEggs'

/** The only string this whole thing exists to display. */
export const CAKE_PHRASE = 'The cake is a lie'

export type CakePhase = 'idle' | 'converting' | 'glitch' | 'collapse' | 'terminal'

// The sequence escalates in three steps, and each one only starts once the
// last has had a moment to register: the conversion runs completely clean, then
// the shell starts shaking, then the red arrives, then it dies.

/** Act 1: every text on screen becomes the phrase, one node after another. */
const CONVERT_MS = 4000
/** Act 2: the shell jitters. Geometry only, no colour yet. */
const GLITCH_MS = 900
/** Act 2b: how far into the jitter the red washes in. */
const RED_AT_MS = 350
/** Act 3: the CRT squeeze to a line, then to a dot. */
const COLLAPSE_MS = 500
/** How long the terminal types before it starts winding up. */
const TERMINAL_MS = 13000
/** A beat of silence after the typing stops, before the reset line. */
const HOLD_MS = 900
/** How long the reset line sits there before the page actually reloads. */
const RESET_MS = 3000

/** The last thing on screen. Read as en-GB to match the rest of the app. */
export const CAKE_RESET_LINE = 'Initialising reset ...'

/** Where the terminal is in its own little sequence. */
export type CakeTerminalStage = 'typing' | 'hold' | 'resetting'
/** Reduced-motion replacement for act 2: a plain fade, no jitter, no squeeze. */
const REDUCED_COLLAPSE_MS = 300

/** Never rewrite text inside these, since it isn't user-visible prose. */
const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'TITLE', 'NOSCRIPT', 'TEXTAREA'])

/**
 * Marks a subtree the sweep must leave alone. The cake dialogs carry it so
 * they stay readable if one is still animating closed as the sweep starts.
 */
const EXEMPT_SELECTOR = '[data-cake-exempt]'

// ── DOM helpers (exported for tests, since they need no timers to verify) ───

/**
 * Every text node under `root` that the sweep is allowed to rewrite.
 *
 * Two things it deliberately never reaches, both of which matter: icon fonts
 * paint through `::before` content rather than text nodes, so **icons survive**
 * and the screen stays legible as something rather than a wall of nothing; and
 * `<input>`/`<textarea>` values are properties rather than text nodes, so
 * **what the user has typed is never rewritten**.
 */
export function collectCakeTargets(root: ParentNode & Node): Text[] {
  if (typeof document === 'undefined') return []

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node: Node): number {
      if (!node.nodeValue?.trim()) return NodeFilter.FILTER_REJECT

      const parent = node.parentElement
      if (!parent) return NodeFilter.FILTER_REJECT
      if (SKIP_TAGS.has(parent.tagName)) return NodeFilter.FILTER_REJECT
      if (parent.closest(EXEMPT_SELECTOR)) return NodeFilter.FILTER_REJECT

      return NodeFilter.FILTER_ACCEPT
    },
  })

  const nodes: Text[] = []
  let node = walker.nextNode()
  while (node) {
    nodes.push(node as Text)
    node = walker.nextNode()
  }
  return nodes
}

/**
 * Swap the prose but keep the surrounding whitespace, so neighbouring inline
 * nodes don't run together into "lieThe cake".
 */
export function cakeify(value: string): string {
  return value.replace(/\S[\s\S]*\S|\S/, CAKE_PHRASE)
}

// ── Module state ────────────────────────────────────────────────────────────

const phase = ref<CakePhase>('idle')
const terminalStage = ref<CakeTerminalStage>('typing')

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function setHtmlClass(name: string, on: boolean): void {
  document.documentElement.classList.toggle(name, on)
}

// ── The conversion ──────────────────────────────────────────────────────────

/**
 * Converts every target across `CONVERT_MS`, driven by a single rAF loop that
 * advances an index pointer, not one timer per node, so the pacing holds
 * whether the page has 40 text nodes or 4000.
 */
function convert(onDone: () => void): void {
  const targets = collectCakeTargets(document.body)
  const total = targets.length
  if (total === 0) {
    onDone()
    return
  }

  const startedAt = performance.now()
  let index = 0

  const step = (now: number): void => {
    const progress = Math.min(1, (now - startedAt) / CONVERT_MS)
    const target = Math.ceil(progress * total)

    while (index < target) {
      const node = targets[index]!
      if (node.isConnected) node.nodeValue = cakeify(node.nodeValue ?? '')
      index++
    }

    if (progress >= 1) {
      onDone()
      return
    }
    requestAnimationFrame(step)
  }

  requestAnimationFrame(step)
}

// ── Public API ──────────────────────────────────────────────────────────────

/**
 * The sequence. It is deliberately **one-way**: there is no Escape, no
 * click-to-dismiss, nothing the user can do to cut it short. It ends by
 * reloading the page itself once the terminal has had its ~13 seconds, which
 * is also why nothing here bothers to record the original strings. Anything
 * unsaved on the page is lost, the same as on any other reload.
 */
function run(): void {
  if (phase.value !== 'idle') return

  const reduced = prefersReducedMotion()

  document.body.style.overflow = 'hidden'
  phase.value = 'converting'

  convert(() => {
    if (reduced) {
      // No jitter, no red, no squeeze, just a fade into the terminal.
      collapse(REDUCED_COLLAPSE_MS)
      return
    }

    phase.value = 'glitch'
    setHtmlClass('cake-glitch', true)
    // The red follows the jitter rather than arriving with it, so the shake
    // lands as its own beat first.
    setTimeout(() => setHtmlClass('cake-red', true), RED_AT_MS)
    setTimeout(() => collapse(COLLAPSE_MS), GLITCH_MS)
  })
}

function collapse(durationMs: number): void {
  phase.value = 'collapse'
  // The collapse owns the shell's transform from here, so the jitter animation
  // has to come off or the two fight over the same property. `cake-red` stays
  // on, since the CRT line burns out red.
  setHtmlClass('cake-glitch', false)
  setHtmlClass('cake-collapse', true)
  // Black goes on *before* the squeeze, not after it. The shell paints its own
  // background, so as it shrinks it uncovers whatever is behind it, which is
  // the app's normal light surface until this lands.
  setHtmlClass('cake-dark', true)

  setTimeout(enterTerminal, durationMs)
}

/**
 * The terminal winds down rather than cutting out: it types, falls silent for a
 * beat, announces the reset, and only then reloads. Flat timers off a single
 * start point rather than nested ones, so the schedule reads as a schedule.
 *
 * The app comes back by reloading, not by being restored. The sequence never
 * recorded the original strings, and a reload is the same exit the user would
 * otherwise have had to perform by hand.
 */
function enterTerminal(): void {
  phase.value = 'terminal'
  terminalStage.value = 'typing'

  setTimeout(() => (terminalStage.value = 'hold'), TERMINAL_MS)
  setTimeout(() => (terminalStage.value = 'resetting'), TERMINAL_MS + HOLD_MS)
  setTimeout(resetAndReload, TERMINAL_MS + HOLD_MS + RESET_MS)
}

/**
 * The sequence's final step. Named and exported so the "a reset really does
 * reset everything" rule is verifiable without driving 17 seconds of timers.
 */
export function resetAndReload(): void {
  // A reset that left the app red and calling itself Aperture Science would not
  // be much of a reset, and aperture mode is the one piece of this that
  // survives a reload on its own, since it persists to localStorage.
  useEasterEggs().setAperture(false)
  // The overflow lock and every cake class go with the document itself.
  globalThis.location?.reload()
}

export function useCakeProtocol() {
  return {
    phase: computed(() => phase.value),
    terminalStage: computed(() => terminalStage.value),
    isRunning: computed(() => phase.value !== 'idle'),
    isTerminal: computed(() => phase.value === 'terminal'),
    run,
  }
}
