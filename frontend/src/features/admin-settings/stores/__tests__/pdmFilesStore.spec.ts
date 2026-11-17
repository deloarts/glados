import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type {
  PdmFileRetryResult,
  PdmFileSnapshot,
  PdmFileSnapshotFilterParams,
} from '../../types/adminSettingsTypes'

const getPdmFilesMock =
  vi.fn<(params?: PdmFileSnapshotFilterParams) => Promise<PageResponse<PdmFileSnapshot>>>()
const retryPdmFileMock = vi.fn<(id: number) => Promise<PdmFileRetryResult>>()
const dismissPdmFileMock = vi.fn<(id: number) => Promise<PdmFileSnapshot>>()

vi.mock('../../api/getPdmFiles', () => ({
  getPdmFiles: (params?: PdmFileSnapshotFilterParams) => getPdmFilesMock(params),
}))
vi.mock('../../api/retryPdmFile', () => ({
  retryPdmFile: (id: number) => retryPdmFileMock(id),
}))
vi.mock('../../api/dismissPdmFile', () => ({
  dismissPdmFile: (id: number) => dismissPdmFileMock(id),
}))

import { usePdmFilesStore } from '../pdmFilesStore'

function makeSnapshot(overrides: Partial<PdmFileSnapshot> = {}): PdmFileSnapshot {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    vault_id: 'vault-guid',
    file_id: 42,
    kind: 'made',
    name: 'bracket.sldprt',
    path: '\\Made-Parts\\bracket.sldprt',
    parent_folder_id: 7,
    version: 3,
    state_id: 2,
    state: 'Released',
    modified_at: '2026-09-01T10:00:00Z',
    first_seen_at: '2026-08-01T10:00:00Z',
    last_seen_at: '2026-09-01T10:05:00Z',
    last_ingested_version: 3,
    sync_state: 'ingested',
    last_error: null,
    part_number: 'PUR-26-00001',
    revision: 'A',
    item_id: 99,
    item_kind: 'made',
    has_parked_payload: false,
    ...overrides,
  }
}

function page(items: PdmFileSnapshot[], total = items.length): PageResponse<PdmFileSnapshot> {
  return { items, total, limit: 25, skip: 0 }
}

describe('pdmFilesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getPdmFilesMock.mockReset()
    retryPdmFileMock.mockReset()
    dismissPdmFileMock.mockReset()
  })

  it('refresh sends skip/limit and populates items/total from the envelope', async () => {
    getPdmFilesMock.mockResolvedValue(page([makeSnapshot()], 7))
    const store = usePdmFilesStore()

    await store.refresh({ skip: 25, limit: 25 })

    expect(getPdmFilesMock).toHaveBeenCalledWith(expect.objectContaining({ skip: 25, limit: 25 }))
    expect(store.items).toHaveLength(1)
    expect(store.total).toBe(7)
  })

  it('folds search/syncState/kind into the request params', async () => {
    getPdmFilesMock.mockResolvedValue(page([]))
    const store = usePdmFilesStore()
    store.search = 'bracket'
    store.syncState = 'conflict'
    store.kind = 'bought'

    await store.refresh({ skip: 0, limit: 25 })

    expect(getPdmFilesMock).toHaveBeenCalledWith(
      expect.objectContaining({ search: 'bracket', sync_state: 'conflict', kind: 'bought' }),
    )
  })

  it('omits unset filters from the request params', async () => {
    getPdmFilesMock.mockResolvedValue(page([]))
    const store = usePdmFilesStore()

    await store.refresh()

    expect(getPdmFilesMock).toHaveBeenCalledWith({})
  })

  it('hasActiveFilters reflects search/syncState/kind', () => {
    const store = usePdmFilesStore()
    expect(store.hasActiveFilters).toBe(false)

    store.search = 'x'
    expect(store.hasActiveFilters).toBe(true)

    store.clearAll()
    expect(store.hasActiveFilters).toBe(false)

    store.syncState = 'missing'
    expect(store.hasActiveFilters).toBe(true)

    store.clearAll()
    store.kind = 'made'
    expect(store.hasActiveFilters).toBe(true)
  })

  it('retry calls the API and optimistically flips the row to pending', async () => {
    getPdmFilesMock.mockResolvedValue(page([makeSnapshot({ id: 5, sync_state: 'error' })]))
    retryPdmFileMock.mockResolvedValue({ accepted: true })
    const store = usePdmFilesStore()
    await store.refresh()

    await store.retry(5)

    expect(retryPdmFileMock).toHaveBeenCalledWith(5)
    expect(store.items[0]?.sync_state).toBe('pending')
  })

  it('dismiss calls the API and replaces the row with the server response', async () => {
    getPdmFilesMock.mockResolvedValue(page([makeSnapshot({ id: 6, sync_state: 'conflict' })]))
    const dismissed = makeSnapshot({
      id: 6,
      sync_state: 'skipped',
      last_error: 'dismissed by tester',
      has_parked_payload: false,
    })
    dismissPdmFileMock.mockResolvedValue(dismissed)
    const store = usePdmFilesStore()
    await store.refresh()

    await store.dismiss(6)

    expect(dismissPdmFileMock).toHaveBeenCalledWith(6)
    expect(store.items[0]).toEqual(dismissed)
  })
})
