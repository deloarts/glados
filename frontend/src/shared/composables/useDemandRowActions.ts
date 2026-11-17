import { computed, ref, type Ref } from 'vue'

import { hasAction, type LifecycleAction } from '@/core/utils/lifecycleActions'
import type { Translate } from '@/core/i18n'

import type {
  DataTableRowClickEvent,
  DataTableRowContextMenuEvent,
  DataTableRowSelectEvent,
} from 'openvue/datatable'

/**
 * A demand row: its status and the lifecycle actions the backend offers on
 * it.
 */
export interface DemandRow<TStatus extends string> {
  id: number
  status: TStatus
  actions?: readonly string[] | null
}

/**
 * Store operations and callbacks `useDemandRowActions` needs, supplied by the
 * caller so this file never imports a Pinia store directly. `TStatus` is the
 * demand's own status union (e.g. `BoughtItemDemandStatus`), and `canceledStatus` is
 * the literal value of that union representing "canceled".
 */
export interface DemandRowActionsDeps<TStatus extends string, TDemand extends DemandRow<TStatus>> {
  /** Reads the current shared selection array. */
  getSelection: () => TDemand[]
  /** Replaces the current shared selection array. */
  setSelection: (demands: TDemand[]) => void
  /**
   * True while a Manage-* panel owns the selection, so a plain row
   * interaction only toggles the bulk checkbox instead of opening detail.
   */
  hasPanelOpen: () => boolean
  /** Opens the demand detail dialog for a single row. */
  openDetail: (demand: TDemand) => void
  /** Makes a click/Enter pair on the same row run its open callback once. */
  guardRowOpen: (id: number, open: () => void) => void
  /** Re-fetches the current page after a status or bucket mutation. */
  fetchItems: () => void
  /** Applies a status change to one demand. */
  updateStatus: (id: number, status: TStatus) => Promise<unknown>
  /** Assigns, or with `null` clears, a bucket for one demand. */
  setBucket: (id: number, bucketId: number | null) => Promise<unknown>
  /** The status value representing "canceled". */
  canceledStatus: TStatus
}

/**
 * The row-interaction and bulk-action plumbing repeated across the
 * bought/made/source-item demand tables: modifier-click selection, the
 * plain-click open-detail gesture, right-click context-menu targeting,
 * multi-target status changes with a confirm-then-cancel flow, and bucket
 * assignment. Every side effect that needs a toast or a translated label
 * stays with the caller, this only reports success/failure counts back.
 */
export function useDemandRowActions<TStatus extends string, TDemand extends DemandRow<TStatus>>(
  deps: DemandRowActionsDeps<TStatus, TDemand>,
) {
  // Snapshot of the selection just before a plain click, taken because
  // OpenVue emits `row-click` before it touches the selection: onRowSelect
  // can hand this back to undo the single-row selection OpenVue just set,
  // while a panel still owns the working set.
  let selectionBeforeClick: TDemand[] = []

  function isModifiedClick(event: Event): boolean {
    const e = event as MouseEvent
    return e.ctrlKey || e.metaKey || e.shiftKey
  }

  // A modified click picks the row even on a link or button, which OpenVue
  // would otherwise ignore. Captured on the table root and replayed on the
  // row element, so OpenVue's own selection logic runs.
  function onTableClickCapture(event: MouseEvent): void {
    if (!isModifiedClick(event)) return
    const target = event.target as HTMLElement | null
    const row = target?.closest<HTMLTableRowElement>('tbody tr[data-p-selectable-row="true"]')
    if (!row || target === row) return
    event.preventDefault()
    event.stopPropagation()
    row.dispatchEvent(
      new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        ctrlKey: event.ctrlKey,
        metaKey: event.metaKey,
        shiftKey: event.shiftKey,
      }),
    )
  }

  function onRowClick(event: DataTableRowClickEvent<TDemand>): void {
    selectionBeforeClick = deps.getSelection()
    if (deps.hasPanelOpen() || isModifiedClick(event.originalEvent)) return
    const demand = event.data
    deps.guardRowOpen(demand.id, () => deps.openDetail(demand))
  }

  function onRowSelect(event: DataTableRowSelectEvent<TDemand>): void {
    // Checkbox toggles and the header select-all both emit `row-select`
    // too, with `type: 'checkbox'`, only a plain row interaction opens
    // detail.
    if (event.type !== 'row') return
    if (isModifiedClick(event.originalEvent)) return
    if (deps.hasPanelOpen()) {
      deps.setSelection(selectionBeforeClick)
      return
    }
    const demand = event.data
    deps.setSelection([])
    deps.guardRowOpen(demand.id, () => deps.openDetail(demand))
  }

  const cm = ref()
  const contextMenuItem = ref(null) as Ref<TDemand | null>

  function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
    cm.value?.show(event.originalEvent)
  }

  // The right-clicked row's own targets: the current selection when the row
  // is part of it, so a right-click anywhere inside an existing selection
  // acts on the whole batch, otherwise just the row itself.
  const contextMenuTargets = computed<TDemand[]>(() => {
    const row = contextMenuItem.value
    if (!row) return []
    const selected = deps.getSelection()
    return selected.some((d) => d.id === row.id) ? selected : [row]
  })

  // The action a manual status stands for: canceling, or marking the demand
  // fulfilled, the only two statuses a user sets by hand.
  function actionFor(status: TStatus): LifecycleAction {
    return status === deps.canceledStatus ? 'cancel' : 'fulfil'
  }

  // Multi-target status change, applied only to targets whose actions offer
  // it, so a fulfilled or canceled demand is left alone. Reports a failure
  // count through `onFailures` instead of showing a toast itself, so callers
  // keep their own wording.
  async function setStatusForTargets(
    targets: TDemand[],
    status: TStatus,
    onFailures?: (failures: number, applicable: number) => void,
  ): Promise<void> {
    const applicable = targets.filter((d) => hasAction(d, actionFor(status)))
    if (applicable.length === 0) return
    const results = await Promise.allSettled(applicable.map((d) => deps.updateStatus(d.id, status)))
    const failures = results.filter((r) => r.status === 'rejected').length
    if (failures > 0) onFailures?.(failures, applicable.length)
    deps.fetchItems()
  }

  // Bulk cancel is the one multi-target status change that gets a confirm
  // first, it is irreversible and shows no per-demand impact, so the dialog
  // at least states the count before the updates fire.
  const bulkCancelTargets = ref([]) as Ref<TDemand[]>
  const showBulkCancel = ref(false)

  function requestBulkCancel(targets: TDemand[]): void {
    bulkCancelTargets.value = targets.filter((d) => hasAction(d, 'cancel'))
    if (bulkCancelTargets.value.length === 0) return
    showBulkCancel.value = true
  }

  function confirmBulkCancel(onFailures?: (failures: number, applicable: number) => void): void {
    showBulkCancel.value = false
    void setStatusForTargets(bulkCancelTargets.value, deps.canceledStatus, onFailures)
  }

  // Marking demands fulfilled is irreversible too, and for the families
  // allocated on order lines it releases what those lines have not
  // delivered yet, so a table of such a family asks first. The caller runs
  // the change once the user confirms, as one or several updates.
  const fulfilTargets = ref([]) as Ref<TDemand[]>
  const showFulfil = ref(false)

  function requestFulfil(targets: TDemand[]): void {
    fulfilTargets.value = targets.filter((d) => hasAction(d, 'fulfil'))
    if (fulfilTargets.value.length === 0) return
    showFulfil.value = true
  }

  async function assignBucket(targets: TDemand[], bucketId: number | null): Promise<void> {
    await Promise.allSettled(targets.map((d) => deps.setBucket(d.id, bucketId)))
    deps.fetchItems()
  }

  return {
    isModifiedClick,
    onTableClickCapture,
    onRowClick,
    onRowSelect,
    cm,
    contextMenuItem,
    onRowContextMenu,
    contextMenuTargets,
    setStatusForTargets,
    bulkCancelTargets,
    showBulkCancel,
    requestBulkCancel,
    confirmBulkCancel,
    fulfilTargets,
    showFulfil,
    requestFulfil,
    assignBucket,
  }
}

/**
 * The `onFailures` callback the demand tables pass to `setStatusForTargets`
 * and `confirmBulkCancel`: one error toast saying how many of the targeted
 * demands kept their status. `keyPrefix` is the feature's demands namespace,
 * such as `boughtItems.demands`, whose `contextMenu` holds the wording.
 */
export function bulkStatusFailureToast(
  toast: { error: (summary: string, detail?: string) => void },
  t: Translate,
  keyPrefix: string,
): (failures: number, applicable: number) => void {
  return (failures, applicable) => {
    toast.error(
      t(`${keyPrefix}.contextMenu.setStatus`),
      t(`${keyPrefix}.contextMenu.bulkActionPartialError`, { count: failures, total: applicable }),
    )
  }
}
