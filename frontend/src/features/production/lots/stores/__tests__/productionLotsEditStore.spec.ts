import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useProductionLotsEditStore } from '../productionLotsEditStore'
import { makeLotSummaryResponse } from '@/test-utils/factories'

import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

function makeLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return makeLotSummaryResponse({ public_id: '22222222-2222-2222-2222-222222222222', ...overrides })
}

describe('useProductionLotsEditStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with edit mode off and no selection', () => {
    const store = useProductionLotsEditStore()

    expect(store.editMode).toBe(false)
    expect(store.selectedItems).toEqual([])
  })

  it('toggleEditMode flips editMode on and off', () => {
    const store = useProductionLotsEditStore()

    store.toggleEditMode()
    expect(store.editMode).toBe(true)

    store.toggleEditMode()
    expect(store.editMode).toBe(false)
  })

  it('turning edit mode off clears any selected items', () => {
    const store = useProductionLotsEditStore()
    store.toggleEditMode()
    store.setSelectedItems([makeLot({ id: 1 }), makeLot({ id: 2 })])
    expect(store.selectedItems).toHaveLength(2)

    store.toggleEditMode()

    expect(store.editMode).toBe(false)
    expect(store.selectedItems).toEqual([])
  })

  it('turning edit mode on leaves an empty selection untouched', () => {
    const store = useProductionLotsEditStore()

    store.toggleEditMode()

    expect(store.editMode).toBe(true)
    expect(store.selectedItems).toEqual([])
  })

  it('setSelectedItems replaces the selection wholesale', () => {
    const store = useProductionLotsEditStore()
    store.setSelectedItems([makeLot({ id: 1 })])

    store.setSelectedItems([makeLot({ id: 2 }), makeLot({ id: 3 })])

    expect(store.selectedItems.map((l) => l.id)).toEqual([2, 3])
  })
})
