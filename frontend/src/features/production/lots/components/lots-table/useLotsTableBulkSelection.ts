import { computed, type Ref } from 'vue'

import { useProductionLotsEditStore } from '../../stores/productionLotsEditStore'
import { useProductionLotsSourceStore } from '../../stores/productionLotsSourceStore'

import type { DataTableRowClickEvent } from 'openvue/datatable'
import type { FlatPositionRow } from '../../types/lotsTableFlatRow'
import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

interface RowSelectionTarget {
  items: LotSummaryResponse[]
  setItems: (items: LotSummaryResponse[]) => void
}

function isModifiedClick(event: Event): boolean {
  const e = event as MouseEvent
  return e.ctrlKey || e.metaKey || e.shiftKey
}

// Row selection for bulk edit or the Manage Source panel, which are never
// active at the same time. A user who may bulk edit always has the bulk edit
// checkboxes, so outside both modes rows can be checked before the panel
// opens, while a plain click still opens the lot.
export function useLotsTableBulkSelection(
  showManageSource: Ref<boolean>,
  isColumnModeActive: Ref<boolean>,
  flatPositionRows: Ref<FlatPositionRow[]>,
  canSelect: () => boolean = () => false,
) {
  const editStore = useProductionLotsEditStore()
  const sourceStore = useProductionLotsSourceStore()

  const rowSelectionTarget = computed<RowSelectionTarget | null>(() => {
    if (editStore.editMode) {
      return { items: editStore.selectedItems, setItems: editStore.setSelectedItems }
    }
    if (showManageSource.value) {
      return { items: sourceStore.selectedLots, setItems: sourceStore.setSelectedLots }
    }
    if (canSelect()) {
      return { items: editStore.selectedItems, setItems: editStore.setSelectedItems }
    }
    return null
  })

  // Checkboxes next to row opening, outside both modes. The table then runs
  // in multiple mode, where ctrl-click and shift-click add rows too.
  const isIdleSelection = computed(
    () => !editStore.editMode && !showManageSource.value && canSelect(),
  )

  // OpenVue emits `row-click` first and then, in the same call, replaces the
  // selection with the clicked row. A plain click opens the lot instead, so
  // that replacement is dropped and the checked rows survive it.
  let plainClickInProgress = false

  function markRowClick(event: DataTableRowClickEvent): void {
    if (!isIdleSelection.value || isModifiedClick(event.originalEvent)) return
    plainClickInProgress = true
    queueMicrotask(() => {
      plainClickInProgress = false
    })
  }

  const editSelection = computed<unknown[]>(() => {
    const target = rowSelectionTarget.value
    if (!target) return []
    if (!isColumnModeActive.value) return target.items
    const selectedIds = new Set(target.items.map((lot) => lot.id))
    return flatPositionRows.value.filter((row) => selectedIds.has(row.lotId))
  })

  function onSelectionUpdate(value: unknown): void {
    const target = rowSelectionTarget.value
    if (plainClickInProgress) return
    if (!target) {
      // Outside both modes the update comes from selectionMode="single", which
      // only exists for keyboard access, so nothing is recorded.
      return
    }
    const rows = (value ?? []) as unknown[]
    if (!isColumnModeActive.value) {
      target.setItems(rows as LotSummaryResponse[])
      return
    }
    // In Column Mode OpenVue's checkbox only toggles a lot's first row, so the
    // emitted array cannot tell which lots remain. Diffing against the previous
    // selection finds the toggled rows, which apply to the whole lot.
    const previousRows = editSelection.value as FlatPositionRow[]
    const newRows = rows as FlatPositionRow[]
    const previousKeys = new Set(previousRows.map((row) => row.rowKey))
    const newKeys = new Set(newRows.map((row) => row.rowKey))
    const removedRows = previousRows.filter((row) => !newKeys.has(row.rowKey))
    const addedRows = newRows.filter((row) => !previousKeys.has(row.rowKey))

    const byId = new Map<number, LotSummaryResponse>()
    for (const lot of target.items) byId.set(lot.id, lot)
    for (const row of removedRows) byId.delete(row.lotId)
    for (const row of addedRows) byId.set(row.lotId, row.lot)
    target.setItems([...byId.values()])
  }

  return { rowSelectionTarget, isIdleSelection, editSelection, markRowClick, onSelectionUpdate }
}
