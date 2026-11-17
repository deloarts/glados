import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type {
  PdmSyncRun,
  PdmSyncRunEntry,
  PdmSyncRunEntryFilterParams,
  PdmSyncRunFilterParams,
} from '../../types/adminSettingsTypes'

const getPdmSyncRunsMock =
  vi.fn<(params?: PdmSyncRunFilterParams) => Promise<PageResponse<PdmSyncRun>>>()
const getPdmSyncRunEntriesMock =
  vi.fn<
    (runId: number, params?: PdmSyncRunEntryFilterParams) => Promise<PageResponse<PdmSyncRunEntry>>
  >()

vi.mock('../../api/getPdmSyncRuns', () => ({
  getPdmSyncRuns: (params?: PdmSyncRunFilterParams) => getPdmSyncRunsMock(params),
}))
vi.mock('../../api/getPdmSyncRunEntries', () => ({
  getPdmSyncRunEntries: (runId: number, params?: PdmSyncRunEntryFilterParams) =>
    getPdmSyncRunEntriesMock(runId, params),
}))

import { usePdmSyncLogStore } from '../pdmSyncLogStore'

function makeRun(overrides: Partial<PdmSyncRun> = {}): PdmSyncRun {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    started_at: '2026-09-01T10:00:00Z',
    finished_at: '2026-09-01T10:00:05Z',
    trigger: 'scheduled',
    files_seen: 12,
    changed: 3,
    ingested: 2,
    skipped: 8,
    conflicts: 1,
    errors: 0,
    missing: 0,
    error: null,
    summary: '12 files checked, 2 ingested.',
    folders_walked: 4,
    folders_skipped_cold: 0,
    phase: null,
    current_path: null,
    files_queued: 0,
    files_processed: 0,
    progress_at: null,
    ...overrides,
  }
}

function makeEntry(overrides: Partial<PdmSyncRunEntry> = {}): PdmSyncRunEntry {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    run_id: 1,
    vault_id: 'vault-guid',
    file_id: 42,
    name: 'bracket.sldprt',
    path: '\\Made-Parts\\bracket.sldprt',
    kind: 'made',
    action: 'created',
    item_id: 99,
    message: 'Item created',
    created_at: '2026-09-01T10:00:02Z',
    ...overrides,
  }
}

function page<T>(items: T[], total = items.length): PageResponse<T> {
  return { items, total, limit: 25, skip: 0 }
}

describe('pdmSyncLogStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getPdmSyncRunsMock.mockReset()
    getPdmSyncRunEntriesMock.mockReset()
  })

  it('refresh sends skip/limit and populates runs/total from the envelope', async () => {
    getPdmSyncRunsMock.mockResolvedValue(page([makeRun()], 5))
    const store = usePdmSyncLogStore()

    await store.refresh({ skip: 25, limit: 25 })

    expect(getPdmSyncRunsMock).toHaveBeenCalledWith({ skip: 25, limit: 25 })
    expect(store.runs).toHaveLength(1)
    expect(store.total).toBe(5)
  })

  it('refresh with no page argument calls the API with no params', async () => {
    getPdmSyncRunsMock.mockResolvedValue(page([]))
    const store = usePdmSyncLogStore()

    await store.refresh()

    expect(getPdmSyncRunsMock).toHaveBeenCalledWith(undefined)
  })

  it('loadEntries fetches entries for the given run and populates entries/entriesTotal', async () => {
    getPdmSyncRunEntriesMock.mockResolvedValue(page([makeEntry()], 3))
    const store = usePdmSyncLogStore()

    await store.loadEntries(1, { skip: 0, limit: 25 })

    expect(getPdmSyncRunEntriesMock).toHaveBeenCalledWith(1, { skip: 0, limit: 25 })
    expect(store.entries).toHaveLength(1)
    expect(store.entriesTotal).toBe(3)
  })

  it('folds the action filter into the entries request when set', async () => {
    getPdmSyncRunEntriesMock.mockResolvedValue(page([]))
    const store = usePdmSyncLogStore()
    store.action = 'conflict'

    await store.loadEntries(1, { skip: 0, limit: 25 })

    expect(getPdmSyncRunEntriesMock).toHaveBeenCalledWith(1, {
      action: 'conflict',
      skip: 0,
      limit: 25,
    })
  })

  it('omits the action filter from the request when unset', async () => {
    getPdmSyncRunEntriesMock.mockResolvedValue(page([]))
    const store = usePdmSyncLogStore()

    await store.loadEntries(1)

    expect(getPdmSyncRunEntriesMock).toHaveBeenCalledWith(1, {})
  })

  it('loadEntries does not touch selectedRunId - the caller owns selection', async () => {
    getPdmSyncRunEntriesMock.mockResolvedValue(page([makeEntry()]))
    const store = usePdmSyncLogStore()
    store.selectedRunId = 7

    await store.loadEntries(1)

    expect(store.selectedRunId).toBe(7)
  })

  it('clearSelection resets selectedRunId and the entries list', async () => {
    getPdmSyncRunEntriesMock.mockResolvedValue(page([makeEntry()], 3))
    const store = usePdmSyncLogStore()
    store.selectedRunId = 1
    await store.loadEntries(1)
    expect(store.entries).toHaveLength(1)

    store.clearSelection()

    expect(store.selectedRunId).toBeNull()
    expect(store.entries).toHaveLength(0)
    expect(store.entriesTotal).toBe(0)
  })
})
