import { computed } from 'vue'

import { useRowOpenGuard } from '@/core/composables/useRowOpenGuard'

import type { DataTableRowClickEvent, DataTableRowSelectEvent } from 'openvue/datatable'

/** The part of a catalogue edit store the row selection reads and writes. */
interface CatalogueSelectionStore<TItem> {
  editMode: boolean
  selectedItems: TItem[]
}

interface CatalogueRowSelectionOptions<TItem> {
  editStore: CatalogueSelectionStore<TItem>
  /** Whether the user may bulk edit, which keeps the checkboxes in view. */
  canSelect: () => boolean
  openDetail: (item: TItem) => void
}

function isModifiedClick(event: Event): boolean {
  const e = event as MouseEvent
  return e.ctrlKey || e.metaKey || e.shiftKey
}

/**
 * Row selection and row opening for a catalogue table. A user who may bulk
 * edit always sees the checkbox column with its select all box, and the
 * checked rows are what the edit panel works on. A plain click or Enter
 * opens the row and leaves the checked rows alone, while ctrl-click and
 * shift-click add rows like the checkboxes do. In edit mode nothing opens,
 * so the panel is never left behind by accident.
 *
 * A user who may not bulk edit gets single selection with the selection
 * left unbound, which keeps every row reachable by keyboard (see the OpenVue
 * pitfalls in docs/reference/frontend-conventions.md). With rows checked,
 * OpenVue's keyboard row access narrows, the same trade-off the demand
 * tables accept.
 */
export function useCatalogueRowSelection<TItem extends { id: number }>(
  options: CatalogueRowSelectionOptions<TItem>,
) {
  const { editStore, canSelect, openDetail } = options
  const { guard: guardRowOpen } = useRowOpenGuard<number>()

  const isSelectionColumnVisible = computed(() => editStore.editMode || canSelect())

  const tableSelectionProps = computed(() =>
    isSelectionColumnVisible.value
      ? { selectionMode: 'multiple' as const, metaKeySelection: true, selection: editStore.selectedItems }
      : { selectionMode: 'single' as const, metaKeySelection: false, selection: null },
  )

  // OpenVue emits `row-click` first and then, in the same call, replaces the
  // selection with the clicked row. A plain click is an open gesture, so that
  // replacement is dropped and the checked rows survive it.
  let plainClickInProgress = false

  function onRowClick(event: DataTableRowClickEvent): void {
    if (isModifiedClick(event.originalEvent)) return
    plainClickInProgress = true
    queueMicrotask(() => {
      plainClickInProgress = false
    })
    if (editStore.editMode) return
    const item = event.data as TItem
    guardRowOpen(item.id, () => openDetail(item))
  }

  function onSelectionUpdate(value: unknown): void {
    if (!isSelectionColumnVisible.value || plainClickInProgress) return
    editStore.selectedItems = value as TItem[]
  }

  // Checkbox toggles emit `row-select` too, with `type: 'checkbox'`; only a
  // plain row interaction opens the row.
  function onRowSelect(event: DataTableRowSelectEvent): void {
    if (event.type === 'checkbox' || isModifiedClick(event.originalEvent)) return
    if (editStore.editMode) return
    const item = event.data as TItem
    guardRowOpen(item.id, () => openDetail(item))
  }

  return { isSelectionColumnVisible, tableSelectionProps, onRowClick, onRowSelect, onSelectionUpdate }
}
