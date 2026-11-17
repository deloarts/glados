import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useSourceItemsCatalogueEditStore } from '../sourceItemsCatalogueEditStore'
import type { SourceItemResponse } from '../../types/sourceItemsResponse'

// A thin createCatalogueEditStore<SourceItemResponse> instantiation (see
// shared/stores/createCatalogueEditStore.spec.ts for the generic behaviour).
// These tests pin down that the real store works with the actual
// SourceItemResponse item shape rather than a synthetic test type.
function makeItem(overrides: Partial<SourceItemResponse> = {}): SourceItemResponse {
  return {
    id: 1,
    dimension: 'Ø10x100',
    material: 'Steel',
    ...overrides,
  } as unknown as SourceItemResponse
}

describe('useSourceItemsCatalogueEditStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with edit mode off and no selection', () => {
    const store = useSourceItemsCatalogueEditStore()
    expect(store.editMode).toBe(false)
    expect(store.selectedItems).toEqual([])
  })

  it('toggleEditMode flips edit mode on and off', () => {
    const store = useSourceItemsCatalogueEditStore()
    store.toggleEditMode()
    expect(store.editMode).toBe(true)

    store.toggleEditMode()
    expect(store.editMode).toBe(false)
  })

  it('setSelectedItems replaces the selection with source item rows', () => {
    const store = useSourceItemsCatalogueEditStore()
    const items = [makeItem({ id: 1 }), makeItem({ id: 2 })]

    store.setSelectedItems(items)

    expect(store.selectedItems).toEqual(items)
  })

  it('turning edit mode off clears the current selection', () => {
    const store = useSourceItemsCatalogueEditStore()
    store.toggleEditMode()
    store.setSelectedItems([makeItem({ id: 1 }), makeItem({ id: 2 })])
    expect(store.selectedItems).toHaveLength(2)

    store.toggleEditMode()

    expect(store.editMode).toBe(false)
    expect(store.selectedItems).toEqual([])
  })

  it('setSelectedItems does not itself toggle edit mode', () => {
    const store = useSourceItemsCatalogueEditStore()
    store.setSelectedItems([makeItem({ id: 1 })])
    expect(store.editMode).toBe(false)
  })
})
