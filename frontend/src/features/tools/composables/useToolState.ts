import { inject, onBeforeUnmount, provide, ref, toRaw, watch } from 'vue'
import type { InjectionKey, Ref } from 'vue'

/**
 * What a tool tab publishes so the surrounding tools view can save, compare
 * and print it. `inputs` is the tool's own state as a flat record of
 * strings, the form the tool also accepts back through
 * useInitialToolInputs() when a saved calculation is opened. `results` is a
 * plain, JSON-serialisable snapshot of what the tool shows; it is stored with
 * the calculation and compared on reopening.
 */
export interface ToolState {
  inputs: Record<string, string>
  results: Record<string, unknown>
  title: string
  /** One line describing the current inputs, shown in the page's info bar. */
  description?: string
}

const toolStateKey: InjectionKey<Ref<ToolState | null>> = Symbol('toolState')
const initialInputsKey: InjectionKey<() => Record<string, string> | null> =
  Symbol('initialToolInputs')

/** Called once by the tools view; the active tab writes into the returned ref. */
export function provideToolStateHost(): Ref<ToolState | null> {
  const state = ref<ToolState | null>(null)
  provide(toolStateKey, state)
  return state
}

/**
 * Called by a tool tab with a getter for its current state. The state is
 * cleared when the tab unmounts, so the next tab never shows the previous
 * tool's figures. A tab clears only what it published itself, because a tab
 * that was loaded before mounts and publishes before the previous one
 * unmounts. Outside the tools view (a component spec mounting the tab on its
 * own) there is no host and this does nothing.
 */
export function publishToolState(source: () => ToolState): void {
  const host = inject(toolStateKey, null)
  if (!host) return
  let published: ToolState | null = null
  watch(
    source,
    (next) => {
      published = next
      host.value = next
    },
    { immediate: true, deep: true },
  )
  onBeforeUnmount(() => {
    if (host.value !== null && toRaw(host.value) === published) host.value = null
  })
}

/**
 * Called by whatever hosts a tool (the tools view, the print view) to hand it
 * the inputs of the saved calculation being opened. The host remounts the
 * tool when that calculation changes, so a tool reads them once, at setup.
 */
export function provideInitialToolInputs(get: () => Record<string, string> | null): void {
  provide(initialInputsKey, get)
}

/**
 * The inputs a tool starts from: those of the saved calculation being opened,
 * or null when the tool starts cleared. A tool validates them like
 * any other untrusted input; a calculation saved by an older tool version may
 * hold values the tool no longer accepts.
 */
export function useInitialToolInputs(): Record<string, string> | null {
  const get = inject(initialInputsKey, null)
  return get ? get() : null
}

/**
 * Mount options for component specs: starts a tool on the given inputs and
 * captures what it publishes, as the tools view would.
 */
export function toolTestHost(inputs: Record<string, string> | null = null) {
  const state = ref<ToolState | null>(null)
  return {
    state,
    provide: {
      [toolStateKey as symbol]: state,
      [initialInputsKey as symbol]: () => inputs,
    },
  }
}
