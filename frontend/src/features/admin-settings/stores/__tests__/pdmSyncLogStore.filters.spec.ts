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

const EMPTY_PAGE = { items: [], total: 0, limit: 25, skip: 0 }

describe('pdmSyncLogStore row filters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getPdmSyncRunsMock.mockReset()
    getPdmSyncRunEntriesMock.mockReset()
    getPdmSyncRunsMock.mockResolvedValue(EMPTY_PAGE)
    getPdmSyncRunEntriesMock.mockResolvedValue(EMPTY_PAGE)
  })

  it('folds the run filters into the runs request', async () => {
    const store = usePdmSyncLogStore()
    store.triggers = ['scheduled', 'retry']
    store.startedFrom = new Date(2026, 8, 1)
    store.startedTo = new Date(2026, 8, 3)
    store.runError = ' login '

    await store.refresh({ skip: 0, limit: 25 })

    expect(getPdmSyncRunsMock).toHaveBeenCalledWith({
      skip: 0,
      limit: 25,
      trigger: ['scheduled', 'retry'],
      started_from: '2026-09-01',
      started_to: '2026-09-03',
      error: 'login',
    })
  })

  it('sends filters even without a page', async () => {
    const store = usePdmSyncLogStore()
    store.triggers = ['manual']

    await store.refresh()

    expect(getPdmSyncRunsMock).toHaveBeenCalledWith({ trigger: ['manual'] })
  })

  it('folds kind and the file search into the entries request', async () => {
    const store = usePdmSyncLogStore()
    store.kind = 'bought'
    store.search = ' screw '

    await store.loadEntries(7, { skip: 0, limit: 25 })

    expect(getPdmSyncRunEntriesMock).toHaveBeenCalledWith(7, {
      kind: 'bought',
      search: 'screw',
      skip: 0,
      limit: 25,
    })
  })
})
