import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useBoughtItemsCatalogueViewStore } from '../boughtItemsCatalogueViewStore'

// A thin createCatalogueViewStore<'manufacturer_name' | 'article_groups',
// BoughtItemSortBy> instantiation (see
// shared/stores/createCatalogueViewStore.spec.ts for the generic
// group/sort/actions-column behaviour). These tests pin down that the real
// store is wired with bought items' own grouping and sort fields.
describe('useBoughtItemsCatalogueViewStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with no grouping, no sort, and actions hidden', () => {
    const store = useBoughtItemsCatalogueViewStore()
    expect(store.groupBy).toBeNull()
    expect(store.showActions).toBe(false)
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })

  it('setGroupBy sets article_groups, calling it again toggles it off', () => {
    const store = useBoughtItemsCatalogueViewStore()
    store.setGroupBy('article_groups')
    expect(store.groupBy).toBe('article_groups')

    store.setGroupBy('article_groups')
    expect(store.groupBy).toBeNull()
  })

  it('setGroupBy with a different field switches groups directly', () => {
    const store = useBoughtItemsCatalogueViewStore()
    store.setGroupBy('manufacturer_name')
    store.setGroupBy('article_groups')
    expect(store.groupBy).toBe('article_groups')
  })

  it('clearGroupBy resets to null', () => {
    const store = useBoughtItemsCatalogueViewStore()
    store.setGroupBy('manufacturer_name')
    store.clearGroupBy()
    expect(store.groupBy).toBeNull()
  })

  it('toggleShowActions flips the actions column', () => {
    const store = useBoughtItemsCatalogueViewStore()
    store.toggleShowActions()
    expect(store.showActions).toBe(true)
    store.toggleShowActions()
    expect(store.showActions).toBe(false)
  })

  it('setSort accepts a bought-item sort field and direction; clearSort resets to the default', () => {
    const store = useBoughtItemsCatalogueViewStore()
    store.setSort('article_name', 'desc')
    expect(store.sortBy).toBe('article_name')
    expect(store.sortDir).toBe('desc')

    store.clearSort()
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })
})
