import { describe, it, expect, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { useMadeItemsDemandsFiltersStore } from '../madeItemsDemandsFiltersStore'
import { useMadeItemsProcurementStore } from '../madeItemsProcurementStore'
import type { MadeItemDemandResponse } from '@/features/made-items'

describe('useMadeItemsDemandsFiltersStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // bucketIds is an array: the generic default-equality check would compare
  // a freshly-cleared [] against the original default [] by reference and
  // report it permanently active: this is the parity spec for the custom
  // `isActive` passed to the factory (see boughtItemsDemandsFiltersStore.spec.ts
  // for the same shape of problem).
  it('starts with no active filters', () => {
    const store = useMadeItemsDemandsFiltersStore()
    expect(store.bucketIds).toEqual([])
    expect(store.includeUnbucketed).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
  })

  it('counts a non-empty bucketIds as an active filter', () => {
    const store = useMadeItemsDemandsFiltersStore()
    store.bucketIds.push(1)
    expect(store.hasActiveFilters).toBe(true)
  })

  it('counts includeUnbucketed as an active filter', () => {
    const store = useMadeItemsDemandsFiltersStore()
    store.includeUnbucketed = true
    expect(store.hasActiveFilters).toBe(true)
  })

  it('clearAll resets bucketIds/includeUnbucketed and rebuilds a fresh array', () => {
    const store = useMadeItemsDemandsFiltersStore()
    const originalBucketIds = store.bucketIds
    store.bucketIds.push(1, 2)
    store.includeUnbucketed = true

    store.clearAll()

    expect(store.bucketIds).toEqual([])
    expect(store.includeUnbucketed).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
    // A factory default, not a static object shared across resets: pushing
    // onto the pre-reset array must never leak into the post-reset one.
    expect(store.bucketIds).not.toBe(originalBucketIds)
  })

  it('starts with the id, step method and lot filters inactive', () => {
    const store = useMadeItemsDemandsFiltersStore()
    expect(store.idFilter).toBeNull()
    expect(store.stepMethods).toEqual([])
    expect(store.lotIds).toEqual([])
    expect(store.hasActiveFilters).toBe(false)
  })

  it('counts a set idFilter as an active filter', () => {
    const store = useMadeItemsDemandsFiltersStore()
    store.idFilter = 42
    expect(store.hasActiveFilters).toBe(true)
  })

  it('counts a non-empty stepMethods as an active filter, an empty one not', () => {
    const store = useMadeItemsDemandsFiltersStore()
    store.stepMethods = []
    expect(store.hasActiveFilters).toBe(false)
    store.stepMethods.push('fabrication:3')
    expect(store.hasActiveFilters).toBe(true)
  })

  it('counts a non-empty lotIds as an active filter, an empty one not', () => {
    const store = useMadeItemsDemandsFiltersStore()
    store.lotIds = []
    expect(store.hasActiveFilters).toBe(false)
    store.lotIds.push(7)
    expect(store.hasActiveFilters).toBe(true)
  })

  it('clearAll resets idFilter, stepMethods and lotIds and rebuilds fresh arrays', () => {
    const store = useMadeItemsDemandsFiltersStore()
    const originalStepMethods = store.stepMethods
    const originalLotIds = store.lotIds
    store.idFilter = 42
    store.stepMethods.push('fabrication:3', 'inspection:5')
    store.lotIds.push(7, 8)

    store.clearAll()

    expect(store.idFilter).toBeNull()
    expect(store.stepMethods).toEqual([])
    expect(store.lotIds).toEqual([])
    expect(store.hasActiveFilters).toBe(false)
    expect(store.stepMethods).not.toBe(originalStepMethods)
    expect(store.lotIds).not.toBe(originalLotIds)
  })

  function demand(id: number): MadeItemDemandResponse {
    return { id } as unknown as MadeItemDemandResponse
  }

  it('openPanel opens the requested panel, closes the other, and clears the selection by default', () => {
    const store = useMadeItemsDemandsFiltersStore()
    const procurementStore = useMadeItemsProcurementStore()
    procurementStore.selectedDemands = [demand(1)]

    store.openPanel('lots')

    expect(store.showManageLotsPanel).toBe(true)
    expect(store.showManageStockPanel).toBe(false)
    expect(procurementStore.selectedDemands).toEqual([])

    procurementStore.selectedDemands = [demand(1)]
    store.openPanel('stock')

    expect(store.showManageLotsPanel).toBe(false)
    expect(store.showManageStockPanel).toBe(true)
    expect(procurementStore.selectedDemands).toEqual([])
  })

  it('openPanel keeps the selection when keepSelection is passed', () => {
    const store = useMadeItemsDemandsFiltersStore()
    const procurementStore = useMadeItemsProcurementStore()
    procurementStore.selectedDemands = [demand(1)]

    store.openPanel('lots', { keepSelection: true })

    expect(store.showManageLotsPanel).toBe(true)
    expect(procurementStore.selectedDemands).toEqual([demand(1)])
  })

  it('closePanel closes both panels and clears the selection', () => {
    const store = useMadeItemsDemandsFiltersStore()
    const procurementStore = useMadeItemsProcurementStore()
    store.openPanel('stock', { keepSelection: true })
    procurementStore.selectedDemands = [demand(1)]

    store.closePanel()

    expect(store.showManageLotsPanel).toBe(false)
    expect(store.showManageStockPanel).toBe(false)
    expect(procurementStore.selectedDemands).toEqual([])
  })

  it('togglePanel opens a closed panel and closes an open one', () => {
    const store = useMadeItemsDemandsFiltersStore()

    store.togglePanel('lots')
    expect(store.showManageLotsPanel).toBe(true)

    store.togglePanel('lots')
    expect(store.showManageLotsPanel).toBe(false)
  })

  it('toggleManageLotsPanel stays a thin alias for togglePanel("lots")', () => {
    // MadeItemsDemandsTable.manageLotsFilter.spec.ts (an existing spec this
    // wave must not edit) calls toggleManageLotsPanel() directly.
    const store = useMadeItemsDemandsFiltersStore()

    store.toggleManageLotsPanel()
    expect(store.showManageLotsPanel).toBe(true)

    store.toggleManageLotsPanel()
    expect(store.showManageLotsPanel).toBe(false)
  })

  it('either panel opening narrows the list via notFullyAllocatedOnly, and closing widens it again', async () => {
    const store = useMadeItemsDemandsFiltersStore()

    // The watcher driving notFullyAllocatedOnly off the panel refs runs on
    // Vue's own flush, not synchronously.
    store.openPanel('stock')
    await nextTick()
    expect(store.notFullyAllocatedOnly).toBe(true)

    store.closePanel()
    await nextTick()
    expect(store.notFullyAllocatedOnly).toBe(false)

    store.openPanel('lots')
    await nextTick()
    expect(store.notFullyAllocatedOnly).toBe(true)
  })
})
