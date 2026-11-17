import { describe, it, expect, afterEach } from 'vitest'
import { createPinia, defineStore, setActivePinia } from 'pinia'
import { ref, createApp } from 'vue'

import {
  storeResetPlugin,
  resetAllStores,
  clearPersistedDrafts,
  DEFAULT_EXCLUDED_STORE_IDS,
} from '../resetOnLogout'
import { BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY } from '@/core/stores/resetOnLogout'

// A stand-in for an ordinary feature store: primitives, a dictionary that
// can grow past its initial keys, and a nested object: the three shapes
// resetAllStores has to restore correctly.
const useTestStore = defineStore('__testStore', () => {
  const count = ref(0)
  const tags = ref<Record<string, boolean>>({})
  const profile = ref<{ info: Record<string, number> }>({ info: { a: 1 } })
  function increment(): void {
    count.value++
  }
  function tag(name: string): void {
    tags.value[name] = true
  }
  return { count, tags, profile, increment, tag }
})

function freshPinia(): void {
  const pinia = createPinia()
  // pinia.use() only takes effect immediately if the pinia instance is
  // already installed into a Vue app (pinia._a truthy); see pinia's own
  // createPinia(): otherwise the plugin is queued and only flushed into the
  // active plugin list inside install(app), i.e. on app.use(pinia). Calling
  // that install step here (a throwaway app, never mounted) is what main.ts
  // gets for free from `app.use(pinia)` during real bootstrap. Skipping it
  // in a test would silently leave storeResetPlugin never actually invoked,
  // and every assertion below would look like resetAllStores is a no-op.
  const app = createApp({})
  app.use(pinia)
  pinia.use(storeResetPlugin)
  setActivePinia(pinia)
}

describe('resetOnLogout, DEFAULT_EXCLUDED_STORE_IDS', () => {
  it('names exactly the 5 stores documented as surviving a reset', () => {
    // currentUser: logout()/sessionExpired() already tear it down deliberately.
    // layout/host/connection/loadingBar: device- or app-level, not user data.
    expect([...DEFAULT_EXCLUDED_STORE_IDS].sort()).toEqual(
      ['connection', 'currentUser', 'host', 'layout', 'loadingBar'].sort(),
    )
  })
})

describe('resetOnLogout, storeResetPlugin + resetAllStores', () => {
  afterEach(() => {
    localStorage.clear()
  })

  it('registers a store on first use and restores it to that state', () => {
    freshPinia()
    const store = useTestStore()
    store.increment()
    store.increment()
    expect(store.count).toBe(2)

    resetAllStores([])

    expect(store.count).toBe(0)
  })

  it('drops dictionary keys gained after registration rather than merging over them', () => {
    // This is the reason resetAllStores replaces each key wholesale inside
    // a $patch mutator instead of calling $patch(snapshot) directly:
    // $patch's object form deep-merges plain objects, so a plain merge
    // would keep whatever this added forever; see resetOnLogout.ts.
    freshPinia()
    const store = useTestStore()
    store.tag('row-42')
    expect(store.tags).toEqual({ 'row-42': true })

    resetAllStores([])

    expect(store.tags).toEqual({})
  })

  it('restores a nested object wholesale, dropping keys added inside it too', () => {
    freshPinia()
    const store = useTestStore()
    store.profile.info.b = 2
    expect(store.profile).toEqual({ info: { a: 1, b: 2 } })

    resetAllStores([])

    expect(store.profile).toEqual({ info: { a: 1 } })
  })

  it('leaves an excluded store untouched', () => {
    freshPinia()
    const store = useTestStore()
    store.increment()

    resetAllStores(['__testStore'])

    expect(store.count).toBe(1)
  })

  it('falls back to DEFAULT_EXCLUDED_STORE_IDS when no exclude list is given', () => {
    freshPinia()
    // Reuses a real excluded id so this exercises the actual default, not
    // just the exclusion mechanism in the abstract.
    const useHostLike = defineStore('host', () => {
      const value = ref('default')
      return { value }
    })
    const host = useHostLike()
    host.value = 'mutated'
    const other = useTestStore()
    other.increment()

    resetAllStores()

    expect(host.value).toBe('mutated')
    expect(other.count).toBe(0)
  })

  it('is a no-op for a store id that was never registered', () => {
    freshPinia()
    expect(() => resetAllStores(['store-that-does-not-exist'])).not.toThrow()
    expect(() => resetAllStores()).not.toThrow()
  })

  it('re-snapshots on re-registration rather than keeping a stale snapshot', () => {
    // The plugin's registry is module-level so it survives across pinia
    // instances (needed for this very test file's isolation between specs).
    // A store of the same id created under a *later* pinia must overwrite
    // the earlier snapshot, not have resetAllStores restore it to whatever
    // an unrelated, already-discarded pinia instance's store looked like.
    freshPinia()
    const first = useTestStore()
    first.increment()
    first.increment()
    expect(first.count).toBe(2)

    freshPinia()
    const second = useTestStore()
    second.increment()
    expect(second.count).toBe(1)

    resetAllStores([])

    expect(second.count).toBe(0)
  })
})

describe('resetOnLogout, clearPersistedDrafts', () => {
  afterEach(() => {
    localStorage.clear()
  })

  it('removes the batch demand-import draft key', () => {
    localStorage.setItem(BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY, JSON.stringify({ some: 'draft' }))

    clearPersistedDrafts()

    expect(localStorage.getItem(BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY)).toBeNull()
  })

  it('is a no-op when there is nothing to clear', () => {
    localStorage.removeItem(BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY)

    expect(() => clearPersistedDrafts()).not.toThrow()
  })
})
