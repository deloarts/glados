import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useMadeItemsCatalogueFiltersStore } from '../madeItemsCatalogueFiltersStore'

// Built on createFiltersStore. hasActiveFilters here is
// structural (OpenVue DataTableFilterMeta + date-range tuples), not a flat
// per-field diff, so this is the parity spec for the custom `isActive`
// passed to the factory (see boughtItemsCatalogueFiltersStore.spec.ts for
// the same shape of problem).
describe('useMadeItemsCatalogueFiltersStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with empty filters, no search, and no active filters', () => {
    const store = useMadeItemsCatalogueFiltersStore()
    expect(store.search).toBe('')
    expect(store.hasActiveFilters).toBe(false)
  })

  it('counts a column filter value as an active filter', () => {
    const store = useMadeItemsCatalogueFiltersStore()
    const meta = store.filters.article_name as { value: unknown; matchMode: string }
    meta.value = 'widget'
    expect(store.hasActiveFilters).toBe(true)
  })

  it('counts the free-text search as an active filter', () => {
    const store = useMadeItemsCatalogueFiltersStore()
    store.search = 'widget'
    expect(store.hasActiveFilters).toBe(true)
  })

  it('counts a date-range filter as an active filter', () => {
    const store = useMadeItemsCatalogueFiltersStore()
    const [dateRangeField] = Object.keys(store.dateRangeFilters)
    if (!dateRangeField) throw new Error('expected at least one date-range column')
    store.dateRangeFilters[dateRangeField] = [new Date('2026-01-01'), null]
    expect(store.hasActiveFilters).toBe(true)
  })

  it('counts showArchived as an active filter, and clearAll resets it to false', () => {
    const store = useMadeItemsCatalogueFiltersStore()
    expect(store.showArchived).toBe(false)

    store.showArchived = true
    expect(store.hasActiveFilters).toBe(true)

    store.clearAll()
    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
  })

  it('clearAll resets filters, dateRangeFilters, search and showArchived, and bumps clearTrigger', () => {
    const store = useMadeItemsCatalogueFiltersStore()
    const meta = store.filters.article_name as { value: unknown; matchMode: string }
    meta.value = 'widget'
    store.search = 'widget'
    store.showArchived = true
    const [dateRangeField] = Object.keys(store.dateRangeFilters)
    if (!dateRangeField) throw new Error('expected at least one date-range column')
    store.dateRangeFilters[dateRangeField] = [new Date('2026-01-01'), null]
    const before = store.clearTrigger

    store.clearAll()

    expect((store.filters.article_name as { value: unknown }).value).toBeNull()
    expect(store.search).toBe('')
    expect(store.showArchived).toBe(false)
    expect(store.dateRangeFilters[dateRangeField]).toEqual([null, null])
    expect(store.hasActiveFilters).toBe(false)
    expect(store.clearTrigger).toBe(before + 1)
  })

  it('clearAll rebuilds a fresh filters object rather than reusing the mutated one', () => {
    const store = useMadeItemsCatalogueFiltersStore()
    const originalFilters = store.filters
    store.clearAll()
    expect(store.filters).not.toBe(originalFilters)
  })
})
