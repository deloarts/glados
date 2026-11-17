import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type {
  PdmReconciliationFinding,
  PdmReconciliationFindingFilterParams,
  PdmReconciliationSummary,
  PdmReconcileResult,
  PdmSyncRun,
} from '../../types/adminSettingsTypes'

const getPdmReconciliationMock = vi.fn<() => Promise<PdmReconciliationSummary>>()
const getPdmReconciliationFindingsMock =
  vi.fn<
    (params?: PdmReconciliationFindingFilterParams) => Promise<PageResponse<PdmReconciliationFinding>>
  >()
const requestPdmReconciliationMock = vi.fn<(deep: boolean) => Promise<PdmReconcileResult>>()

vi.mock('../../api/getPdmReconciliation', () => ({
  getPdmReconciliation: () => getPdmReconciliationMock(),
}))
vi.mock('../../api/getPdmReconciliationFindings', () => ({
  getPdmReconciliationFindings: (params?: PdmReconciliationFindingFilterParams) =>
    getPdmReconciliationFindingsMock(params),
}))
vi.mock('../../api/requestPdmReconciliation', () => ({
  requestPdmReconciliation: (deep: boolean) => requestPdmReconciliationMock(deep),
}))

import { usePdmReconciliationStore } from '../pdmReconciliationStore'

function makeRun(overrides: Partial<PdmSyncRun> = {}): PdmSyncRun {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    started_at: '2026-09-04T10:00:00Z',
    finished_at: '2026-09-04T10:00:05Z',
    trigger: 'reconciliation',
    files_seen: 0,
    changed: 0,
    ingested: 0,
    skipped: 0,
    conflicts: 0,
    errors: 0,
    missing: 0,
    error: null,
    summary: null,
    folders_walked: 0,
    folders_skipped_cold: 0,
    phase: null,
    current_path: null,
    files_queued: 0,
    files_processed: 0,
    progress_at: null,
    ...overrides,
  }
}

function makeFinding(overrides: Partial<PdmReconciliationFinding> = {}): PdmReconciliationFinding {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    run_id: 1,
    category: 'stuck_file',
    severity: 'warning',
    kind: 'made',
    item_id: 99,
    file_id: 42,
    part_number: 'PUR-26-00001',
    revision: 'A',
    message: 'File has not been ingested for 9 days.',
    count: 1,
    created_at: '2026-09-04T10:00:03Z',
    ...overrides,
  }
}

function page<T>(items: T[], total = items.length): PageResponse<T> {
  return { items, total, limit: 25, skip: 0 }
}

describe('pdmReconciliationStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getPdmReconciliationMock.mockReset()
    getPdmReconciliationFindingsMock.mockReset()
    requestPdmReconciliationMock.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('loadSummary populates run/counts from the envelope', async () => {
    getPdmReconciliationMock.mockResolvedValue({
      run: makeRun(),
      counts: { stuck_file: 3, orphaned_cad_row: 0 },
    })
    const store = usePdmReconciliationStore()

    await store.loadSummary()

    expect(store.run?.id).toBe(1)
    expect(store.counts).toEqual({ stuck_file: 3, orphaned_cad_row: 0 })
  })

  it('loadSummary reschedules itself every 5s while the run is still open, and stops once it finishes', async () => {
    vi.useFakeTimers()
    getPdmReconciliationMock.mockResolvedValue({
      run: makeRun({ finished_at: null }),
      counts: {},
    })
    const store = usePdmReconciliationStore()

    await store.loadSummary()
    expect(getPdmReconciliationMock).toHaveBeenCalledTimes(1)

    // Next poll tick still finds the run open, fires again on its own.
    await vi.advanceTimersByTimeAsync(5000)
    expect(getPdmReconciliationMock).toHaveBeenCalledTimes(2)

    // The run finishes on this tick's response, no further polling.
    getPdmReconciliationMock.mockResolvedValue({
      run: makeRun({ finished_at: '2026-09-04T10:00:10Z' }),
      counts: { stuck_file: 1 },
    })
    await vi.advanceTimersByTimeAsync(5000)
    expect(getPdmReconciliationMock).toHaveBeenCalledTimes(3)

    await vi.advanceTimersByTimeAsync(15000)
    expect(getPdmReconciliationMock).toHaveBeenCalledTimes(3)
  })

  it('does not schedule polling when the report has never run', async () => {
    vi.useFakeTimers()
    getPdmReconciliationMock.mockResolvedValue({ run: null, counts: {} })
    const store = usePdmReconciliationStore()

    await store.loadSummary()
    await vi.advanceTimersByTimeAsync(15000)

    expect(getPdmReconciliationMock).toHaveBeenCalledTimes(1)
  })

  it('stopPolling cancels a pending scheduled refresh', async () => {
    vi.useFakeTimers()
    getPdmReconciliationMock.mockResolvedValue({ run: makeRun({ finished_at: null }), counts: {} })
    const store = usePdmReconciliationStore()

    await store.loadSummary()
    store.stopPolling()
    await vi.advanceTimersByTimeAsync(15000)

    expect(getPdmReconciliationMock).toHaveBeenCalledTimes(1)
  })

  it('requestRun queues the run and reloads the summary, tracking requesting', async () => {
    requestPdmReconciliationMock.mockResolvedValue({ accepted: true })
    getPdmReconciliationMock.mockResolvedValue({ run: makeRun({ finished_at: null }), counts: {} })
    const store = usePdmReconciliationStore()

    const promise = store.requestRun(true)
    expect(store.requesting).toBe(true)
    await promise

    expect(requestPdmReconciliationMock).toHaveBeenCalledWith(true)
    expect(getPdmReconciliationMock).toHaveBeenCalledTimes(1)
    expect(store.requesting).toBe(false)
    expect(store.run?.finished_at).toBeNull()
  })

  it('requestRun clears requesting even when the request rejects', async () => {
    requestPdmReconciliationMock.mockRejectedValue(new Error('nope'))
    const store = usePdmReconciliationStore()

    await expect(store.requestRun(false)).rejects.toThrow('nope')

    expect(store.requesting).toBe(false)
  })

  it('loadFindings sends skip/limit and populates findings/findingsTotal', async () => {
    getPdmReconciliationFindingsMock.mockResolvedValue(page([makeFinding()], 4))
    const store = usePdmReconciliationStore()

    await store.loadFindings({ skip: 25, limit: 25 })

    expect(getPdmReconciliationFindingsMock).toHaveBeenCalledWith(
      expect.objectContaining({ skip: 25, limit: 25 }),
    )
    expect(store.findings).toHaveLength(1)
    expect(store.findingsTotal).toBe(4)
  })

  it('folds category/kind/search into the findings request', async () => {
    getPdmReconciliationFindingsMock.mockResolvedValue(page([]))
    const store = usePdmReconciliationStore()
    store.category = 'duplicate_part_number'
    store.kind = 'bought'
    store.search = 'PUR-26'

    await store.loadFindings()

    expect(getPdmReconciliationFindingsMock).toHaveBeenCalledWith({
      category: 'duplicate_part_number',
      kind: 'bought',
      search: 'PUR-26',
    })
  })

  it('omits unset findings filters from the request', async () => {
    getPdmReconciliationFindingsMock.mockResolvedValue(page([]))
    const store = usePdmReconciliationStore()

    await store.loadFindings()

    expect(getPdmReconciliationFindingsMock).toHaveBeenCalledWith({})
  })
})
