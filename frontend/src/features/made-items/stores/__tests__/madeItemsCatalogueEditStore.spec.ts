import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useMadeItemsCatalogueEditStore } from '../madeItemsCatalogueEditStore'
import type { MadeItemResponse } from '../../types/madeItemsResponse'

function makeItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return { id: 1, article_name: 'Widget', ...overrides } as unknown as MadeItemResponse
}

// createCatalogueEditStore is fully generic (see
// createCatalogueEditStore.spec.ts for its behaviour, exercised there with a
// throwaway TestItem type). madeItemsCatalogueEditStore adds nothing beyond
// the store id and the MadeItemResponse type parameter, so this pins down
// only that the wiring itself works with real made-item rows.
describe('useMadeItemsCatalogueEditStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with edit mode off and no selection', () => {
    const store = useMadeItemsCatalogueEditStore()
    expect(store.editMode).toBe(false)
    expect(store.selectedItems).toEqual([])
  })

  it('toggleEditMode turns edit mode on', () => {
    const store = useMadeItemsCatalogueEditStore()
    store.toggleEditMode()
    expect(store.editMode).toBe(true)
  })

  it('setSelectedItems tracks the selected made items', () => {
    const store = useMadeItemsCatalogueEditStore()
    store.toggleEditMode()
    const items = [makeItem({ id: 1 }), makeItem({ id: 2 })]

    store.setSelectedItems(items)

    expect(store.selectedItems).toEqual(items)
  })

  it('turning edit mode off clears the current selection', () => {
    const store = useMadeItemsCatalogueEditStore()
    store.toggleEditMode()
    store.setSelectedItems([makeItem()])

    store.toggleEditMode()

    expect(store.editMode).toBe(false)
    expect(store.selectedItems).toEqual([])
  })

  it('turning edit mode back on starts with an empty selection', () => {
    const store = useMadeItemsCatalogueEditStore()
    store.toggleEditMode()
    store.setSelectedItems([makeItem()])
    store.toggleEditMode()

    store.toggleEditMode()

    expect(store.editMode).toBe(true)
    expect(store.selectedItems).toEqual([])
  })
})
