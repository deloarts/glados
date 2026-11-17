import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { BATCH_MADE_ITEM_DEMAND_IMPORT_DRAFT_STORAGE_KEY } from '@/core/stores/resetOnLogout'


const validateBatchMadeItemDemandsMock =
  vi.fn<
    (payload: ValidateBatchMadeItemDemandsRequest) => Promise<ValidateBatchMadeItemDemandsResponse>
  >()
const commitBatchMadeItemDemandsMock =
  vi.fn<
    (payload: CommitBatchMadeItemDemandsRequest) => Promise<CommitBatchMadeItemDemandsResponse>
  >()

vi.mock('@/features/made-items/api/madeItemDemandsApi', () => ({
  validateBatchMadeItemDemands: (payload: ValidateBatchMadeItemDemandsRequest) =>
    validateBatchMadeItemDemandsMock(payload),
  commitBatchMadeItemDemands: (payload: CommitBatchMadeItemDemandsRequest) =>
    commitBatchMadeItemDemandsMock(payload),
}))

import { useMadeItemsDemandsBatchDraftStore } from '../madeItemsDemandsBatchDraftStore'
import type {
  CommitBatchMadeItemDemandsRequest,
  CommitBatchMadeItemDemandsResponse,
  MadeItemBatchDemandRowInput,
  MadeItemRowValidationResult,
  ValidateBatchMadeItemDemandsRequest,
  ValidateBatchMadeItemDemandsResponse,
} from '@/features/made-items'

function makeRowInput(overrides: Partial<MadeItemBatchDemandRowInput> = {}): MadeItemBatchDemandRowInput {
  return {
    row_index: 0,
    project_number: 'PRJ-001',
    quantity: 1,
    part_number: 'PN-1',
    revision: 'A',
    article_name: 'Bracket',
    desired_delivery_date: null,
    note: null,
    ...overrides,
  }
}

function makeResult(overrides: Partial<MadeItemRowValidationResult> = {}): MadeItemRowValidationResult {
  return {
    row_index: 0,
    row_status: 'matched',
    match_source: 'part_number_revision',
    matched_item: null,
    divergences: [],
    resolved_project_id: 1,
    errors: [],
    ...overrides,
  }
}

describe('useMadeItemsDemandsBatchDraftStore', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    validateBatchMadeItemDemandsMock.mockReset()
    commitBatchMadeItemDemandsMock.mockReset()
  })

  it('allRowsValid is false when a row is not_found/ambiguous/unresolved/invalid', async () => {
    for (const status of ['not_found', 'ambiguous', 'unresolved_reference', 'invalid'] as const) {
      setActivePinia(createPinia())
      const store = useMadeItemsDemandsBatchDraftStore()
      store.addRow(makeRowInput())
      validateBatchMadeItemDemandsMock.mockResolvedValue({
        results: [makeResult({ row_status: status })],
        all_valid: false,
      })

      await store.validate()

      expect(store.allRowsValid).toBe(false)
    }
  })

  it('allRowsValid is false when the draft is stale after updateRow', async () => {
    const store = useMadeItemsDemandsBatchDraftStore()
    store.addRow(makeRowInput())
    validateBatchMadeItemDemandsMock.mockResolvedValue({
      results: [makeResult({ row_status: 'matched' })],
      all_valid: true,
    })
    await store.validate()
    expect(store.allRowsValid).toBe(true)

    const [row] = store.rows
    store.updateRow(row!.clientId, { quantity: 5 })

    expect(store.validationStale).toBe(true)
    expect(store.allRowsValid).toBe(false)
  })

  it('allRowsValid is true when every row is matched and validation is fresh', async () => {
    const store = useMadeItemsDemandsBatchDraftStore()
    store.addRow(makeRowInput())
    store.addRow(makeRowInput({ part_number: 'PN-2' }))
    validateBatchMadeItemDemandsMock.mockResolvedValue({
      results: [
        makeResult({ row_index: 0, row_status: 'matched' }),
        makeResult({ row_index: 1, row_status: 'matched' }),
      ],
      all_valid: true,
    })

    await store.validate()

    expect(store.allRowsValid).toBe(true)
  })

  it('warningRowCount counts matched rows with divergences (e.g. inactive/replaced status), blockedRowCount counts non-matched rows', async () => {
    const store = useMadeItemsDemandsBatchDraftStore()
    store.addRow(makeRowInput())
    store.addRow(makeRowInput({ part_number: 'PN-2' }))
    store.addRow(makeRowInput({ part_number: 'PN-3' }))
    validateBatchMadeItemDemandsMock.mockResolvedValue({
      results: [
        makeResult({
          row_index: 0,
          row_status: 'matched',
          divergences: [{ field: 'status', db_value: 'inactive', file_value: null }],
        }),
        makeResult({ row_index: 1, row_status: 'matched', divergences: [] }),
        makeResult({ row_index: 2, row_status: 'not_found' }),
      ],
      all_valid: false,
    })

    await store.validate()

    expect(store.warningRowCount).toBe(1)
    expect(store.blockedRowCount).toBe(1)
  })

  it('commit clears the draft, including for a store freshly reloaded from storage', async () => {
    const store = useMadeItemsDemandsBatchDraftStore()
    store.addRow(makeRowInput())
    validateBatchMadeItemDemandsMock.mockResolvedValue({
      results: [makeResult({ row_status: 'matched' })],
      all_valid: true,
    })
    await store.validate()
    commitBatchMadeItemDemandsMock.mockResolvedValue({ created_demand_ids: [1] })

    await store.commit()

    expect(store.rows).toEqual([])
    expect(store.step).toBe('upload')
    expect(store.hasDraft).toBe(false)

    // discardDraft() removes the storage key synchronously, but the deep
    // persistence watcher it also triggers can re-write an empty-draft
    // snapshot to that same key on the next microtask (see
    // resetOnLogout.ts's clearPersistedDrafts doc comment for the same
    // race), so the real invariant is that a store reloaded afterwards
    // never resurrects the committed rows, not that the key is literally
    // absent at this exact instant.
    setActivePinia(createPinia())
    const reloaded = useMadeItemsDemandsBatchDraftStore()
    expect(reloaded.rows).toEqual([])
    expect(reloaded.hasDraft).toBe(false)
  })

  it('uses the made-item batch draft storage key registered in resetOnLogout', () => {
    expect(BATCH_MADE_ITEM_DEMAND_IMPORT_DRAFT_STORAGE_KEY).toBe(
      'glados.batchMadeItemDemandImport.draft.v1',
    )
  })

  it('ignores malformed persisted state and starts with an empty draft', () => {
    localStorage.setItem(
      BATCH_MADE_ITEM_DEMAND_IMPORT_DRAFT_STORAGE_KEY,
      JSON.stringify({ step: 'not-a-real-step', rows: 'not-an-array' }),
    )
    setActivePinia(createPinia())

    const store = useMadeItemsDemandsBatchDraftStore()

    expect(store.step).toBe('upload')
    expect(store.rows).toEqual([])
  })
})
