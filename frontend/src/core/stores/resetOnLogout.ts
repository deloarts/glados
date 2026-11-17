import { nextTick } from 'vue'
import type { PiniaPluginContext } from 'pinia'

import { bumpFetchEpoch } from '@/core/composables/useSequencedFetch'
import { safeStorage } from '@/core/utils/safeStorage'
import { cancelDraftWrite } from './draftWrites'

// Persisted draft keys cleared on logout. They live in core so feature
// adapters depend on core, never the other way around.
export const BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY = 'glados.batchDemandImport.draft.v2'

export const BATCH_MADE_ITEM_DEMAND_IMPORT_DRAFT_STORAGE_KEY =
  'glados.batchMadeItemDemandImport.draft.v1'

export const BOUGHT_ITEM_IMPORT_DRAFT_STORAGE_KEY = 'glados.boughtItemImport.draft.v1'

// Add a new draft key here, and only here, to have it cleared on logout.
const PERSISTED_DRAFT_STORAGE_KEYS: readonly string[] = [
  BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY,
  BATCH_MADE_ITEM_DEMAND_IMPORT_DRAFT_STORAGE_KEY,
  BOUGHT_ITEM_IMPORT_DRAFT_STORAGE_KEY,
]

/**
 * Stores that survive resetAllStores() because they hold device or server
 * state rather than the ended session's data. Too few entries wipe a
 * device preference, too many leak per-user data to the next sign-in.
 * currentUser tears itself down, layout is a device preference, host
 * describes the server, connection the network, and resetting loadingBar
 * would desync it from requests still in flight.
 */
export const DEFAULT_EXCLUDED_STORE_IDS: readonly string[] = [
  'currentUser',
  'layout',
  'host',
  'connection',
  'loadingBar',
]

interface RegisteredStore {
  initialState: Record<string, unknown>
  patch: (mutator: (state: Record<string, unknown>) => void) => void
}

const registeredStores = new Map<string, RegisteredStore>()

/**
 * Deep-clones plain JSON-shaped store state. `structuredClone` throws on
 * the reactive Proxy, while plain property reads unwrap it.
 */
function clonePlainState<T>(value: T): T {
  if (Array.isArray(value)) return value.map((item) => clonePlainState(item)) as T
  if (value !== null && typeof value === 'object') {
    const result: Record<string, unknown> = {}
    for (const key of Object.keys(value as Record<string, unknown>)) {
      result[key] = clonePlainState((value as Record<string, unknown>)[key])
    }
    return result as T
  }
  return value
}

/**
 * Pinia plugin that snapshots every store's initial state, because setup
 * stores have no working `$reset()`.
 */
export function storeResetPlugin({ store }: PiniaPluginContext): void {
  registeredStores.set(store.$id, {
    initialState: clonePlainState(store.$state as Record<string, unknown>),
    patch: (mutator) => store.$patch(mutator),
  })
}

/**
 * Restores every registered store except `exclude` to its initial state.
 *
 * Each key is assigned inside a `$patch` mutator. The object form of
 * `$patch` deep-merges, so keys added since registration would survive, and
 * deleting a key first would orphan the ref the setup store exposes. A plain
 * assignment replaces the value through the existing ref.
 *
 * The fetch epoch is bumped first, so a refresh still in flight cannot
 * repopulate a reset store with pre-logout data.
 */
export function resetAllStores(exclude: readonly string[] = DEFAULT_EXCLUDED_STORE_IDS): void {
  bumpFetchEpoch()

  for (const [id, { initialState, patch }] of registeredStores) {
    if (exclude.includes(id)) continue

    patch((state) => {
      for (const key of Object.keys(initialState)) {
        state[key] = clonePlainState(initialState[key])
      }
    })
  }
}

/**
 * Removes persisted drafts so they do not resurface for the next user.
 * Call after resetAllStores(). The draft stores' watchers schedule a write
 * of the reset draft a tick later, so after nextTick() that write is
 * cancelled and the keys are removed again.
 */
export function clearPersistedDrafts(): void {
  const clear = (): void => {
    for (const key of PERSISTED_DRAFT_STORAGE_KEYS) {
      cancelDraftWrite(key)
      safeStorage.remove(key)
    }
  }
  clear()
  void nextTick().then(clear)
}
