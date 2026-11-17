import { computed, inject, type Component, type ComputedRef, type InjectionKey } from 'vue'

/**
 * What the explained page knows about its current state, handed to the
 * components a help doc embeds, e.g. the auto-plan doc highlights the picked
 * algorithm. Strings only, so the help content imports no feature types.
 */
export type HelpContext = Record<string, string | undefined>

/**
 * The help system a page shows its explanations through. The app shell
 * installs the real one, the handbook, at the app level, so shared code and
 * features can offer help without importing the feature that provides it.
 */
export interface HelpProvider {
  /** Whether a doc exists for the slug. A page without one shows no help control. */
  has(slug: string | undefined): boolean
  /**
   * The drawer that shows one doc. It takes the props `slug`, `anchor` and
   * `context` and opens through `v-model:visible`.
   */
  drawer: Component
}

export const helpProviderKey: InjectionKey<HelpProvider> = Symbol('helpProvider')

// Without an installed provider there is nothing to explain with, so every
// help control renders nothing rather than a button that opens an empty drawer.
const NO_HELP: HelpProvider = {
  has: () => false,
  drawer: () => null,
}

/** Reads the help provider the app shell installed. */
export function useHelp(): HelpProvider {
  return inject(helpProviderKey, NO_HELP)
}

export const helpContextKey: InjectionKey<ComputedRef<HelpContext>> = Symbol('helpContext')

const EMPTY_CONTEXT: ComputedRef<HelpContext> = computed(() => ({}))

/**
 * Reads the context the page passed along with its help doc, for a component
 * the doc embeds. Defaults to empty for a doc read as a full page.
 */
export function useHelpContext(): ComputedRef<HelpContext> {
  return inject(helpContextKey, EMPTY_CONTEXT)
}
