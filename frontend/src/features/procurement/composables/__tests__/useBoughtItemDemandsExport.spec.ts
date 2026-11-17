import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeDemandItemResponse } from '@/test-utils/factories'
import { useBoughtItemsDemandsStore } from '@/features/bought-items'
import { useBoughtItemsDemandsFiltersStore } from '../../stores/boughtItemsDemandsFiltersStore'
import { useBoughtItemsProcurementStore } from '../../stores/boughtItemsProcurementStore'
import { useBoughtItemDemandsExport } from '../useBoughtItemDemandsExport'

import type { WorksheetData } from '@/shared/spreadsheet-export/utils/buildWorksheet'
import type { SpreadsheetFormat } from '@/shared/spreadsheet-export'

const { getDemandsMock, writeMock } = vi.hoisted(() => ({
  getDemandsMock: vi.fn<(params?: Record<string, unknown>, config?: { signal?: AbortSignal }) => Promise<unknown>>(),
  writeMock: vi.fn<(worksheet: WorksheetData, format: SpreadsheetFormat) => Promise<void>>(),
}))

vi.mock('@/features/bought-items', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/bought-items')>()),
  getDemands: getDemandsMock,
}))
vi.mock('@/shared/spreadsheet-export/utils/writeSpreadsheet', () => ({ writeSpreadsheetFile: writeMock }))

let pinia: ReturnType<typeof createPinia>

function mountExport() {
  let exporter: ReturnType<typeof useBoughtItemDemandsExport> | undefined
  const Host = defineComponent({
    setup() {
      exporter = useBoughtItemDemandsExport()
      return () => h('div')
    },
  })
  mountWithApp(Host, { pinia })
  return exporter!
}

describe('useBoughtItemDemandsExport', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    writeMock.mockResolvedValue(undefined)
    getDemandsMock.mockImplementation(async (params) => ({
      items: [makeDemandItemResponse({ id: 7 })],
      total: 1,
      skip: Number(params?.skip ?? 0),
      limit: Number(params?.limit ?? 1),
    }))
  })

  it('reads the demands with the table filter and sort and writes them', async () => {
    useBoughtItemsDemandsStore().total = 1
    const filtersStore = useBoughtItemsDemandsFiltersStore()
    filtersStore.search = 'bolt'
    filtersStore.statusFilter = 'open'
    filtersStore.setSort('created', 'desc')

    await mountExport().run('filtered')
    await flushPromises()

    const [params, config] = getDemandsMock.mock.calls[0]!
    expect(params).toMatchObject({
      search: 'bolt',
      status: 'open',
      order_by: 'created',
      order_dir: 'desc',
      skip: 0,
      limit: 500,
    })
    expect(config?.signal).toBeInstanceOf(AbortSignal)
    const [worksheet, format] = writeMock.mock.calls[0]!
    expect(worksheet.cells.A2).toEqual({ t: 'n', v: 7 })
    expect(format.sheetName).toBe('Bought Items Demand')
    expect(format.filename).toMatch(/^bought-items-demand_\d{4}-\d{2}-\d{2}\.xlsx$/)
  })

  it('writes the checked demands without reading the list', async () => {
    useBoughtItemsProcurementStore().selectedDemands = [makeDemandItemResponse({ id: 3 })]

    await mountExport().run('selected')
    await flushPromises()

    expect(getDemandsMock).not.toHaveBeenCalled()
    expect(writeMock.mock.calls[0]?.[0].cells.A2).toEqual({ t: 'n', v: 3 })
  })
})
