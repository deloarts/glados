import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useProductionLotsFiltersStore } from '../productionLotsFiltersStore'

// Mirrors the existing productionLotsFiltersStore.spec.ts's own coverage of
// needsAssignmentOnly; needsApprovalOnly is the same shape (a plain generic
// TFields boolean), added rather than folded into the read-only sibling file.
describe('useProductionLotsFiltersStore needsApprovalOnly', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('defaults to false', () => {
    const store = useProductionLotsFiltersStore()
    expect(store.needsApprovalOnly).toBe(false)
  })

  it('toggleNeedsApprovalOnly flips the field', () => {
    const store = useProductionLotsFiltersStore()
    store.toggleNeedsApprovalOnly()
    expect(store.needsApprovalOnly).toBe(true)
    store.toggleNeedsApprovalOnly()
    expect(store.needsApprovalOnly).toBe(false)
  })

  it.each(['needsAssignmentOnly', 'needsApprovalOnly'] as const)(
    'counts %s as an active filter, alongside the other',
    (field) => {
      const store = useProductionLotsFiltersStore()
      expect(store.hasActiveFilters).toBe(false)
      store[field] = true
      expect(store.hasActiveFilters).toBe(true)
    },
  )

  it('clearAll resets needsApprovalOnly back to false, alongside needsAssignmentOnly', () => {
    const store = useProductionLotsFiltersStore()
    store.needsAssignmentOnly = true
    store.needsApprovalOnly = true
    const before = store.clearTrigger

    store.clearAll()

    expect(store.needsAssignmentOnly).toBe(false)
    expect(store.needsApprovalOnly).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
    expect(store.clearTrigger).toBe(before + 1)
  })

  // The two toggles are independent: flipping one must not disturb the
  // other, matching "append, don't rewrite".
  it('toggling one does not flip the other', () => {
    const store = useProductionLotsFiltersStore()
    store.toggleNeedsApprovalOnly()
    expect(store.needsApprovalOnly).toBe(true)
    expect(store.needsAssignmentOnly).toBe(false)

    store.toggleNeedsAssignmentOnly()
    expect(store.needsAssignmentOnly).toBe(true)
    expect(store.needsApprovalOnly).toBe(true)
  })
})
