import { computed, getCurrentScope, onScopeDispose, shallowRef, watch } from 'vue'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { readLocalDraft, removeLocalDraft, writeLocalDraft } from '../utils/localDraft'
import type { LocalDraft } from '../utils/localDraft'

/** How long the screen has to stay still before its changes are written down. */
export const LOCAL_DRAFT_WRITE_MS = 250

export interface LocalDraftOptions<V> {
  /** Names the copy, such as "checklist.42"; null while nothing is open. */
  key: () => string | null
  /** The document's last save on the server; a copy written against another one is stale. */
  base: () => string | null
  /** The unsaved changes on screen, or null when there are none. */
  value: () => V | null
}

export interface LocalDraftOffer<V> {
  draft: LocalDraft<V>
  /** The document was saved again after the copy was written. */
  stale: boolean
}

/**
 * Keeps the unsaved changes of the open document in this browser while they
 * exist, and drops the copy once the screen matches the saved document
 * again. When a document is opened the page calls check(): an existing copy
 * becomes the offer, and nothing is written or dropped for that document
 * until the page settles the offer with accept(), discard() or dismiss().
 * A dismissed copy is kept until new changes replace it.
 */
export function useLocalDraft<V>(options: LocalDraftOptions<V>) {
  const currentUserStore = useCurrentUserStore()
  const userId = computed(() => currentUserStore.user?.id ?? null)
  const offer = shallowRef<LocalDraftOffer<V> | null>(null)

  // The copy that was looked for; until then the stored copy is left alone.
  let checkedKey: string | null = null
  // A dismissed copy survives a screen without changes.
  let held = false
  let pending: { userId: number; key: string; value: V | null; base: string | null } | null = null
  let timer: ReturnType<typeof setTimeout> | null = null

  function flush(): void {
    if (timer) clearTimeout(timer)
    timer = null
    const write = pending
    pending = null
    if (!write) return
    if (write.value === null) removeLocalDraft(write.userId, write.key)
    else writeLocalDraft(write.userId, write.key, write.value, write.base)
  }

  watch(
    () => [userId.value, options.key(), options.value()] as const,
    ([uid, key, value]) => {
      if (uid === null || key === null || key !== checkedKey || offer.value) return
      if (value === null && held) return
      held = false
      // A copy is a snapshot; later changes on screen must not reach into it.
      pending = { userId: uid, key, value: value === null ? null : (JSON.parse(JSON.stringify(value)) as V), base: options.base() }
      if (timer) clearTimeout(timer)
      timer = setTimeout(flush, LOCAL_DRAFT_WRITE_MS)
    },
    { deep: true },
  )

  // Another document opened in the same page starts unchecked. A page may
  // check the new document before this runs, which then stays checked.
  watch(options.key, (key) => {
    if (key === checkedKey) return
    flush()
    checkedKey = null
    offer.value = null
    held = false
  })

  /** Looks for a copy of the open document and offers it; call once it is loaded. */
  function check(): void {
    flush()
    const uid = userId.value
    const key = options.key()
    checkedKey = key
    held = false
    offer.value = null
    if (uid === null || key === null) return
    const draft = readLocalDraft<V>(uid, key)
    if (draft) offer.value = { draft, stale: draft.base !== options.base() }
  }

  /** Takes the offered changes; the page puts them on screen right away, and they are kept from then on. */
  function accept(): V | null {
    const taken = offer.value
    offer.value = null
    held = false
    return taken ? taken.draft.value : null
  }

  /** Drops the offered copy for good. */
  function discard(): void {
    const uid = userId.value
    const key = checkedKey
    offer.value = null
    held = false
    if (uid !== null && key !== null) removeLocalDraft(uid, key)
  }

  /** Puts the offer aside; the copy stays until new changes replace it. */
  function dismiss(): void {
    offer.value = null
    held = true
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('pagehide', flush)
    if (getCurrentScope()) {
      onScopeDispose(() => {
        window.removeEventListener('pagehide', flush)
        flush()
      })
    }
  }

  return { offer, check, accept, discard, dismiss, flush }
}

export type LocalDraftHandle<V> = ReturnType<typeof useLocalDraft<V>>
