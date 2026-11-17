import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useProductionLotsSourceStore } from '../productionLotsSourceStore'
import { makeLotSummaryResponse } from '@/test-utils/factories'

import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

function makeLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return makeLotSummaryResponse({ public_id: '22222222-2222-2222-2222-222222222222', ...overrides })
}

describe('useProductionLotsSourceStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with an empty selection', () => {
    const store = useProductionLotsSourceStore()

    expect(store.selectedLots).toEqual([])
  })

  it('setSelectedLots replaces the selection wholesale', () => {
    const store = useProductionLotsSourceStore()
    store.setSelectedLots([makeLot({ id: 1 })])

    store.setSelectedLots([makeLot({ id: 2 }), makeLot({ id: 3 })])

    expect(store.selectedLots.map((l) => l.id)).toEqual([2, 3])
  })

  it('removeLot drops only the matching lot by id', () => {
    const store = useProductionLotsSourceStore()
    store.setSelectedLots([makeLot({ id: 1 }), makeLot({ id: 2 }), makeLot({ id: 3 })])

    store.removeLot(2)

    expect(store.selectedLots.map((l) => l.id)).toEqual([1, 3])
  })

  it('removeLot is a no-op when the id is not in the selection', () => {
    const store = useProductionLotsSourceStore()
    store.setSelectedLots([makeLot({ id: 1 })])

    store.removeLot(99)

    expect(store.selectedLots.map((l) => l.id)).toEqual([1])
  })

  it('clearSelection empties the selection', () => {
    const store = useProductionLotsSourceStore()
    store.setSelectedLots([makeLot({ id: 1 }), makeLot({ id: 2 })])

    store.clearSelection()

    expect(store.selectedLots).toEqual([])
  })
})
