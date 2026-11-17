import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useBoughtItemsCatalogueEditStore } from '../boughtItemsCatalogueEditStore'
import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

// A thin createCatalogueEditStore<BoughtItemResponse> instantiation (see
// shared/stores/createCatalogueEditStore.spec.ts for the generic behaviour).
// These tests pin down that the real store works with the actual
// BoughtItemResponse item shape rather than a synthetic test type.
function makeItem(overrides: Partial<BoughtItemResponse> = {}): BoughtItemResponse {
  return { id: 1, article_name: 'Widget', ...overrides } as unknown as BoughtItemResponse
}

describe('useBoughtItemsCatalogueEditStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with edit mode off and no selection', () => {
    const store = useBoughtItemsCatalogueEditStore()
    expect(store.editMode).toBe(false)
    expect(store.selectedItems).toEqual([])
  })

  it('toggleEditMode flips edit mode on and off', () => {
    const store = useBoughtItemsCatalogueEditStore()
    store.toggleEditMode()
    expect(store.editMode).toBe(true)

    store.toggleEditMode()
    expect(store.editMode).toBe(false)
  })

  it('setSelectedItems replaces the selection with bought item rows', () => {
    const store = useBoughtItemsCatalogueEditStore()
    const items = [makeItem({ id: 1 }), makeItem({ id: 2 })]

    store.setSelectedItems(items)

    expect(store.selectedItems).toEqual(items)
  })

  it('turning edit mode off clears the current selection', () => {
    const store = useBoughtItemsCatalogueEditStore()
    store.toggleEditMode()
    store.setSelectedItems([makeItem({ id: 1 }), makeItem({ id: 2 })])
    expect(store.selectedItems).toHaveLength(2)

    store.toggleEditMode()

    expect(store.editMode).toBe(false)
    expect(store.selectedItems).toEqual([])
  })

  it('setSelectedItems does not itself toggle edit mode', () => {
    const store = useBoughtItemsCatalogueEditStore()
    store.setSelectedItems([makeItem({ id: 1 })])
    expect(store.editMode).toBe(false)
  })
})
