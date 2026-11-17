import { describe, it, expect, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { useBoughtItemsDemandsFiltersStore } from '../boughtItemsDemandsFiltersStore'
import { useBoughtItemsProcurementStore } from '../boughtItemsProcurementStore'
import type { BoughtItemDemandResponse } from '@/features/bought-items'

describe('useBoughtItemsDemandsFiltersStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // bucketIds is an array: the generic default-equality check would compare
  // a freshly-cleared [] against the original default [] by reference and
  // report it permanently active. This is the parity spec for the custom
  // `isActive` passed to the factory (see madeItemsDemandsFiltersStore for
  // the same shape of problem).
  it('starts with no active filters', () => {
    const store = useBoughtItemsDemandsFiltersStore()
    expect(store.bucketIds).toEqual([])
    expect(store.includeUnbucketed).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
  })

  it('counts a non-empty bucketIds as an active filter', () => {
    const store = useBoughtItemsDemandsFiltersStore()
    store.bucketIds.push(1)
    expect(store.hasActiveFilters).toBe(true)
  })

  it('counts includeUnbucketed as an active filter', () => {
    const store = useBoughtItemsDemandsFiltersStore()
    store.includeUnbucketed = true
    expect(store.hasActiveFilters).toBe(true)
  })

  it('clearAll resets bucketIds/includeUnbucketed and rebuilds a fresh array', () => {
    const store = useBoughtItemsDemandsFiltersStore()
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

  it('counts idFilter as an active filter', () => {
    const store = useBoughtItemsDemandsFiltersStore()
    expect(store.idFilter).toBeNull()
    store.idFilter = 42
    expect(store.hasActiveFilters).toBe(true)
  })

  it('counts a non-empty orderIds as active and an empty one as inactive', () => {
    const store = useBoughtItemsDemandsFiltersStore()
    expect(store.orderIds).toEqual([])
    expect(store.hasActiveFilters).toBe(false)
    store.orderIds = [7]
    expect(store.hasActiveFilters).toBe(true)
    store.orderIds = []
    expect(store.hasActiveFilters).toBe(false)
  })

  it('clearAll resets idFilter and rebuilds a fresh orderIds array', () => {
    const store = useBoughtItemsDemandsFiltersStore()
    const originalOrderIds = store.orderIds
    store.idFilter = 42
    store.orderIds.push(7, 8)

    store.clearAll()

    expect(store.idFilter).toBeNull()
    expect(store.orderIds).toEqual([])
    expect(store.orderIds).not.toBe(originalOrderIds)
    expect(store.hasActiveFilters).toBe(false)
  })

  function demand(id: number): BoughtItemDemandResponse {
    return { id } as unknown as BoughtItemDemandResponse
  }

  it('openPanel opens the requested panel, closes the other, and clears the selection by default', () => {
    const store = useBoughtItemsDemandsFiltersStore()
    const procurementStore = useBoughtItemsProcurementStore()
    procurementStore.selectedDemands = [demand(1)]

    store.openPanel('orders')

    expect(store.showManageOrderPanel).toBe(true)
    expect(store.showManageStockPanel).toBe(false)
    expect(procurementStore.selectedDemands).toEqual([])

    procurementStore.selectedDemands = [demand(1)]
    store.openPanel('stock')

    expect(store.showManageOrderPanel).toBe(false)
    expect(store.showManageStockPanel).toBe(true)
    expect(procurementStore.selectedDemands).toEqual([])
  })

  it('openPanel keeps the selection when keepSelection is passed', () => {
    const store = useBoughtItemsDemandsFiltersStore()
    const procurementStore = useBoughtItemsProcurementStore()
    procurementStore.selectedDemands = [demand(1)]

    store.openPanel('orders', { keepSelection: true })

    expect(store.showManageOrderPanel).toBe(true)
    expect(procurementStore.selectedDemands).toEqual([demand(1)])
  })

  it('closePanel closes both panels and clears the selection', () => {
    const store = useBoughtItemsDemandsFiltersStore()
    const procurementStore = useBoughtItemsProcurementStore()
    store.openPanel('stock', { keepSelection: true })
    procurementStore.selectedDemands = [demand(1)]

    store.closePanel()

    expect(store.showManageOrderPanel).toBe(false)
    expect(store.showManageStockPanel).toBe(false)
    expect(procurementStore.selectedDemands).toEqual([])
  })

  it('togglePanel opens a closed panel and closes an open one', () => {
    const store = useBoughtItemsDemandsFiltersStore()

    store.togglePanel('orders')
    expect(store.showManageOrderPanel).toBe(true)

    store.togglePanel('orders')
    expect(store.showManageOrderPanel).toBe(false)
  })

  it('either panel opening narrows the list via notFullyAllocatedOnly, and closing widens it again', async () => {
    const store = useBoughtItemsDemandsFiltersStore()

    // The watcher driving notFullyAllocatedOnly off the panel refs runs on
    // Vue's own flush, not synchronously, so each step awaits a flush, as
    // BoughtItemsDemandsTable.manageOrderFilter.spec.ts does after toggling the panel.
    store.openPanel('stock')
    await nextTick()
    expect(store.notFullyAllocatedOnly).toBe(true)

    store.closePanel()
    await nextTick()
    expect(store.notFullyAllocatedOnly).toBe(false)

    store.openPanel('orders')
    await nextTick()
    expect(store.notFullyAllocatedOnly).toBe(true)
  })
})
