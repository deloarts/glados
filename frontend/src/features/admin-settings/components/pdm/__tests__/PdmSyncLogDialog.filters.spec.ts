import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'

import type { PageResponse } from '@/core/api/types'
import type {
  PdmSyncRun,
  PdmSyncRunEntry,
  PdmSyncRunEntryFilterParams,
  PdmSyncRunFilterParams,
} from '../../../types/adminSettingsTypes'

const getPdmSyncRunsMock =
  vi.fn<(params?: PdmSyncRunFilterParams) => Promise<PageResponse<PdmSyncRun>>>()
const getPdmSyncRunEntriesMock =
  vi.fn<
    (runId: number, params?: PdmSyncRunEntryFilterParams) => Promise<PageResponse<PdmSyncRunEntry>>
  >()

vi.mock('../../../api/getPdmSyncRuns', () => ({
  getPdmSyncRuns: (params?: PdmSyncRunFilterParams) => getPdmSyncRunsMock(params),
}))
vi.mock('../../../api/getPdmSyncRunEntries', () => ({
  getPdmSyncRunEntries: (runId: number, params?: PdmSyncRunEntryFilterParams) =>
    getPdmSyncRunEntriesMock(runId, params),
}))

import PdmSyncLogDialog from '../PdmSyncLogDialog.vue'
import { usePdmSyncLogStore } from '../../../stores/pdmSyncLogStore'

const EMPTY_PAGE = { items: [], total: 0, limit: 25, skip: 0 }

async function mountDialog() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(PdmSyncLogDialog, {
    props: { visible: true },
    pinia,
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

describe('PdmSyncLogDialog row filters', () => {
  beforeEach(() => {
    getPdmSyncRunsMock.mockReset()
    getPdmSyncRunEntriesMock.mockReset()
    getPdmSyncRunsMock.mockResolvedValue(EMPTY_PAGE)
    getPdmSyncRunEntriesMock.mockResolvedValue(EMPTY_PAGE)
    document.body.innerHTML = ''
  })

  it('shows both tables with a filter row', async () => {
    const wrapper = await mountDialog()

    const tables = wrapper.findAllComponents({ name: 'DataTable' })
    expect(tables.map((table) => table.props('filterDisplay'))).toEqual(['row', 'row'])

    wrapper.unmount()
  })

  it('refetches the runs from page one with the picked triggers', async () => {
    const wrapper = await mountDialog()
    getPdmSyncRunsMock.mockClear()

    await wrapper.findComponent({ name: 'MultiSelect' }).vm.$emit('update:modelValue', ['retry'])
    await flushPromises()

    expect(getPdmSyncRunsMock).toHaveBeenCalledWith({ skip: 0, limit: 25, trigger: ['retry'] })

    wrapper.unmount()
  })

  it('refetches the selected run entries with the picked kind', async () => {
    const wrapper = await mountDialog()
    usePdmSyncLogStore().selectedRunId = 4
    getPdmSyncRunEntriesMock.mockClear()

    // The first Select is the action filter, the second the kind filter.
    await wrapper.findAllComponents({ name: 'Select' })[1]!.vm.$emit('update:modelValue', 'document')
    await flushPromises()

    expect(getPdmSyncRunEntriesMock).toHaveBeenCalledWith(4, { kind: 'document', skip: 0, limit: 25 })

    wrapper.unmount()
  })
})
