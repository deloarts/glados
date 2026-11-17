import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type {
  PdmReconciliationFinding,
  PdmReconciliationFindingFilterParams,
} from '../../types/adminSettingsTypes'

const getPdmReconciliationFindingsMock =
  vi.fn<
    (params?: PdmReconciliationFindingFilterParams) => Promise<PageResponse<PdmReconciliationFinding>>
  >()

vi.mock('../../api/getPdmReconciliation', () => ({
  getPdmReconciliation: vi.fn<() => Promise<unknown>>(),
}))
vi.mock('../../api/getPdmReconciliationFindings', () => ({
  getPdmReconciliationFindings: (params?: PdmReconciliationFindingFilterParams) =>
    getPdmReconciliationFindingsMock(params),
}))
vi.mock('../../api/requestPdmReconciliation', () => ({
  requestPdmReconciliation: vi.fn<() => Promise<unknown>>(),
}))

import { usePdmReconciliationStore } from '../pdmReconciliationStore'

describe('pdmReconciliationStore column filters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getPdmReconciliationFindingsMock.mockReset()
    getPdmReconciliationFindingsMock.mockResolvedValue({ items: [], total: 0, limit: 25, skip: 0 })
  })

  it('sends the part number and message filters as their own params', async () => {
    const store = usePdmReconciliationStore()
    store.partNumber = ' PUR-26 '
    store.message = 'behind'

    await store.loadFindings({ skip: 0, limit: 25 })

    expect(getPdmReconciliationFindingsMock).toHaveBeenCalledWith({
      part_number: 'PUR-26',
      message: 'behind',
      skip: 0,
      limit: 25,
    })
  })

  it('leaves empty column filters out of the request', async () => {
    const store = usePdmReconciliationStore()
    store.partNumber = '   '

    await store.loadFindings({ skip: 0, limit: 25 })

    expect(getPdmReconciliationFindingsMock).toHaveBeenCalledWith({ skip: 0, limit: 25 })
  })
})
