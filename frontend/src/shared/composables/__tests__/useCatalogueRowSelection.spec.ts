import { describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'

import { useCatalogueRowSelection } from '../useCatalogueRowSelection'

import type { DataTableRowClickEvent, DataTableRowSelectEvent } from 'openvue/datatable'

interface Item {
  id: number
}

const first: Item = { id: 1 }
const second: Item = { id: 2 }

function setup(options: { canSelect?: boolean; editMode?: boolean; selected?: Item[] } = {}) {
  const editStore = reactive({ editMode: options.editMode ?? false, selectedItems: options.selected ?? [] })
  const openDetail = vi.fn<(item: Item) => void>()
  const selection = useCatalogueRowSelection<Item>({
    editStore,
    canSelect: () => options.canSelect ?? true,
    openDetail,
  })
  return { editStore, openDetail, ...selection }
}

function click(data: Item, init: MouseEventInit = {}): DataTableRowClickEvent {
  return { originalEvent: new MouseEvent('click', init), data, index: 0 }
}

function select(data: Item, type: string, init: MouseEventInit = {}): DataTableRowSelectEvent {
  return { originalEvent: new MouseEvent('click', init), data, index: 0, type }
}

describe('useCatalogueRowSelection', () => {
  it('keeps the old single selection for a user who may not bulk edit', () => {
    const { isSelectionColumnVisible, tableSelectionProps } = setup({ canSelect: false })

    expect(isSelectionColumnVisible.value).toBe(false)
    expect(tableSelectionProps.value).toEqual({ selectionMode: 'single', metaKeySelection: false, selection: null })
  })

  it('binds the checked rows in multiple mode for a user who may bulk edit', () => {
    const { isSelectionColumnVisible, tableSelectionProps } = setup({ selected: [first] })

    expect(isSelectionColumnVisible.value).toBe(true)
    expect(tableSelectionProps.value).toEqual({ selectionMode: 'multiple', metaKeySelection: true, selection: [first] })
  })

  it('opens the row on a plain click and keeps the checked rows', () => {
    const { editStore, openDetail, onRowClick, onSelectionUpdate, onRowSelect } = setup({ selected: [first] })

    // OpenVue's order for one plain click: row-click, the replaced selection, row-select.
    onRowClick(click(second))
    onSelectionUpdate([second])
    onRowSelect(select(second, 'row'))

    expect(openDetail).toHaveBeenCalledExactlyOnceWith(second)
    expect(editStore.selectedItems).toEqual([first])
  })

  it('adds a row on ctrl-click without opening it', () => {
    const { editStore, openDetail, onRowClick, onSelectionUpdate, onRowSelect } = setup({ selected: [first] })

    onRowClick(click(second, { ctrlKey: true }))
    onSelectionUpdate([first, second])
    onRowSelect(select(second, 'row', { ctrlKey: true }))

    expect(openDetail).not.toHaveBeenCalled()
    expect(editStore.selectedItems).toEqual([first, second])
  })

  it('records a checkbox toggle without opening the row', () => {
    const { editStore, openDetail, onSelectionUpdate, onRowSelect } = setup()

    onSelectionUpdate([second])
    onRowSelect(select(second, 'checkbox'))

    expect(openDetail).not.toHaveBeenCalled()
    expect(editStore.selectedItems).toEqual([second])
  })

  it('opens nothing while the edit panel is open', () => {
    const { openDetail, onRowClick, onRowSelect } = setup({ editMode: true })

    onRowClick(click(first))
    onRowSelect(select(first, 'row'))

    expect(openDetail).not.toHaveBeenCalled()
  })
})
