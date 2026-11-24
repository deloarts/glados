import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useExternalWorkStore } from '../externalWorkStore'

describe('externalWorkStore query', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('sends only the filters that are set', () => {
    expect(useExternalWorkStore().query()).toEqual({ skip: 0, limit: 25 })
  })

  it('sends the lot column filters as lists and the back-by range as days', () => {
    const store = useExternalWorkStore()
    store.lotIds = [4]
    store.projectIds = [1, 2]
    store.productIds = [7]
    store.backByFrom = new Date(2026, 11, 1)
    store.backByTo = new Date(2026, 11, 15)

    expect(store.query()).toEqual({
      skip: 0,
      limit: 25,
      lot_ids: [4],
      project_ids: [1, 2],
      product_ids: [7],
      back_by_from: '2026-12-01',
      back_by_to: '2026-12-15',
    })
    expect(store.hasActiveFilters).toBe(true)
  })
})
