import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useQaFiltersStore } from '../qaFiltersStore'

// The three toggles all reveal work the default worklist hides, so the
// contract is: everything off by default, each one counts as an active
// filter, and Clear puts them all back.
describe('useQaFiltersStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('hides completed, canceled and future tasks by default', () => {
    const store = useQaFiltersStore()
    expect(store.showCompleted).toBe(false)
    expect(store.showCanceled).toBe(false)
    expect(store.showFuture).toBe(false)
  })

  it('reports no active filters in its default state', () => {
    expect(useQaFiltersStore().hasActiveFilters).toBe(false)
  })

  it.each(['showCompleted', 'showCanceled', 'showFuture'] as const)(
    'counts %s as an active filter',
    (toggle) => {
      const store = useQaFiltersStore()
      store[toggle] = true
      expect(store.hasActiveFilters).toBe(true)
    },
  )

  it('counts a search term as an active filter', () => {
    const store = useQaFiltersStore()
    store.search = 'FN-26'
    expect(store.hasActiveFilters).toBe(true)
  })

  it('clearAll resets every toggle, the search and the sort', () => {
    const store = useQaFiltersStore()
    store.showCompleted = true
    store.showCanceled = true
    store.showFuture = true
    store.search = 'FN-26'
    store.setSort('part', 'desc')

    store.clearAll()

    expect(store.showCompleted).toBe(false)
    expect(store.showCanceled).toBe(false)
    expect(store.showFuture).toBe(false)
    expect(store.search).toBe('')
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
    expect(store.hasActiveFilters).toBe(false)
  })

  it('bumps clearTrigger so the view can refetch', () => {
    const store = useQaFiltersStore()
    const before = store.clearTrigger
    store.clearAll()
    expect(store.clearTrigger).toBe(before + 1)
  })
})

// The column filters of the task table: every one counts as active once
// set, and Clear resets them, the arrays to fresh empty ones.
describe('useQaFiltersStore column filters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it.each([
    ['statuses', ['completed']],
    ['inspectionMethodIds', [3]],
    ['finishedByIds', [7]],
    ['lotNumber', 'LN-26'],
    ['projectNumber', 'P26'],
    ['itemText', 'Shaft'],
    ['quantityMin', 1],
    ['quantityMax', 5],
    ['plannedStartFrom', new Date(2026, 8, 1)],
    ['plannedStartTo', new Date(2026, 8, 30)],
    ['finishedFrom', new Date(2026, 8, 1)],
    ['finishedTo', new Date(2026, 8, 30)],
  ] as const)('counts %s as an active filter', (field, value) => {
    const store = useQaFiltersStore()
    ;(store as unknown as Record<string, unknown>)[field] = value
    expect(store.hasActiveFilters).toBe(true)
  })

  it('does not count a cleared array filter as active', () => {
    const store = useQaFiltersStore()
    store.statuses = ['queued']
    store.statuses = []
    expect(store.hasActiveFilters).toBe(false)
  })

  it('clearAll resets every column filter', () => {
    const store = useQaFiltersStore()
    store.statuses = ['completed']
    store.inspectionMethodIds = [3]
    store.finishedByIds = [7]
    store.lotNumber = 'LN'
    store.projectNumber = 'P'
    store.itemText = 'Shaft'
    store.quantityMin = 1
    store.quantityMax = 5
    store.plannedStartFrom = new Date(2026, 8, 1)
    store.plannedStartTo = new Date(2026, 8, 30)
    store.finishedFrom = new Date(2026, 8, 1)
    store.finishedTo = new Date(2026, 8, 30)
    const statusesBefore = store.statuses

    store.clearAll()

    expect(store.statuses).toEqual([])
    expect(store.statuses).not.toBe(statusesBefore)
    expect(store.inspectionMethodIds).toEqual([])
    expect(store.finishedByIds).toEqual([])
    expect(store.lotNumber).toBe('')
    expect(store.projectNumber).toBe('')
    expect(store.itemText).toBe('')
    expect(store.quantityMin).toBeNull()
    expect(store.quantityMax).toBeNull()
    expect(store.plannedStartFrom).toBeNull()
    expect(store.plannedStartTo).toBeNull()
    expect(store.finishedFrom).toBeNull()
    expect(store.finishedTo).toBeNull()
    expect(store.hasActiveFilters).toBe(false)
  })
})
