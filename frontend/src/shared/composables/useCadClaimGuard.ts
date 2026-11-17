import { reactive, watch } from 'vue'

/** The part of a bought or made item the guard reads. */
export interface CadClaimable {
  id: number
  data_source: string
}

export type CadClaimReason = 'claimed' | 'claimedMeanwhile'

/** A catalogue list read filtered to one id, such as `getBoughtItems`. */
export type CadClaimRead = (params: {
  id: number
  limit: number
}) => Promise<{ items: readonly CadClaimable[] }>

/** A catalogue edit store: the table selection the edit panel works on. */
export interface CadClaimSelection<T extends CadClaimable> {
  readonly selectedItems: readonly T[]
  readonly editMode: boolean
  setSelectedItems(items: T[]): void
}

export type CadClaimGuard = ReturnType<typeof useCadClaimGuard>

/**
 * Warns before a catalogue item that PDM has claimed is edited in the web.
 *
 * A CAD item is edited in the SolidWorks file; PDM may overwrite what the
 * web changes (docs/FIELD_OWNERSHIP.md). The backend takes no lock against a
 * claim landing while a form is open, so the form asks the user twice: when
 * it opens on a CAD item, and when a fresh read at save, or a live update
 * while editing, shows an item turned CAD since. An item the user already
 * agreed to edit is not asked about again until `reset`.
 *
 * Render `CadClaimDialog` with the guard.
 */
export function useCadClaimGuard() {
  const dialog = reactive({
    visible: false,
    reason: 'claimed' as CadClaimReason,
    count: 0,
  })

  const acknowledged = new Set<number>()
  let pendingIds: number[] = []
  let resolver: ((proceed: boolean) => void) | null = null

  function settle(proceed: boolean): void {
    const resolve = resolver
    resolver = null
    if (proceed) for (const id of pendingIds) acknowledged.add(id)
    pendingIds = []
    resolve?.(proceed)
  }

  function unacknowledgedCad(items: readonly CadClaimable[]): number[] {
    return items
      .filter((item) => item.data_source === 'CAD' && !acknowledged.has(item.id))
      .map((item) => item.id)
  }

  function ask(reason: CadClaimReason, ids: number[]): Promise<boolean> {
    if (ids.length === 0) return Promise.resolve(true)
    // A question still open is answered as dismissed; the newer one replaces it.
    settle(false)
    pendingIds = ids
    dialog.reason = reason
    dialog.count = ids.length
    dialog.visible = true
    return new Promise((resolve) => {
      resolver = resolve
    })
  }

  /** The dialog's confirm handler. */
  function confirm(): void {
    settle(true)
  }

  /**
   * The dialog's visibility handler; closing it without confirming declines.
   * The dialog closes itself before it emits confirm, so the decline waits a
   * microtask and lets a confirm that follows settle first.
   */
  function onVisibleChange(visible: boolean): void {
    dialog.visible = visible
    if (visible) return
    const asked = resolver
    void Promise.resolve().then(() => {
      if (resolver === asked && asked !== null) settle(false)
    })
  }

  /** Asks when the form opens on items PDM has claimed. */
  function confirmOpen(items: readonly CadClaimable[]): Promise<boolean> {
    return ask('claimed', unacknowledgedCad(items))
  }

  /** Asks when a live update shows an item claimed while the form is open. */
  function confirmLive(items: readonly CadClaimable[]): Promise<boolean> {
    return ask('claimedMeanwhile', unacknowledgedCad(items))
  }

  /**
   * Reads the items fresh before a save and asks when one turned CAD since
   * the form opened. A failed read does not block the save, since the
   * server enforces the PDM-owned fields either way.
   */
  async function confirmSave(items: readonly CadClaimable[], read: CadClaimRead): Promise<boolean> {
    let fresh: CadClaimable[]
    try {
      const pages = await Promise.all(items.map((item) => read({ id: item.id, limit: 1 })))
      fresh = pages.flatMap((page) => page.items.slice(0, 1))
    } catch {
      return true
    }
    return ask('claimedMeanwhile', unacknowledgedCad(fresh))
  }

  /**
   * Guards an edit panel over a table selection. An item that joins the
   * selection while the panel edits, or the whole selection when the panel
   * switches to editing, is asked about when PDM claimed it; an item a live
   * update shows claimed since is asked about as claimed meanwhile. Declined
   * items leave the selection.
   */
  function guardSelection<T extends CadClaimable>(selection: CadClaimSelection<T>): void {
    watch(
      [() => selection.selectedItems, () => selection.editMode],
      ([items, editing], [previousItems, wasEditing]) => {
        if (!editing) {
          reset()
          return
        }
        const before = new Map<number, string>(
          wasEditing ? (previousItems ?? []).map((item) => [item.id, item.data_source]) : [],
        )
        const turned = items.filter((item) => before.get(item.id) === 'WEB')
        const joined = items.filter((item) => !before.has(item.id))
        const candidates = [...turned, ...joined]
        const asked = new Set(unacknowledgedCad(candidates))
        if (asked.size === 0) return
        const meanwhile = unacknowledgedCad(turned).length > 0
        const question = meanwhile ? confirmLive(candidates) : confirmOpen(candidates)
        void question.then((proceed) => {
          if (proceed) return
          selection.setSelectedItems(selection.selectedItems.filter((item) => !asked.has(item.id)))
        })
      },
      { immediate: true },
    )
  }

  /** Forgets what the user agreed to, for a form opened afresh. */
  function reset(): void {
    acknowledged.clear()
    settle(false)
    dialog.visible = false
  }

  return {
    dialog,
    confirm,
    onVisibleChange,
    confirmOpen,
    confirmLive,
    confirmSave,
    guardSelection,
    reset,
  }
}
