import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeBoughtItemResponse } from '@/test-utils/factories'
import BoughtItemsCatalogueControls from '../../components/BoughtItemsCatalogueControls.vue'
import { useBoughtItemsCatalogueEditStore } from '../../stores/boughtItemsCatalogueEditStore'
import { useBoughtItemsCatalogueFiltersStore } from '../../stores/boughtItemsCatalogueFiltersStore'
import { useBoughtItemsCatalogueViewStore } from '../../stores/boughtItemsCatalogueViewStore'
import { useBoughtItemsStore } from '../../stores/boughtItemsStore'

import type { PageResponse } from '@/core/api/types'
import type { WebRequestConfig } from '@/core/api/webRequest'
import type { BoughtItemFilterParams } from '../../types/boughtItemsRequest'
import type { BoughtItemResponse } from '../../types/boughtItemsResponse'
import type { WorksheetData } from '@/shared/spreadsheet-export/utils/buildWorksheet'
import type { SpreadsheetFormat } from '@/shared/spreadsheet-export'

const { getBoughtItemsMock, writeMock } = vi.hoisted(() => ({
  getBoughtItemsMock:
    vi.fn<(params?: BoughtItemFilterParams, config?: WebRequestConfig) => Promise<PageResponse<BoughtItemResponse>>>(),
  writeMock: vi.fn<(worksheet: WorksheetData, format: SpreadsheetFormat) => Promise<void>>(),
}))

vi.mock('../../api/getBoughtItems', () => ({ getBoughtItems: getBoughtItemsMock }))
vi.mock('@/shared/spreadsheet-export/utils/writeSpreadsheet', () => ({ writeSpreadsheetFile: writeMock }))

const router = createRouter({ history: createMemoryHistory(), routes: [] })

describe('useBoughtItemsCatalogueExport', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    writeMock.mockResolvedValue(undefined)
    getBoughtItemsMock.mockImplementation(async (params) => ({
      items: [makeBoughtItemResponse({ id: 1 }), makeBoughtItemResponse({ id: 2 })],
      total: 2,
      skip: params?.skip ?? 0,
      limit: params?.limit ?? 2,
    }))
  })

  function mountControls() {
    return mountWithApp(BoughtItemsCatalogueControls, { pinia, global: { plugins: [router] } })
  }

  it('reads the rows with the search, archived toggle and sort of the table', async () => {
    useBoughtItemsStore().total = 2
    const filtersStore = useBoughtItemsCatalogueFiltersStore()
    filtersStore.search = 'bolt'
    filtersStore.showArchived = true
    const viewStore = useBoughtItemsCatalogueViewStore()
    viewStore.sortBy = 'article_name'
    viewStore.sortDir = 'desc'

    const wrapper = mountControls()
    await wrapper.get('[data-testid="spreadsheet-export"]').trigger('click')
    await flushPromises()

    expect(getBoughtItemsMock).toHaveBeenCalledTimes(1)
    const [params, config] = getBoughtItemsMock.mock.calls[0]!
    expect(params).toMatchObject({
      search: 'bolt',
      include_archived: true,
      order_by: 'article_name',
      order_dir: 'desc',
      skip: 0,
      limit: 500,
    })
    expect(config?.signal).toBeInstanceOf(AbortSignal)
    expect(writeMock).toHaveBeenCalledTimes(1)
    expect(writeMock.mock.calls[0]?.[1].filename).toMatch(/^bought-items_\d{4}-\d{2}-\d{2}\.xlsx$/)
    expect(writeMock.mock.calls[0]?.[1].sheetName).toBe('Bought Items')
  })

  it('offers the checked rows in the export menu', async () => {
    useBoughtItemsStore().total = 10
    useBoughtItemsCatalogueEditStore().selectedItems = [makeBoughtItemResponse({ id: 5 })]

    const wrapper = mountControls()
    await wrapper.get('[data-testid="spreadsheet-export-menu"]').trigger('click')
    await flushPromises()

    const labels = [...document.body.querySelectorAll('[role="menuitem"]')].map((item) => item.textContent?.trim())
    expect(labels).toContain('Selected Rows (1)')
    expect(labels).toContain('All Filtered Rows (10)')
    wrapper.unmount()
  })
})
