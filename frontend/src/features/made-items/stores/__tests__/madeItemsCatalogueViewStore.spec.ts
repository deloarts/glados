import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useMadeItemsCatalogueViewStore, useMadeItemsShowAllRevisionsStore } from '../madeItemsCatalogueViewStore'

// createCatalogueViewStore is fully generic (see createCatalogueViewStore.spec.ts
// for its behaviour). This pins down the made-items wiring: the
// 'article_groups' groupBy and MadeItemSortBy fields actually work through
// the real store, plus the sibling useMadeItemsShowAllRevisionsStore that
// lives next to it (see the comment in madeItemsCatalogueViewStore.ts for
// why it isn't folded into the generic factory).
describe('useMadeItemsCatalogueViewStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with no grouping, no sort, and actions hidden', () => {
    const store = useMadeItemsCatalogueViewStore()
    expect(store.groupBy).toBeNull()
    expect(store.showActions).toBe(false)
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })

  it('setGroupBy groups by article_groups, calling it again toggles it back off', () => {
    const store = useMadeItemsCatalogueViewStore()
    store.setGroupBy('article_groups')
    expect(store.groupBy).toBe('article_groups')

    store.setGroupBy('article_groups')
    expect(store.groupBy).toBeNull()
  })

  it('clearGroupBy resets to null', () => {
    const store = useMadeItemsCatalogueViewStore()
    store.setGroupBy('article_groups')
    store.clearGroupBy()
    expect(store.groupBy).toBeNull()
  })

  it('toggleShowActions flips the actions column', () => {
    const store = useMadeItemsCatalogueViewStore()
    store.toggleShowActions()
    expect(store.showActions).toBe(true)
    store.toggleShowActions()
    expect(store.showActions).toBe(false)
  })

  it('setSort sets a made-item sort field and direction; clearSort resets to the default', () => {
    const store = useMadeItemsCatalogueViewStore()
    store.setSort('article_name', 'desc')
    expect(store.sortBy).toBe('article_name')
    expect(store.sortDir).toBe('desc')

    store.clearSort()
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })
})

describe('useMadeItemsShowAllRevisionsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('defaults showAllRevisions to false', () => {
    const store = useMadeItemsShowAllRevisionsStore()
    expect(store.showAllRevisions).toBe(false)
  })

  it('toggleShowAllRevisions flips the flag each call', () => {
    const store = useMadeItemsShowAllRevisionsStore()
    store.toggleShowAllRevisions()
    expect(store.showAllRevisions).toBe(true)
    store.toggleShowAllRevisions()
    expect(store.showAllRevisions).toBe(false)
  })
})
