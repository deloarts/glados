import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { createCatalogueEditStore } from '../createCatalogueEditStore'

interface TestItem {
  id: number
}

describe('createCatalogueEditStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with edit mode off and no selection', () => {
    const store = createCatalogueEditStore<TestItem>('testEdit1')()
    expect(store.editMode).toBe(false)
    expect(store.selectedItems).toEqual([])
  })

  it('toggleEditMode flips edit mode on', () => {
    const store = createCatalogueEditStore<TestItem>('testEdit2')()
    store.toggleEditMode()
    expect(store.editMode).toBe(true)
  })

  it('turning edit mode off clears the current selection', () => {
    const store = createCatalogueEditStore<TestItem>('testEdit3')()
    store.toggleEditMode()
    store.setSelectedItems([{ id: 1 }, { id: 2 }])
    expect(store.selectedItems).toHaveLength(2)

    store.toggleEditMode()
    expect(store.editMode).toBe(false)
    expect(store.selectedItems).toEqual([])
  })

  it('setSelectedItems replaces the selection', () => {
    const store = createCatalogueEditStore<TestItem>('testEdit4')()
    store.setSelectedItems([{ id: 1 }])
    expect(store.selectedItems).toEqual([{ id: 1 }])
  })
})
