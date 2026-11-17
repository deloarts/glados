import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { FilterMatchMode } from '@openvue/core/api'
import type { DataTableFilterMeta } from 'openvue/datatable'

import { createCatalogueFiltersStore } from '../createCatalogueFiltersStore'
import type { DateRangeFilters } from '../createCatalogueColumnsStore'

function emptyFilters(): DataTableFilterMeta {
  return { name: { value: null, matchMode: FilterMatchMode.CONTAINS } }
}

function emptyDateRanges(): DateRangeFilters {
  return { created: [null, null] }
}

describe('createCatalogueFiltersStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function makeStore(id: string) {
    return createCatalogueFiltersStore(id, emptyFilters, emptyDateRanges)()
  }

  it('starts empty and inactive', () => {
    const store = makeStore('catalogueFiltersEmpty')
    expect(store.filters).toEqual(emptyFilters())
    expect(store.dateRangeFilters).toEqual(emptyDateRanges())
    expect(store.search).toBe('')
    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
  })

  it('is active for a column filter, search, archived toggle or date range', () => {
    const store = makeStore('catalogueFiltersActive')

    ;(store.filters.name as { value: unknown }).value = 'bolt'
    expect(store.hasActiveFilters).toBe(true)
    store.clearAll()
    expect(store.hasActiveFilters).toBe(false)

    store.search = 'x'
    expect(store.hasActiveFilters).toBe(true)
    store.clearAll()

    store.showArchived = true
    expect(store.hasActiveFilters).toBe(true)
    store.clearAll()

    store.dateRangeFilters = { created: [new Date(2026, 0, 1), null] }
    expect(store.hasActiveFilters).toBe(true)
  })

  it('restores fresh filter objects on clearAll', () => {
    const store = makeStore('catalogueFiltersClear')
    const before = store.filters
    ;(store.filters.name as { value: unknown }).value = 'bolt'
    store.clearAll()
    expect(store.filters).not.toBe(before)
    expect(store.filters).toEqual(emptyFilters())
  })
})
