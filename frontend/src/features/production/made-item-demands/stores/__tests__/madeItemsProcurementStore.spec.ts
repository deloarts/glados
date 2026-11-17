import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useMadeItemsProcurementStore } from '../madeItemsProcurementStore'
import type { MadeItemDemandResponse } from '@/features/made-items'

describe('useMadeItemsProcurementStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with no selected demands and a refreshTrigger of 0', () => {
    const store = useMadeItemsProcurementStore()
    expect(store.selectedDemands).toEqual([])
    expect(store.refreshTrigger).toBe(0)
  })

  it('clearSelection empties selectedDemands', () => {
    const store = useMadeItemsProcurementStore()
    store.selectedDemands = [{ id: 1 } as unknown as MadeItemDemandResponse]

    store.clearSelection()

    expect(store.selectedDemands).toEqual([])
  })

  it('triggerRefresh increments refreshTrigger each call', () => {
    const store = useMadeItemsProcurementStore()
    store.triggerRefresh()
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(2)
  })
})
