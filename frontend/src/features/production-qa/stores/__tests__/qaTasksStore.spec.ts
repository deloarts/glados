import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { QaTaskFilterParams, QaTaskResponse } from '../../types/qaTaskResponse'

const getQaTasksMock =
  vi.fn<(params?: QaTaskFilterParams) => Promise<PageResponse<QaTaskResponse>>>()

vi.mock('../../api/getQaTasks', () => ({
  getQaTasks: (params?: QaTaskFilterParams) => getQaTasksMock(params),
}))

import { useQaTasksStore } from '../qaTasksStore'

/**
 * A promise plus its resolve, so a test can control exactly when a given
 * call settles instead of racing on real timers. Mirrors the helper in
 * useSequencedFetch.spec.ts.
 */
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function makeTask(overrides: Partial<QaTaskResponse> = {}): QaTaskResponse {
  return {
    id: 1,
    public_id: '33333333-3333-3333-3333-333333333333',
    production_order_number: 'PO-1',
    status: 'queued',
    priority: 'normal',
    quantity: 10,
    quantity_completed: 0,
    planned_start: null,
    planned_end: null,
    actual_start: null,
    actual_end: null,
    finished_by: null,
    can_start: true,
    conflicts: [],
    inspection_method_id: 1,
    inspection_method_name: { enGB: 'Visual' },
    requires_evidence: false,
    has_evidence: false,
    evidence_files: [],
    lot_position_id: 1,
    lot_position_sequence: 1,
    lot_position_count: 1,
    lot_id: 1,
    lot_number: 'LOT-1',
    lot_status: 'draft',
    made_item_id: 1,
    made_item_part_number: 'PN-1',
    made_item_article_name: 'Bracket',
    made_item_revision: 'A',
    made_item_material: '1.0037',
    project_id: 1,
    project_number: 'P-001',
    project_customer: 'Acme',
    ...overrides,
  }
}

function page(items: QaTaskResponse[]): PageResponse<QaTaskResponse> {
  return { items, total: items.length, limit: null, skip: 0 }
}

describe('qaTasksStore.refresh/fetchTasks, concurrency', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getQaTasksMock.mockReset()
  })

  it('populates tasks/total from a single fetchTasks call', async () => {
    getQaTasksMock.mockResolvedValue(page([makeTask()]))
    const store = useQaTasksStore()

    await store.fetchTasks()

    expect(store.tasks).toHaveLength(1)
    expect(store.total).toBe(1)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('discards a slow response that resolves after a faster, later refresh (last-wins)', async () => {
    const slow = deferred<PageResponse<QaTaskResponse>>()
    const fast = deferred<PageResponse<QaTaskResponse>>()
    getQaTasksMock.mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise)
    const store = useQaTasksStore()

    // Two overlapping live-resync calls, e.g. an SSE event firing a second
    // refresh before the first, slower one has come back.
    const slowCall = store.refresh()
    const fastCall = store.refresh()

    // The second (fast) call resolves first...
    fast.resolve(page([makeTask({ id: 2, production_order_number: 'PO-2' })]))
    await fastCall
    expect(store.tasks.map((t) => t.production_order_number)).toEqual(['PO-2'])
    expect(store.refreshing).toBe(false)

    // ...then the stale first call lands. It must be discarded, not
    // overwrite the later call's result, and must not blank the table.
    slow.resolve(page([makeTask({ id: 1, production_order_number: 'PO-1' })]))
    await slowCall

    expect(store.tasks.map((t) => t.production_order_number)).toEqual(['PO-2'])
    expect(store.total).toBe(1)
    expect(store.refreshing).toBe(false)
    // The unrelated `loading` flag (owned by fetchTasks) must stay untouched
    // by refresh() calls. The two flags are deliberately not collapsed.
    expect(store.loading).toBe(false)
  })

  it('shares sequencing across fetchTasks and refresh, so a later refresh discards an earlier fetchTasks', async () => {
    const slowFetch = deferred<PageResponse<QaTaskResponse>>()
    const fastRefresh = deferred<PageResponse<QaTaskResponse>>()
    getQaTasksMock.mockReturnValueOnce(slowFetch.promise).mockReturnValueOnce(fastRefresh.promise)
    const store = useQaTasksStore()

    const fetchCall = store.fetchTasks({ skip: 0, limit: 20 })
    const refreshCall = store.refresh()

    fastRefresh.resolve(page([makeTask({ id: 2, production_order_number: 'PO-2' })]))
    await refreshCall
    expect(store.tasks.map((t) => t.production_order_number)).toEqual(['PO-2'])

    slowFetch.resolve(page([makeTask({ id: 1, production_order_number: 'PO-1' })]))
    await fetchCall

    expect(store.tasks.map((t) => t.production_order_number)).toEqual(['PO-2'])
    expect(store.loading).toBe(false)
    expect(store.refreshing).toBe(false)
  })
})
