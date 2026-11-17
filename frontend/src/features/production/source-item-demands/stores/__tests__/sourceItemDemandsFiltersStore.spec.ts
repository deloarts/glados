import { describe, it, expect, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { useSourceItemDemandsFiltersStore } from '../sourceItemDemandsFiltersStore'
import { useSourceItemDemandsSelectionStore } from '../sourceItemDemandsSelectionStore'
import { useSourceItemDemandsQuery } from '../../composables/useSourceItemDemandsQuery'
import type { SourceItemDemandResponse } from '@/features/source-items'

describe('useSourceItemDemandsFiltersStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // bucketIds is an array: the generic default-equality check would compare
  // a freshly-cleared [] against the original default [] by reference and
  // report it permanently active. This is the parity spec for the custom
  // `isActive` passed to the factory (see boughtItemsDemandsFiltersStore.spec.ts
  // for the same shape of problem).
  it('starts with no active filters', () => {
    const store = useSourceItemDemandsFiltersStore()
    expect(store.bucketIds).toEqual([])
    expect(store.includeUnbucketed).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
  })

  it('counts a non-empty bucketIds as an active filter', () => {
    const store = useSourceItemDemandsFiltersStore()
    store.bucketIds.push(1)
    expect(store.hasActiveFilters).toBe(true)
  })

  it('counts a search term as an active filter and sends it trimmed', () => {
    const store = useSourceItemDemandsFiltersStore()
    store.search = '  1.4301 '
    expect(store.hasActiveFilters).toBe(true)
    expect(useSourceItemDemandsQuery().filterParams()).toMatchObject({ search: '1.4301' })

    store.search = '   '
    expect(useSourceItemDemandsQuery().filterParams()).not.toHaveProperty('search')
  })

  it('counts includeUnbucketed as an active filter', () => {
    const store = useSourceItemDemandsFiltersStore()
    store.includeUnbucketed = true
    expect(store.hasActiveFilters).toBe(true)
  })

  it('clearAll resets bucketIds/includeUnbucketed and rebuilds a fresh array', () => {
    const store = useSourceItemDemandsFiltersStore()
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

  type FiltersStore = ReturnType<typeof useSourceItemDemandsFiltersStore>

  it.each<[string, (store: FiltersStore) => void]>([
    ['idFilter', (s) => (s.idFilter = 42)],
    ['projectId', (s) => (s.projectId = 5)],
    ['itemDimension', (s) => (s.itemDimension = '10mm')],
    ['itemMaterial', (s) => (s.itemMaterial = 'Steel')],
    ['itemType', (s) => (s.itemType = 'Rod')],
    ['lotIds', (s) => s.lotIds.push(3)],
    ['orderIds', (s) => s.orderIds.push(7)],
    ['desiredFrom', (s) => (s.desiredFrom = new Date(2026, 0, 1))],
    ['desiredTo', (s) => (s.desiredTo = new Date(2026, 0, 31))],
  ])('counts %s as an active filter on its own', (_name, apply) => {
    const store = useSourceItemDemandsFiltersStore()
    expect(store.hasActiveFilters).toBe(false)
    apply(store)
    expect(store.hasActiveFilters).toBe(true)
  })

  it('treats empty lotIds/orderIds and empty text fields as inactive', () => {
    const store = useSourceItemDemandsFiltersStore()
    expect(store.lotIds).toEqual([])
    expect(store.orderIds).toEqual([])
    expect(store.idFilter).toBeNull()
    expect(store.projectId).toBeNull()
    expect(store.itemDimension).toBe('')
    expect(store.itemMaterial).toBe('')
    expect(store.itemType).toBe('')
    expect(store.desiredFrom).toBeNull()
    expect(store.desiredTo).toBeNull()
    expect(store.hasActiveFilters).toBe(false)
  })

  it('clearAll resets every column filter and rebuilds fresh lotIds/orderIds arrays', () => {
    const store = useSourceItemDemandsFiltersStore()
    const originalLotIds = store.lotIds
    const originalOrderIds = store.orderIds
    store.idFilter = 42
    store.projectId = 5
    store.itemDimension = '10mm'
    store.itemMaterial = 'Steel'
    store.itemType = 'Rod'
    store.lotIds.push(3)
    store.orderIds.push(7)
    store.desiredFrom = new Date(2026, 0, 1)
    store.desiredTo = new Date(2026, 0, 31)

    store.clearAll()

    expect(store.idFilter).toBeNull()
    expect(store.projectId).toBeNull()
    expect(store.itemDimension).toBe('')
    expect(store.itemMaterial).toBe('')
    expect(store.itemType).toBe('')
    expect(store.lotIds).toEqual([])
    expect(store.orderIds).toEqual([])
    expect(store.desiredFrom).toBeNull()
    expect(store.desiredTo).toBeNull()
    expect(store.hasActiveFilters).toBe(false)
    expect(store.lotIds).not.toBe(originalLotIds)
    expect(store.orderIds).not.toBe(originalOrderIds)
  })

  function demand(id: number): SourceItemDemandResponse {
    return { id } as unknown as SourceItemDemandResponse
  }

  it('openPanel opens the requested panel, closes the other, and clears the selection by default', () => {
    const store = useSourceItemDemandsFiltersStore()
    const selectionStore = useSourceItemDemandsSelectionStore()
    selectionStore.selectedDemands = [demand(1)]

    store.openPanel('orders')

    expect(store.showManageOrderPanel).toBe(true)
    expect(store.showManageStockPanel).toBe(false)
    expect(selectionStore.selectedDemands).toEqual([])

    selectionStore.selectedDemands = [demand(1)]
    store.openPanel('stock')

    expect(store.showManageOrderPanel).toBe(false)
    expect(store.showManageStockPanel).toBe(true)
    expect(selectionStore.selectedDemands).toEqual([])
  })

  it('openPanel keeps the selection when keepSelection is passed', () => {
    const store = useSourceItemDemandsFiltersStore()
    const selectionStore = useSourceItemDemandsSelectionStore()
    selectionStore.selectedDemands = [demand(1)]

    store.openPanel('orders', { keepSelection: true })

    expect(store.showManageOrderPanel).toBe(true)
    expect(selectionStore.selectedDemands).toEqual([demand(1)])
  })

  it('closePanel closes both panels and clears the selection', () => {
    const store = useSourceItemDemandsFiltersStore()
    const selectionStore = useSourceItemDemandsSelectionStore()
    store.openPanel('stock', { keepSelection: true })
    selectionStore.selectedDemands = [demand(1)]

    store.closePanel()

    expect(store.showManageOrderPanel).toBe(false)
    expect(store.showManageStockPanel).toBe(false)
    expect(selectionStore.selectedDemands).toEqual([])
  })

  it('togglePanel opens a closed panel and closes an open one', () => {
    const store = useSourceItemDemandsFiltersStore()

    store.togglePanel('orders')
    expect(store.showManageOrderPanel).toBe(true)

    store.togglePanel('orders')
    expect(store.showManageOrderPanel).toBe(false)
  })

  it('either panel opening narrows the list via notFullyAllocatedOnly, and closing widens it again', async () => {
    const store = useSourceItemDemandsFiltersStore()

    // The watcher driving notFullyAllocatedOnly off the panel refs runs on
    // Vue's own flush, not synchronously, so each step awaits a flush, as
    // SourceItemDemandsTable.manageOrderFilter.spec.ts does after toggling the panel.
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
