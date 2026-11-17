import { computed, ref, watch } from 'vue'
import type { Ref, WatchSource } from 'vue'
import { useI18n } from 'vue-i18n'

import { usePermissions } from '@/core/composables/usePermissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import type { ControlledDocument } from '../types'
import { useDocumentLock } from './useDocumentLock'
import { useLocalDraft } from './useLocalDraft'

/** The steps on a controlled document that its page offers as buttons. */
export type DocumentAction = 'edit' | 'release' | 'revise' | 'invalidate' | 'delete'

/** A controlled document as the lifecycle reads it: the control fields, its creator and its last save. */
export type LifecycleDocument = ControlledDocument & { creator_id: number; changed: string | null }

/** The permissions of one document type. */
export interface DocumentPermissions {
  /** Edits, revises and deletes; someone else's draft also needs `manage`. */
  write: string
  /** Marks a released revision invalid and takes over someone else's editing. */
  manage: string
  release: string
}

/** The calls of a document type's API the lifecycle makes. */
export interface ControlledDocumentApi<T> {
  get: (id: number) => Promise<T>
  lock: (id: number, takeOver: boolean) => Promise<T>
  unlock: (id: number, force?: boolean) => Promise<T>
  release: (id: number) => Promise<T>
  markInvalid: (id: number, reason: string) => Promise<T>
  revise: (id: number, reason: string) => Promise<T>
  remove: (id: number) => Promise<unknown>
}

/** What a document type's own condition for offering an action can build on. */
export interface OfferedContext {
  /** Whether the shared rules alone offer the action. */
  standard: boolean
  /** Whether this page holds the edit lock. */
  editing: boolean
}

export interface ControlledDocumentOptions<T extends LifecycleDocument, D, B extends string> {
  /** The open record, which the edit lock and the kept changes follow. */
  document: Ref<T | null>
  /** The record the actions and permissions apply to, when it differs from `document`. */
  current?: Readonly<Ref<T | null>>
  /** Changes when the page opens another revision; editing of the one left behind ends then. */
  opened: WatchSource<unknown>
  /** The live resource the document's changes are signalled on. */
  resource: string
  api: ControlledDocumentApi<T>
  permissions: DocumentPermissions
  /** Puts a record the server answered with on screen. */
  show: (saved: T) => void | Promise<void>
  /** Takes over a fresh copy from the lock; by default only the record moves on while editing. */
  apply?: (loaded: T, editing: boolean) => void
  /** Puts the screen back to the saved record when editing is discarded; by default `show`. */
  revert?: (saved: T) => void
  draft: {
    /** Names the kept copy together with the record id, such as "checklist". */
    name: string
    /** The unsaved changes on screen, or null when there are none. */
    value: () => D | null
    /** Puts kept changes back on screen; without it restoreDraft() does nothing. */
    restore?: (value: D) => void
    /** Whether kept changes can be put on screen now. */
    restorable?: () => boolean
  }
  /** A document type's own condition for offering an action, in place of the shared one. */
  offered?: Partial<Record<DocumentAction, (context: OfferedContext) => boolean>>
  /** Why the document cannot be released right now, in the order they are shown. */
  releaseBlockers?: () => B[]
  /** Runs after the lock was taken over by someone else, before the kept changes are offered. */
  onLost?: () => void
  /** Whether the kept changes are offered again when editing ended for inactivity; true by default. */
  offerDraftAfterIdle?: boolean
  afterStartEditing?: () => Promise<void>
  afterRelease?: (released: T) => Promise<void>
  afterRevise?: (created: T) => Promise<void>
  afterRemove?: () => Promise<void>
}

const ACTIONS: readonly DocumentAction[] = ['edit', 'release', 'revise', 'invalidate', 'delete']

/**
 * The lifecycle a controlled document page shares with every other one: the
 * edit lock, the copy of unsaved changes kept in this browser, what the user
 * may do with the open revision and the actions that move it on. The page
 * keeps its own content, how it is saved and what it reloads after a step.
 *
 * Each action is offered when the document's state allows it and is
 * possible when the user also holds the permissions it needs. An action
 * that is offered but not possible names the missing permission in
 * `missing`, so the page shows it disabled and says what is missing rather
 * than hiding it.
 *
 * Leaving the revision, or the page, ends editing of it.
 */
export function useControlledDocument<T extends LifecycleDocument, D, B extends string = never>(
  options: ControlledDocumentOptions<T, D, B>,
) {
  const { t } = useI18n()
  const { hasPermission } = usePermissions()
  const currentUserStore = useCurrentUserStore()
  const { document, api, permissions } = options
  const current = options.current ?? document
  const busy = ref(false)

  /** Who took over editing from this page, one entry per take-over, for the page to tell the user. */
  const lostBy = ref<Array<string | null>>([])
  /** Counts the times editing ended because nobody worked on the page, for the page to tell the user. */
  const idleEnded = ref(0)

  const lock = useDocumentLock({
    document,
    resource: options.resource,
    lock: api.lock,
    unlock: api.unlock,
    reload: api.get,
    apply:
      options.apply ??
      ((loaded, editing) => {
        if (editing) document.value = loaded
        else void options.show(loaded)
      }),
    onLost: (by) => {
      lostBy.value.push(by)
      options.onLost?.()
      draft.check()
    },
    onIdle: () => {
      idleEnded.value += 1
      if (options.offerDraftAfterIdle ?? true) draft.check()
    },
  })

  watch(options.opened, () => {
    const left = document.value
    if (left && lock.editing.value) api.unlock(left.id).catch(() => {})
  })

  const draft = useLocalDraft<D>({
    key: () => (document.value ? `${options.draft.name}.${document.value.id}` : null),
    base: () => document.value?.changed ?? null,
    value: options.draft.value,
  })

  // ── Permissions ─────────────────────────────────────────────────────

  const userId = computed(() => currentUserStore.user?.id ?? null)
  const canManage = computed(() => hasPermission(permissions.manage))
  const canWrite = computed(() => hasPermission(permissions.write))
  const isOwn = computed(() => current.value?.creator_id === userId.value)
  const isLatest = computed(() => current.value?.is_latest === true)
  const released = computed(() => current.value?.released_at != null)
  const isDraft = computed(() => !!current.value && !current.value.read_only)

  // An action restricted to the creator needs the manage permission on
  // someone else's document.
  const ownOrManage = (): string | null => (isOwn.value || canManage.value ? null : permissions.manage)
  /** The permission an action lacks, or null when the user holds every one it needs. */
  const missing = computed<Record<DocumentAction, string | null>>(() => ({
    edit: canWrite.value ? ownOrManage() : permissions.write,
    release: hasPermission(permissions.release) ? null : permissions.release,
    revise: canWrite.value ? null : permissions.write,
    invalidate: canManage.value ? null : permissions.manage,
    delete: canWrite.value ? ownOrManage() : permissions.write,
  }))

  const standardOffered = computed<Record<DocumentAction, boolean>>(() => ({
    edit: isDraft.value && !lock.editing.value && lock.lockedByOther.value === null,
    release: !!current.value && !released.value && isLatest.value,
    revise: !!current.value && isLatest.value && released.value && !lock.editing.value,
    invalidate: released.value && current.value?.invalid_at == null,
    // A released revision is kept as a record; only a draft is deleted.
    delete: !!current.value && isLatest.value && !released.value,
  }))
  /** Whether the state of the document allows each action, whatever the user's rights. */
  const offered = computed<Record<DocumentAction, boolean>>(() => {
    const standard = standardOffered.value
    const editing = lock.editing.value
    const result = { ...standard }
    for (const action of ACTIONS) {
      const own = options.offered?.[action]
      if (own) result[action] = own({ standard: standard[action], editing })
    }
    return result
  })

  /** Whether the user may change the open draft, once they hold its lock. */
  const canChange = computed(() => isDraft.value && missing.value.edit === null)
  /** Whether Edit can be pressed: the user may change the draft and nobody else edits it. */
  const canEdit = computed(() => offered.value.edit && missing.value.edit === null)
  /** Whether the content on screen can be changed now. */
  const editable = computed(() => canChange.value && lock.editing.value)
  const canTakeOver = computed(() => canChange.value && canManage.value && lock.lockedByOther.value !== null)
  /**
   * Why taking over someone else's editing cannot be pressed: the permission
   * the user lacks, or '' when it can be pressed or the draft is not locked
   * by someone else. Take over stays visible but disabled with this tooltip.
   */
  const takeOverBlocked = computed(() => {
    if (!isDraft.value || lock.lockedByOther.value === null || canTakeOver.value) return ''
    const permission = missing.value.edit ?? (canManage.value ? null : permissions.manage)
    return permission ? t('documents.permissionMissing', { permission: permissionLabel(t, permission) }) : ''
  })
  const releaseBlockers = computed<B[]>(() => options.releaseBlockers?.() ?? [])
  const canRelease = computed(
    () => offered.value.release && missing.value.release === null && releaseBlockers.value.length === 0,
  )
  const canMarkInvalid = computed(() => offered.value.invalidate && missing.value.invalidate === null)
  const canRevise = computed(() => offered.value.revise && missing.value.revise === null)
  const canDelete = computed(() => offered.value.delete && missing.value.delete === null)

  /** Why the kept changes cannot be restored now, or null when they can. */
  const draftBlocked = computed<string | null>(() => {
    if (!canChange.value) return t('documents.draft.blocked')
    const other = lock.lockedByOther.value
    return other ? t('documents.draft.lockedBy', { name: other.name }) : null
  })

  // ── Actions ─────────────────────────────────────────────────────────

  /** Runs a request with the page marked busy. */
  async function run<R>(action: () => Promise<R>): Promise<R> {
    busy.value = true
    try {
      return await action()
    } finally {
      busy.value = false
    }
  }

  async function release(): Promise<void> {
    const doc = current.value
    if (!doc) return
    await run(async () => {
      const saved = await api.release(doc.id)
      await options.show(saved)
      await options.afterRelease?.(saved)
    })
  }

  async function markInvalid(reason: string): Promise<void> {
    const doc = current.value
    if (!doc) return
    await run(async () => options.show(await api.markInvalid(doc.id, reason)))
  }

  async function startEditing(takeOver = false): Promise<void> {
    await lock.startEditing(takeOver)
    await options.afterStartEditing?.()
  }

  /** Ends editing without saving: the screen goes back to what is saved. */
  async function discard(): Promise<void> {
    const doc = document.value
    if (!doc) return
    if (options.revert) options.revert(doc)
    else void options.show(doc)
    await lock.stopEditing()
  }

  /** Takes the edit lock if needed and puts the kept changes back on screen. */
  async function restoreDraft(): Promise<void> {
    const restore = options.draft.restore
    if (!draft.offer.value || !restore || !(options.draft.restorable?.() ?? true)) return
    if (!lock.editing.value) await startEditing()
    const value = draft.accept()
    if (!value) return
    restore(value)
  }

  /** Starts the next revision and returns it. */
  async function revise(reason: string): Promise<T | null> {
    const doc = current.value
    if (!doc) return null
    return run(async () => {
      const created = await api.revise(doc.id, reason)
      await options.afterRevise?.(created)
      return created
    })
  }

  async function remove(): Promise<void> {
    const doc = current.value
    if (!doc) return
    await run(() => api.remove(doc.id))
    draft.discard()
    await options.afterRemove?.()
  }

  return {
    busy,
    run,
    lock,
    lostBy,
    idleEnded,
    draft,
    draftBlocked,
    released,
    isLatest,
    isOwn,
    offered,
    missing,
    canChange,
    canEdit,
    editable,
    canTakeOver,
    takeOverBlocked,
    releaseBlockers,
    canRelease,
    canMarkInvalid,
    canRevise,
    canDelete,
    release,
    markInvalid,
    startEditing,
    discard,
    restoreDraft,
    revise,
    remove,
  }
}
