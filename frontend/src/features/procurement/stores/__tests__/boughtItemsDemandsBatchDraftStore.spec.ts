import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY } from '@/core/stores/resetOnLogout'


const validateBatchDemandsMock =
  vi.fn<(payload: ValidateBatchDemandsRequest) => Promise<ValidateBatchDemandsResponse>>()
const commitBatchDemandsMock =
  vi.fn<(payload: CommitBatchDemandsRequest) => Promise<CommitBatchDemandsResponse>>()

vi.mock('@/features/bought-items/api/boughtItemDemandsApi', () => ({
  validateBatchDemands: (payload: ValidateBatchDemandsRequest) =>
    validateBatchDemandsMock(payload),
  commitBatchDemands: (payload: CommitBatchDemandsRequest) => commitBatchDemandsMock(payload),
}))

import { useBoughtItemsDemandsBatchDraftStore } from '../boughtItemsDemandsBatchDraftStore'
import type {
  BatchDemandRowInput,
  CommitBatchDemandsRequest,
  CommitBatchDemandsResponse,
  RowValidationResult,
  ValidateBatchDemandsRequest,
  ValidateBatchDemandsResponse,
} from '@/features/bought-items'

function makeRowInput(overrides: Partial<BatchDemandRowInput> = {}): BatchDemandRowInput {
  return {
    row_index: 0,
    project_number: 'PRJ-001',
    quantity: 1,
    unit: 'pcs',
    part_number: 'PN-1',
    article_name: 'Widget',
    order_code: null,
    manufacturer_name: null,
    desired_delivery_date: null,
    note: null,
    ...overrides,
  }
}

function makeResult(overrides: Partial<RowValidationResult> = {}): RowValidationResult {
  return {
    row_index: 0,
    row_status: 'matched',
    match_source: 'part_number',
    matched_item: null,
    divergences: [],
    resolved_project_id: 1,
    errors: [],
    ...overrides,
  }
}

describe('useBoughtItemsDemandsBatchDraftStore', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    validateBatchDemandsMock.mockReset()
    commitBatchDemandsMock.mockReset()
  })

  it('allRowsValid is false when a row is not_found/ambiguous/unresolved/invalid', async () => {
    for (const status of ['not_found', 'ambiguous', 'unresolved_reference', 'invalid'] as const) {
      setActivePinia(createPinia())
      const store = useBoughtItemsDemandsBatchDraftStore()
      store.addRow(makeRowInput())
      validateBatchDemandsMock.mockResolvedValue({
        results: [makeResult({ row_status: status })],
        all_valid: false,
      })

      await store.validate()

      expect(store.allRowsValid).toBe(false)
    }
  })

  it('allRowsValid is false when the draft is stale after updateRow', async () => {
    const store = useBoughtItemsDemandsBatchDraftStore()
    store.addRow(makeRowInput())
    validateBatchDemandsMock.mockResolvedValue({
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
    const store = useBoughtItemsDemandsBatchDraftStore()
    store.addRow(makeRowInput())
    store.addRow(makeRowInput({ part_number: 'PN-2' }))
    validateBatchDemandsMock.mockResolvedValue({
      results: [
        makeResult({ row_index: 0, row_status: 'matched' }),
        makeResult({ row_index: 1, row_status: 'matched' }),
      ],
      all_valid: true,
    })

    await store.validate()

    expect(store.allRowsValid).toBe(true)
  })

  it('warningRowCount counts matched rows with divergences, blockedRowCount counts non-matched rows', async () => {
    const store = useBoughtItemsDemandsBatchDraftStore()
    store.addRow(makeRowInput())
    store.addRow(makeRowInput({ part_number: 'PN-2' }))
    store.addRow(makeRowInput({ part_number: 'PN-3' }))
    validateBatchDemandsMock.mockResolvedValue({
      results: [
        makeResult({
          row_index: 0,
          row_status: 'matched',
          divergences: [{ field: 'article_name', db_value: 'DB Name', file_value: 'File Name' }],
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
    const store = useBoughtItemsDemandsBatchDraftStore()
    store.addRow(makeRowInput())
    validateBatchDemandsMock.mockResolvedValue({
      results: [makeResult({ row_status: 'matched' })],
      all_valid: true,
    })
    await store.validate()
    commitBatchDemandsMock.mockResolvedValue({ created_demand_ids: [1] })

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
    const reloaded = useBoughtItemsDemandsBatchDraftStore()
    expect(reloaded.rows).toEqual([])
    expect(reloaded.hasDraft).toBe(false)
  })

  it('uses the v2 storage key', () => {
    expect(BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY).toBe('glados.batchDemandImport.draft.v2')
  })

  it('ignores malformed persisted state and starts with an empty draft', () => {
    localStorage.setItem(
      BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY,
      JSON.stringify({ step: 'not-a-real-step', rows: 'not-an-array' }),
    )
    setActivePinia(createPinia())

    const store = useBoughtItemsDemandsBatchDraftStore()

    expect(store.step).toBe('upload')
    expect(store.rows).toEqual([])
  })

  it('ignores an old v1-shaped draft with a rows object instead of an array', () => {
    localStorage.setItem(
      BATCH_DEMAND_IMPORT_DRAFT_STORAGE_KEY,
      JSON.stringify({ step: 'review', rows: { foo: 'bar' } }),
    )
    setActivePinia(createPinia())

    const store = useBoughtItemsDemandsBatchDraftStore()

    expect(store.step).toBe('upload')
    expect(store.rows).toEqual([])
  })
})
