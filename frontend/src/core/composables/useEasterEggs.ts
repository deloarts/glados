import { computed, getCurrentScope, onScopeDispose, ref } from 'vue'

import { useConfetti } from '@/core/composables/useConfetti'
import { safeStorage } from '@/core/utils/safeStorage'

const STORAGE_KEY = 'apertureMode'

const KONAMI = [
  'arrowup',
  'arrowup',
  'arrowdown',
  'arrowdown',
  'arrowleft',
  'arrowright',
  'arrowleft',
  'arrowright',
  'b',
  'a',
]

/**
 * The preset the Konami code unlocks. It is filtered out of the account page's
 * theme picker unless aperture mode is on, so this is the only way to reach it.
 */
export const APERTURE_PRESET = 'Nora'

/**
 * The red primary aperture mode paints over the user's own. Painted rather
 * than selected: the user's real choice stays recorded so it can be put back
 * when the mode is switched off. See colorPalettes.ts for the palette itself.
 */
export const APERTURE_PRIMARY = 'aperture'

/**
 * Branding aperture mode imposes, overriding whatever the deployment has
 * configured: a customer's own name and footer text would rather defeat the
 * point of the reference. Both revert the moment the mode is switched off;
 * nothing here is persisted or sent to the server.
 */
export const APERTURE_BRAND = 'Glados'
export const APERTURE_FOOTER = 'Aperture Science'

// Module-scope singleton, the same shape as the layout store: one listener for
// the whole tab, and state that outlives any component that reads it.
const apertureMode = ref(false)
/**
 * Bumped to summon the cake outside its weekly window. A counter rather than a
 * boolean so CakeEasterEgg can watch it and re-summon on every code entry,
 * not just the first.
 */
const cakeSummons = ref(0)

let buffer: string[] = []
let initialised = false

function readStored(): boolean {
  return safeStorage.get(STORAGE_KEY) === 'true'
}

/**
 * Typing "b" in the header search box must not count towards the code, and
 * that box takes focus readily.
 */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable
}

function applyClass(): void {
  document.documentElement.classList.toggle('aperture-mode', apertureMode.value)
}

function setAperture(value: boolean): void {
  apertureMode.value = value
  applyClass()
  // Blocked storage only costs the mode its persistence across reloads.
  safeStorage.set(STORAGE_KEY, String(value))
}

function toggleAperture(): void {
  setAperture(!apertureMode.value)
  if (!apertureMode.value) return

  // Both already no-op under reduced motion / without a canvas.
  void useConfetti().celebrate()
  cakeSummons.value++
}

function onKeydown(event: KeyboardEvent): void {
  if (isTypingTarget(event.target)) {
    buffer = []
    return
  }

  // A sliding window rather than an explicit reset, so a fumbled start doesn't
  // require lifting off and beginning again. Only the last ten keys matter.
  buffer.push(event.key.toLowerCase())
  if (buffer.length > KONAMI.length) buffer.shift()
  if (buffer.length < KONAMI.length) return
  if (!buffer.every((key, index) => key === KONAMI[index])) return

  buffer = []
  toggleAperture()
}

/**
 * Called once from App.vue's onMounted, beside initDefaultTheme(). That call
 * happens after an `await`, with no active effect scope by then, so
 * onScopeDispose below is a no-op there and the listener lives for the whole
 * tab, same as before. It only matters for a caller that does run inside a
 * scope, tests included, which get automatic cleanup for free.
 */
export function initEasterEggs(): void {
  if (initialised || typeof window === 'undefined') return
  initialised = true

  apertureMode.value = readStored()
  applyClass()
  window.addEventListener('keydown', onKeydown)

  if (getCurrentScope()) {
    onScopeDispose(disposeEasterEggs)
  }
}

/**
 * Undoes initEasterEggs(): removes the keydown listener and resets the
 * initialised guard, so a later initEasterEggs() call re-attaches it. Safe to
 * call even when never initialised.
 */
export function disposeEasterEggs(): void {
  if (!initialised || typeof window === 'undefined') return
  window.removeEventListener('keydown', onKeydown)
  initialised = false
}

export function useEasterEggs() {
  return {
    apertureMode: computed(() => apertureMode.value),
    cakeSummons: computed(() => cakeSummons.value),
    setAperture,
    toggleAperture,
  }
}
