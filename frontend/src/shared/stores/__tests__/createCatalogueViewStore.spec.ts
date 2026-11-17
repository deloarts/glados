import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { createCatalogueViewStore } from '../createCatalogueViewStore'

type TestGroupBy = 'status' | 'category'
type TestSortBy = 'name' | 'created'

describe('createCatalogueViewStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with no grouping, no sort, actions hidden', () => {
    const store = createCatalogueViewStore<TestGroupBy, TestSortBy>('testView1')()
    expect(store.groupBy).toBeNull()
    expect(store.showActions).toBe(false)
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })

  it('setGroupBy sets the group, calling it again with the same value clears it (toggle)', () => {
    const store = createCatalogueViewStore<TestGroupBy, TestSortBy>('testView2')()
    store.setGroupBy('status')
    expect(store.groupBy).toBe('status')

    store.setGroupBy('status')
    expect(store.groupBy).toBeNull()
  })

  it('setGroupBy with a different value switches groups directly', () => {
    const store = createCatalogueViewStore<TestGroupBy, TestSortBy>('testView3')()
    store.setGroupBy('status')
    store.setGroupBy('category')
    expect(store.groupBy).toBe('category')
  })

  it('clearGroupBy resets to null', () => {
    const store = createCatalogueViewStore<TestGroupBy, TestSortBy>('testView4')()
    store.setGroupBy('status')
    store.clearGroupBy()
    expect(store.groupBy).toBeNull()
  })

  it('toggleShowActions flips the actions column', () => {
    const store = createCatalogueViewStore<TestGroupBy, TestSortBy>('testView5')()
    store.toggleShowActions()
    expect(store.showActions).toBe(true)
    store.toggleShowActions()
    expect(store.showActions).toBe(false)
  })

  it('setSort sets both field and direction; clearSort resets to the no-sort default', () => {
    const store = createCatalogueViewStore<TestGroupBy, TestSortBy>('testView6')()
    store.setSort('created', 'desc')
    expect(store.sortBy).toBe('created')
    expect(store.sortDir).toBe('desc')

    store.clearSort()
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })
})
