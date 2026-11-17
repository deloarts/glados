import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useProductionLotsFiltersStore } from '../productionLotsFiltersStore'

// The store is built on createFiltersStore. Besides the generic fields,
// this spec covers coverageFilterArmed and groupBy/simpleMode/
// widescreenMode, which live outside the generic field set via `extend`.
describe('useProductionLotsFiltersStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with every field at its default and no active filters', () => {
    const store = useProductionLotsFiltersStore()
    expect(store.search).toBe('')
    expect(store.statusFilter).toBeNull()
    expect(store.priorityFilter).toBeNull()
    expect(store.hideCompleted).toBe(false)
    expect(store.hideCanceled).toBe(false)
    expect(store.actionableFilterArmed).toBe(false)
    expect(store.coverageFilterArmed).toBe(false)
    // On by default: the smart filter is opt-out, not opt-in.
    expect(store.smartFilterEnabled).toBe(true)
    expect(store.hasActiveFilters).toBe(false)
  })

  it('counts search, projectNumber and itemArticleName as active filters', () => {
    const s1 = useProductionLotsFiltersStore()
    s1.search = 'FN-26'
    expect(s1.hasActiveFilters).toBe(true)

    setActivePinia(createPinia())
    const s2 = useProductionLotsFiltersStore()
    s2.projectNumber = 'P-1'
    expect(s2.hasActiveFilters).toBe(true)

    setActivePinia(createPinia())
    const s3 = useProductionLotsFiltersStore()
    s3.itemArticleName = 'widget'
    expect(s3.hasActiveFilters).toBe(true)
  })

  it('counts statusFilter/priorityFilter/creatorFilter as active filters', () => {
    const store = useProductionLotsFiltersStore()
    store.statusFilter = 'draft'
    expect(store.hasActiveFilters).toBe(true)
    store.statusFilter = null
    store.priorityFilter = 'high'
    expect(store.hasActiveFilters).toBe(true)
    store.priorityFilter = null
    store.creatorFilter = 7
    expect(store.hasActiveFilters).toBe(true)
  })

  it('counts createdFrom/createdTo as active filters', () => {
    const store = useProductionLotsFiltersStore()
    store.createdFrom = new Date('2026-01-01')
    expect(store.hasActiveFilters).toBe(true)
    store.createdFrom = null
    store.createdTo = new Date('2026-01-02')
    expect(store.hasActiveFilters).toBe(true)
  })

  it.each([
    'hideCompleted',
    'hideCanceled',
    'needsAssignmentOnly',
    'actionableFilterArmed',
    'coverageFilterArmed',
  ] as const)('counts %s as an active filter', (field) => {
    const store = useProductionLotsFiltersStore()
    store[field] = true
    expect(store.hasActiveFilters).toBe(true)
  })

  // The per-column filters added for the lot, source and step columns.
  // Every one of them defaults to '' or null, so the generic default-
  // equality read of hasActiveFilters covers them without an isActive
  // override.
  const columnFilterSamples = {
    lotNumber: 'LOT-7',
    targetDateFrom: new Date('2026-01-01'),
    targetDateTo: new Date('2026-01-31'),
    quantityMin: 0,
    quantityMax: 50,
    sourceText: 'S355',
    sourceDimension: '40 x 8',
    sourceType: 'Flat bar',
    sourceStatus: 'ordered',
    sourceDeliveryFrom: new Date('2026-02-01'),
    sourceDeliveryTo: new Date('2026-02-28'),
    stepMethod: 'fabrication:3',
    stepStatus: 'queued',
    stepSetupMin: 5,
    stepSetupMax: 30,
    stepPerPieceMin: 0.5,
    stepPerPieceMax: 2,
    stepPlannedStartFrom: new Date('2026-03-01'),
    stepPlannedStartTo: new Date('2026-03-15'),
    stepPlannedEndFrom: new Date('2026-03-16'),
    stepPlannedEndTo: new Date('2026-03-31'),
    stepDeliveryFrom: new Date('2026-04-01'),
    stepDeliveryTo: new Date('2026-04-30'),
    stepNote: 'deburr',
  } as const

  it.each(Object.entries(columnFilterSamples))(
    'counts the column filter %s as an active filter',
    (field, value) => {
      const store = useProductionLotsFiltersStore()
      expect(store.hasActiveFilters).toBe(false)
      ;(store as unknown as Record<string, unknown>)[field] = value
      expect(store.hasActiveFilters).toBe(true)
    },
  )

  it('clearAll resets every column filter back to its default', () => {
    const store = useProductionLotsFiltersStore()
    for (const [field, value] of Object.entries(columnFilterSamples)) {
      ;(store as unknown as Record<string, unknown>)[field] = value
    }
    expect(store.hasActiveFilters).toBe(true)

    store.clearAll()

    expect(store.lotNumber).toBe('')
    expect(store.sourceText).toBe('')
    expect(store.stepNote).toBe('')
    expect(store.targetDateFrom).toBeNull()
    expect(store.targetDateTo).toBeNull()
    expect(store.quantityMin).toBeNull()
    expect(store.quantityMax).toBeNull()
    expect(store.sourceStatus).toBeNull()
    expect(store.sourceDeliveryFrom).toBeNull()
    expect(store.sourceDeliveryTo).toBeNull()
    expect(store.stepMethod).toBeNull()
    expect(store.stepStatus).toBeNull()
    expect(store.stepSetupMin).toBeNull()
    expect(store.stepSetupMax).toBeNull()
    expect(store.stepPerPieceMin).toBeNull()
    expect(store.stepPerPieceMax).toBeNull()
    expect(store.stepPlannedStartFrom).toBeNull()
    expect(store.stepPlannedStartTo).toBeNull()
    expect(store.stepPlannedEndFrom).toBeNull()
    expect(store.stepPlannedEndTo).toBeNull()
    expect(store.stepDeliveryFrom).toBeNull()
    expect(store.stepDeliveryTo).toBeNull()
    expect(store.hasActiveFilters).toBe(false)
  })

  it('groupBy and sort do not count as active filters', () => {
    const store = useProductionLotsFiltersStore()
    store.setGroupBy('status')
    store.setSort('lot_number', 'desc')
    expect(store.hasActiveFilters).toBe(false)
  })

  it('setGroupBy toggles off when the same value is picked again, and turns on widescreen mode', () => {
    const store = useProductionLotsFiltersStore()
    expect(store.widescreenMode).toBe(false)

    store.setGroupBy('status')
    expect(store.groupBy).toBe('status')
    expect(store.widescreenMode).toBe(true)

    store.setGroupBy('status')
    expect(store.groupBy).toBeNull()
  })

  it('turning off widescreen mode clears an active groupBy', () => {
    const store = useProductionLotsFiltersStore()
    store.setGroupBy('priority')
    expect(store.widescreenMode).toBe(true)

    store.toggleWidescreenMode()
    expect(store.widescreenMode).toBe(false)
    expect(store.groupBy).toBeNull()
  })

  it('clearAll resets every generic field, the sort, and groupBy - but not simpleMode/widescreenMode', () => {
    const store = useProductionLotsFiltersStore()
    store.search = 'FN-26'
    store.statusFilter = 'draft'
    store.hideCompleted = true
    store.needsAssignmentOnly = true
    store.actionableFilterArmed = true
    store.coverageFilterArmed = true
    store.setSort('quantity', 'desc')
    store.setGroupBy('project')
    store.toggleSimpleMode()
    const before = store.clearTrigger

    store.clearAll()

    expect(store.search).toBe('')
    expect(store.statusFilter).toBeNull()
    expect(store.hideCompleted).toBe(false)
    expect(store.needsAssignmentOnly).toBe(false)
    expect(store.actionableFilterArmed).toBe(false)
    expect(store.coverageFilterArmed).toBe(false)
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
    expect(store.groupBy).toBeNull()
    expect(store.hasActiveFilters).toBe(false)
    expect(store.clearTrigger).toBe(before + 1)
    // simpleMode is UI display state, not a filter; clearAll leaves it be.
    expect(store.simpleMode).toBe(true)
  })

  it('toggleHideCompleted/toggleHideCanceled/toggleNeedsAssignmentOnly flip the generic fields', () => {
    const store = useProductionLotsFiltersStore()
    store.toggleHideCompleted()
    expect(store.hideCompleted).toBe(true)
    store.toggleHideCanceled()
    expect(store.hideCanceled).toBe(true)
    store.toggleNeedsAssignmentOnly()
    expect(store.needsAssignmentOnly).toBe(true)
  })

  it('toggleSmartFilter flips smartFilterEnabled, off then back on', () => {
    const store = useProductionLotsFiltersStore()
    store.toggleSmartFilter()
    expect(store.smartFilterEnabled).toBe(false)
    store.toggleSmartFilter()
    expect(store.smartFilterEnabled).toBe(true)
  })

  it('toggling smartFilterEnabled alone does not count toward hasActiveFilters', () => {
    const store = useProductionLotsFiltersStore()
    store.toggleSmartFilter()
    expect(store.smartFilterEnabled).toBe(false)
    expect(store.hasActiveFilters).toBe(false)
  })

  it('clearAll force-disables smartFilterEnabled even when it was on - Clear must actually widen the list', () => {
    // smartFilterEnabled defaults to true, so a plain reset-to-default
    // would be a no-op in the common case (nobody touched the toggle);
    // clicking Clear while Manage Production is open would then leave
    // actionable_for still narrowing the table, and Clear would seem to do
    // nothing.
    const store = useProductionLotsFiltersStore()
    expect(store.smartFilterEnabled).toBe(true)

    store.search = 'FN-26'
    store.clearAll()

    expect(store.search).toBe('')
    expect(store.smartFilterEnabled).toBe(false)
  })
})
