import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'

import { useLotsTableBulkSelection } from '../useLotsTableBulkSelection'
import { useProductionLotsEditStore } from '../../../stores/productionLotsEditStore'
import { makeLotSummaryResponse } from '@/test-utils/factories'

import type { FlatPositionRow } from '../../../types/lotsTableFlatRow'
import type { LotSummaryResponse } from '../../../../types/productionLotsResponse'

// LotsTable.vue's onSelectionUpdate, the trickiest part of
// the bulk-edit checkbox column: in Column Mode, OpenVue's checkbox only
// ever renders (and toggles) a lot's first rowspanned row, so membership has
// to be reconstructed by diffing against the previous selection rather than
// read straight off the emitted array.

function makeLot(id: number): LotSummaryResponse {
  return makeLotSummaryResponse({
    id,
    public_id: `11111111-1111-1111-1111-11111111000${id}`,
    lot_number: `LOT-${id}`,
  })
}

function makeRow(lot: LotSummaryResponse, positionId: number): FlatPositionRow {
  return {
    rowKey: `${lot.id}-${positionId}`,
    lotId: lot.id,
    lot,
    group: null,
  }
}

describe('useLotsTableBulkSelection', () => {
  it('adds a lot to the edit selection in Row Mode', () => {
    setActivePinia(createPinia())
    const editStore = useProductionLotsEditStore()
    editStore.editMode = true

    const lot1 = makeLot(1)
    const { onSelectionUpdate } = useLotsTableBulkSelection(ref(false), ref(false), ref([]))

    onSelectionUpdate([lot1])

    expect(editStore.selectedItems).toEqual([lot1])
  })

  it('adds every position row of a multi-position lot when Column Mode selects its first row', () => {
    setActivePinia(createPinia())
    const editStore = useProductionLotsEditStore()
    editStore.editMode = true

    const lot1 = makeLot(1)
    const rowA = makeRow(lot1, 10)
    const rowB = makeRow(lot1, 20)
    const flatRows = ref<FlatPositionRow[]>([rowA, rowB])

    const { onSelectionUpdate } = useLotsTableBulkSelection(ref(false), ref(true), flatRows)

    // OpenVue's checkbox column only ever emits the group's anchor row.
    onSelectionUpdate([rowA])

    expect(editStore.selectedItems).toEqual([lot1])
  })

  it('removes the whole lot when Column Mode unchecks its anchor row', () => {
    setActivePinia(createPinia())
    const editStore = useProductionLotsEditStore()
    editStore.editMode = true
    const lot1 = makeLot(1)
    const lot2 = makeLot(2)
    editStore.selectedItems = [lot1, lot2]

    const rowA = makeRow(lot1, 10)
    const rowB = makeRow(lot1, 20)
    const flatRows = ref<FlatPositionRow[]>([rowA, rowB])

    const { onSelectionUpdate } = useLotsTableBulkSelection(ref(false), ref(true), flatRows)

    // Previous selection (both of lot1's rows) minus the anchor row being
    // unchecked: lot1 must drop out entirely, lot2 must stay untouched.
    onSelectionUpdate([])

    expect(editStore.selectedItems).toEqual([lot2])
  })

  it('does nothing when neither bulk edit nor Manage Source is active', () => {
    setActivePinia(createPinia())
    const editStore = useProductionLotsEditStore()
    editStore.editMode = false

    const { onSelectionUpdate, rowSelectionTarget } = useLotsTableBulkSelection(
      ref(false),
      ref(false),
      ref([]),
    )

    expect(rowSelectionTarget.value).toBeNull()
    expect(() => onSelectionUpdate([makeLot(1)])).not.toThrow()
    expect(editStore.selectedItems).toEqual([])
  })

  it('keeps the checkboxes outside both modes for a user who may bulk edit', () => {
    setActivePinia(createPinia())
    const editStore = useProductionLotsEditStore()

    const lot1 = makeLot(1)
    const { onSelectionUpdate, isIdleSelection } = useLotsTableBulkSelection(
      ref(false),
      ref(false),
      ref([]),
      () => true,
    )

    expect(isIdleSelection.value).toBe(true)
    onSelectionUpdate([lot1])
    expect(editStore.selectedItems).toEqual([lot1])
  })

  it('drops the selection a plain row click would set, so the checked lots survive', async () => {
    setActivePinia(createPinia())
    const editStore = useProductionLotsEditStore()
    const lot1 = makeLot(1)
    const lot2 = makeLot(2)
    editStore.selectedItems = [lot1]

    const { onSelectionUpdate, markRowClick } = useLotsTableBulkSelection(
      ref(false),
      ref(false),
      ref([]),
      () => true,
    )

    markRowClick({ originalEvent: new MouseEvent('click'), data: lot2, index: 1 })
    onSelectionUpdate([lot2])
    expect(editStore.selectedItems).toEqual([lot1])
    // The next click is a separate event, after the plain click has settled.
    await Promise.resolve()

    markRowClick({ originalEvent: new MouseEvent('click', { ctrlKey: true }), data: lot2, index: 1 })
    onSelectionUpdate([lot1, lot2])
    expect(editStore.selectedItems).toEqual([lot1, lot2])
  })
})
