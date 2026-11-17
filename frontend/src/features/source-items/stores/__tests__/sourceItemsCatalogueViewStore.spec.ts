import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useSourceItemsCatalogueViewStore } from '../sourceItemsCatalogueViewStore'

// A thin createCatalogueViewStore<'manufacturer_name' | 'status',
// SourceItemSortBy> instantiation (see
// shared/stores/createCatalogueViewStore.spec.ts for the generic
// group/sort/actions-column behaviour). These tests pin down that the real
// store is wired with source items' own grouping and sort fields.
describe('useSourceItemsCatalogueViewStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with no grouping, no sort, and actions hidden', () => {
    const store = useSourceItemsCatalogueViewStore()
    expect(store.groupBy).toBeNull()
    expect(store.showActions).toBe(false)
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })

  it('setGroupBy sets manufacturer_name, calling it again toggles it off', () => {
    const store = useSourceItemsCatalogueViewStore()
    store.setGroupBy('manufacturer_name')
    expect(store.groupBy).toBe('manufacturer_name')

    store.setGroupBy('manufacturer_name')
    expect(store.groupBy).toBeNull()
  })

  it('setGroupBy with a different field switches groups directly', () => {
    const store = useSourceItemsCatalogueViewStore()
    store.setGroupBy('manufacturer_name')
    store.setGroupBy('status')
    expect(store.groupBy).toBe('status')
  })

  it('clearGroupBy resets to null', () => {
    const store = useSourceItemsCatalogueViewStore()
    store.setGroupBy('status')
    store.clearGroupBy()
    expect(store.groupBy).toBeNull()
  })

  it('toggleShowActions flips the actions column', () => {
    const store = useSourceItemsCatalogueViewStore()
    store.toggleShowActions()
    expect(store.showActions).toBe(true)
    store.toggleShowActions()
    expect(store.showActions).toBe(false)
  })

  it('setSort accepts a source-item sort field and direction; clearSort resets to the default', () => {
    const store = useSourceItemsCatalogueViewStore()
    store.setSort('created', 'desc')
    expect(store.sortBy).toBe('created')
    expect(store.sortDir).toBe('desc')

    store.clearSort()
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })
})
