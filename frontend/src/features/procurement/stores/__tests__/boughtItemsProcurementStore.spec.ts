import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useBoughtItemsProcurementStore } from '../boughtItemsProcurementStore'
import type { BoughtItemDemandResponse } from '@/features/bought-items'

describe('useBoughtItemsProcurementStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with no selected demands and a refreshTrigger of 0', () => {
    const store = useBoughtItemsProcurementStore()
    expect(store.selectedDemands).toEqual([])
    expect(store.refreshTrigger).toBe(0)
  })

  it('clearSelection empties selectedDemands', () => {
    const store = useBoughtItemsProcurementStore()
    store.selectedDemands = [{ id: 1 } as unknown as BoughtItemDemandResponse]

    store.clearSelection()

    expect(store.selectedDemands).toEqual([])
  })

  it('triggerRefresh increments refreshTrigger each call', () => {
    const store = useBoughtItemsProcurementStore()
    store.triggerRefresh()
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(2)
  })
})
