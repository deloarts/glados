import { inject, type App, type InjectionKey } from 'vue'

/**
 * The list an app collects under `key`, created and provided on first use.
 * Plugins of several features add their entries to the same list while the
 * app is set up, and the page that renders them reads it back with
 * `inject(key)`, so the page never names the features that contribute.
 */
export function appRegistry<T>(app: App, key: InjectionKey<T[]>): T[] {
  const existing = app.runWithContext(() => inject(key, null))
  if (existing) return existing
  const created: T[] = []
  app.provide(key, created)
  return created
}
