import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useOrdersFiltersStore } from '../ordersFiltersStore'

// Built on createFiltersStore using the generic pattern (see
// productionLotsFiltersStore.spec.ts). This is the parity spec for the
// generic default-equality fields plus everything living outside them via
// `extend`: showActions, showOrderFiles, groupBy, and the two
// hideDelivered/hideCanceled toggles.
describe('useOrdersFiltersStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with every field at its default and no active filters', () => {
    const store = useOrdersFiltersStore()
    expect(store.search).toBe('')
    expect(store.statusFilter).toEqual([])
    expect(store.supplierFilter).toBeNull()
    expect(store.hideDelivered).toBe(false)
    expect(store.hideCanceled).toBe(false)
    expect(store.invoiceFilter).toBeNull()
    expect(store.hasActiveFilters).toBe(false)
  })

  it('starts with showActions off, showOrderFiles on, and no groupBy', () => {
    const store = useOrdersFiltersStore()
    expect(store.showActions).toBe(false)
    expect(store.showOrderFiles).toBe(true)
    expect(store.groupBy).toBeNull()
  })

  it('counts statusFilter/supplierFilter/creatorFilter as active filters', () => {
    const s1 = useOrdersFiltersStore()
    s1.statusFilter = ['draft']
    expect(s1.hasActiveFilters).toBe(true)

    setActivePinia(createPinia())
    const s2 = useOrdersFiltersStore()
    s2.supplierFilter = 3
    expect(s2.hasActiveFilters).toBe(true)

    setActivePinia(createPinia())
    const s3 = useOrdersFiltersStore()
    s3.creatorFilter = 7
    expect(s3.hasActiveFilters).toBe(true)
  })

  it('counts noteFilter/storagePlaceFilter as active filters', () => {
    const s1 = useOrdersFiltersStore()
    expect(s1.noteFilter).toBe('')
    expect(s1.storagePlaceFilter).toBe('')
    s1.noteFilter = 'urgent'
    expect(s1.hasActiveFilters).toBe(true)

    setActivePinia(createPinia())
    const s2 = useOrdersFiltersStore()
    s2.storagePlaceFilter = 'Shelf A'
    expect(s2.hasActiveFilters).toBe(true)
  })

  it('clearAll resets noteFilter and storagePlaceFilter', () => {
    const store = useOrdersFiltersStore()
    store.noteFilter = 'urgent'
    store.storagePlaceFilter = 'Shelf A'
    store.clearAll()
    expect(store.noteFilter).toBe('')
    expect(store.storagePlaceFilter).toBe('')
    expect(store.hasActiveFilters).toBe(false)
  })

  it('counts hideDelivered/hideCanceled as active filters', () => {
    const store = useOrdersFiltersStore()
    store.hideDelivered = true
    expect(store.hasActiveFilters).toBe(true)
    store.hideDelivered = false
    store.hideCanceled = true
    expect(store.hasActiveFilters).toBe(true)
  })

  it('counts each date-range field as an active filter', () => {
    const store = useOrdersFiltersStore()
    store.orderedFrom = new Date('2026-01-01')
    expect(store.hasActiveFilters).toBe(true)
  })

  it('groupBy, showActions, and showOrderFiles do not count as active filters', () => {
    const store = useOrdersFiltersStore()
    store.setGroupBy('status')
    store.toggleShowActions()
    store.toggleShowOrderFiles()
    expect(store.hasActiveFilters).toBe(false)
  })

  it('setGroupBy toggles off when the same value is picked again', () => {
    const store = useOrdersFiltersStore()
    store.setGroupBy('supplier')
    expect(store.groupBy).toBe('supplier')
    store.setGroupBy('supplier')
    expect(store.groupBy).toBeNull()
  })

  it('setGroupBy switches directly from one group to another', () => {
    const store = useOrdersFiltersStore()
    store.setGroupBy('status')
    store.setGroupBy('supplier')
    expect(store.groupBy).toBe('supplier')
  })

  it('clearGroupBy resets groupBy to null', () => {
    const store = useOrdersFiltersStore()
    store.setGroupBy('status')
    store.clearGroupBy()
    expect(store.groupBy).toBeNull()
  })

  it('toggleShowActions/toggleShowOrderFiles flip their respective flags', () => {
    const store = useOrdersFiltersStore()
    store.toggleShowActions()
    expect(store.showActions).toBe(true)
    store.toggleShowOrderFiles()
    expect(store.showOrderFiles).toBe(false)
  })

  it('toggleHideDelivered/toggleHideCanceled flip the generic fields', () => {
    const store = useOrdersFiltersStore()
    store.toggleHideDelivered()
    expect(store.hideDelivered).toBe(true)
    store.toggleHideCanceled()
    expect(store.hideCanceled).toBe(true)
  })

  it('toggleMissingInvoice flips between missing and off and counts as an active filter', () => {
    const store = useOrdersFiltersStore()
    store.toggleMissingInvoice()
    expect(store.invoiceFilter).toBe('missing')
    expect(store.hasActiveFilters).toBe(true)
    store.toggleMissingInvoice()
    expect(store.invoiceFilter).toBeNull()
    expect(store.hasActiveFilters).toBe(false)
  })

  it('clearAll resets invoiceFilter', () => {
    const store = useOrdersFiltersStore()
    store.invoiceFilter = 'present'
    store.clearAll()
    expect(store.invoiceFilter).toBeNull()
  })

  it('clearAll resets every generic field and groupBy, bumps clearTrigger, but leaves showActions/showOrderFiles alone', () => {
    const store = useOrdersFiltersStore()
    store.search = 'ORD-1'
    store.statusFilter = ['draft']
    store.hideDelivered = true
    store.setGroupBy('supplier')
    store.toggleShowActions()
    const before = store.clearTrigger

    store.clearAll()

    expect(store.search).toBe('')
    expect(store.statusFilter).toEqual([])
    expect(store.hideDelivered).toBe(false)
    expect(store.groupBy).toBeNull()
    expect(store.hasActiveFilters).toBe(false)
    expect(store.clearTrigger).toBe(before + 1)
    // showActions is UI display state, not a filter, so clearAll leaves it be.
    expect(store.showActions).toBe(true)
  })
})
