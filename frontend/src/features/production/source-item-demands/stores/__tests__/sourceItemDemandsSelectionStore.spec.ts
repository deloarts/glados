import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useSourceItemDemandsSelectionStore } from '../sourceItemDemandsSelectionStore'
import type { SourceItemDemandResponse } from '@/features/source-items'

function makeDemand(overrides: Partial<SourceItemDemandResponse> = {}): SourceItemDemandResponse {
  return { id: 1, quantity: 10, ...overrides } as unknown as SourceItemDemandResponse
}

describe('useSourceItemDemandsSelectionStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with no selection and refreshTrigger at zero', () => {
    const store = useSourceItemDemandsSelectionStore()
    expect(store.selectedDemands).toEqual([])
    expect(store.refreshTrigger).toBe(0)
  })

  it('selectedDemands is a plain writable ref the table binds v-model:selection to', () => {
    const store = useSourceItemDemandsSelectionStore()
    const demands = [makeDemand({ id: 1 }), makeDemand({ id: 2 })]

    store.selectedDemands = demands

    expect(store.selectedDemands).toEqual(demands)
  })

  it('clearSelection empties the current selection', () => {
    const store = useSourceItemDemandsSelectionStore()
    store.selectedDemands = [makeDemand({ id: 1 })]

    store.clearSelection()

    expect(store.selectedDemands).toEqual([])
  })

  it('triggerRefresh increments refreshTrigger without touching the selection', () => {
    const store = useSourceItemDemandsSelectionStore()
    store.selectedDemands = [makeDemand({ id: 1 })]

    store.triggerRefresh()

    expect(store.refreshTrigger).toBe(1)
    expect(store.selectedDemands).toHaveLength(1)

    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(2)
  })
})
