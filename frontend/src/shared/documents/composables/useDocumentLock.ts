import { computed, getCurrentScope, onScopeDispose, ref, watch } from 'vue'
import type { Ref } from 'vue'

import { useLiveStore } from '@/core/realtime/liveStore'
import { lastInteractionAt } from '@/core/session/userActivity'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { ControlledDocument } from '../types'

/** How often the lease of a held lock is renewed while the user works; the backend lease is 15 minutes. */
export const LOCK_RENEW_MS = 5 * 60 * 1000
/** Editing ends after this long without input, before the backend lease runs out. */
export const LOCK_IDLE_MS = 13 * 60 * 1000
const LOCK_CHECK_MS = 60 * 1000

export interface DocumentLockOptions<T extends ControlledDocument> {
  /** The open document, null while nothing is open. */
  document: Ref<T | null>
  /** The live resource the document's changes are signalled on. */
  resource: string
  lock: (id: number, takeOver: boolean) => Promise<T>
  /** With `force`, ends someone else's lock; needs the manage permission. */
  unlock: (id: number, force?: boolean) => Promise<T>
  /** Reads the document again, quietly, after another user changed it. */
  reload: (id: number) => Promise<T>
  /** Takes over a fresh copy of the document; the page decides what to keep. */
  apply: (document: T, editing: boolean) => void
  /** The lock was taken over by someone else while this page was editing. */
  onLost?: (by: string | null) => void
  /** Editing ended because nobody worked on the page for LOCK_IDLE_MS. */
  onIdle?: () => void
}

/**
 * The edit lock of a controlled document as a page uses it: Edit takes the
 * lock, Save, Discard or leaving end it, and changes by other users arrive
 * through the live stream, so the page shows who edits the document and
 * notices when its own lock is taken over.
 *
 * The lease is renewed only while the user works on the page. A page left
 * alone ends its editing after LOCK_IDLE_MS, so a forgotten page neither
 * blocks the document nor keeps the session alive with its renewals.
 */
export function useDocumentLock<T extends ControlledDocument>(options: DocumentLockOptions<T>) {
  const live = useLiveStore()
  const currentUserStore = useCurrentUserStore()
  const userId = computed(() => currentUserStore.user?.id ?? null)
  const busy = ref(false)

  const editing = computed(
    () => options.document.value?.locked_by_id != null && options.document.value.locked_by_id === userId.value,
  )
  /** Who else edits the document now, or null. */
  const lockedByOther = computed(() => {
    const doc = options.document.value
    if (!doc || doc.locked_by_id == null || doc.locked_by_id === userId.value) return null
    return { name: doc.locked_by_full_name ?? '', since: doc.locked_at }
  })

  async function withBusy<R>(action: () => Promise<R>): Promise<R> {
    busy.value = true
    try {
      return await action()
    } finally {
      busy.value = false
    }
  }

  /** Takes the lock, or with `takeOver` the lock of the person editing now. */
  async function startEditing(takeOver = false): Promise<void> {
    const doc = options.document.value
    if (!doc) return
    const locked = await withBusy(() => options.lock(doc.id, takeOver))
    options.apply(locked, true)
  }

  /** Ends editing; a lock that is no longer held is left alone. */
  async function stopEditing(): Promise<void> {
    const doc = options.document.value
    if (!doc || !editing.value) return
    const unlocked = await withBusy(() => options.unlock(doc.id))
    options.apply(unlocked, false)
  }

  /** Ends someone else's editing without taking the lock; for managers. */
  async function endOthersEditing(): Promise<void> {
    const doc = options.document.value
    if (!doc || lockedByOther.value === null) return
    const unlocked = await withBusy(() => options.unlock(doc.id, true))
    options.apply(unlocked, false)
  }

  async function lost(): Promise<void> {
    const doc = options.document.value
    if (!doc) return
    const fresh = await options.reload(doc.id)
    options.apply(fresh, false)
    options.onLost?.(fresh.locked_by_full_name)
  }

  let timer: ReturnType<typeof setInterval> | null = null
  // Editing starts with a click, so it counts as activity of its own.
  let editingSince = 0
  let lastRenewal = 0
  const lastActivity = (): number => Math.max(lastInteractionAt(), editingSince)

  function stopWatching(): void {
    if (timer) clearInterval(timer)
    timer = null
  }

  async function idle(): Promise<void> {
    const doc = options.document.value
    if (!doc || !editing.value) return
    stopWatching()
    const ended = await withBusy(() => options.unlock(doc.id)).catch(() => null)
    const fresh = ended ?? (await options.reload(doc.id).catch(() => null))
    if (fresh) options.apply(fresh, false)
    options.onIdle?.()
  }

  function tick(): void {
    const doc = options.document.value
    if (!doc) return
    const now = Date.now()
    if (lastActivity() > lastRenewal && now - lastRenewal >= LOCK_RENEW_MS) {
      lastRenewal = now
      options.lock(doc.id, false).catch(() => void lost())
    } else if (now - lastActivity() >= LOCK_IDLE_MS) {
      void idle()
    }
  }

  watch(
    editing,
    (now) => {
      stopWatching()
      if (!now) return
      editingSince = lastRenewal = Date.now()
      timer = setInterval(tick, LOCK_CHECK_MS)
    },
    { immediate: true },
  )

  async function onSignal(id: number): Promise<void> {
    const doc = options.document.value
    if (!doc || doc.id !== id) return
    const wasEditing = editing.value
    const fresh = await options.reload(id).catch(() => null)
    if (!fresh) return
    const stillEditing = fresh.locked_by_id != null && fresh.locked_by_id === userId.value
    options.apply(fresh, stillEditing)
    if (wasEditing && !stillEditing) options.onLost?.(fresh.locked_by_full_name)
  }

  const unsubscribe = live.on(options.resource, (signal) => {
    if (signal.action === 'updated') void onSignal(signal.id)
  })

  if (getCurrentScope()) {
    onScopeDispose(() => {
      unsubscribe()
      stopWatching()
      // Leaving the page ends editing; the lease runs out by itself if
      // this request never arrives.
      if (editing.value && options.document.value) {
        options.unlock(options.document.value.id).catch(() => {})
      }
    })
  }

  return { editing, lockedByOther, busy, startEditing, stopEditing, endOthersEditing }
}

export type DocumentLock = ReturnType<typeof useDocumentLock>
