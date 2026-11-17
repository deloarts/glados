import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderItemResponse, makeOrderResponse } from '@/test-utils/factories'
import { useOrdersFiltersStore } from '../../stores/ordersFiltersStore'
import { useOrdersStore } from '../../stores/ordersStore'
import { useOrdersExport } from '../useOrdersExport'

import type { PageResponse } from '@/core/api/types'
import type { WebRequestConfig } from '@/core/api/webRequest'
import type { OrderFilterParams } from '../../types/ordersRequest'
import type { OrderResponse } from '../../types/ordersResponse'
import type { WorksheetData } from '@/shared/spreadsheet-export/utils/buildWorksheet'
import type { SpreadsheetFormat } from '@/shared/spreadsheet-export'

const { getOrdersMock, writeMock } = vi.hoisted(() => ({
  getOrdersMock:
    vi.fn<(params?: OrderFilterParams, config?: WebRequestConfig) => Promise<PageResponse<OrderResponse>>>(),
  writeMock: vi.fn<(worksheet: WorksheetData, format: SpreadsheetFormat) => Promise<void>>(),
}))

vi.mock('../../api/getOrders', () => ({ getOrders: getOrdersMock }))
vi.mock('@/shared/spreadsheet-export/utils/writeSpreadsheet', () => ({ writeSpreadsheetFile: writeMock }))

let pinia: ReturnType<typeof createPinia>

function mountExport() {
  let exporter: ReturnType<typeof useOrdersExport> | undefined
  const Host = defineComponent({
    setup() {
      exporter = useOrdersExport()
      return () => h('div')
    },
  })
  mountWithApp(Host, { pinia })
  return exporter!
}

describe('useOrdersExport', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    writeMock.mockResolvedValue(undefined)
    getOrdersMock.mockImplementation(async (params) => ({
      items: [
        makeOrderResponse({
          order_number: 'ORD-1',
          items: [makeOrderItemResponse({ id: 1, position: 1 }), makeOrderItemResponse({ id: 2, position: 2 })],
        }),
      ],
      total: 1,
      skip: params?.skip ?? 0,
      limit: params?.limit ?? 1,
    }))
  })

  it('reads the orders with the table filter and sort and writes one row per line', async () => {
    useOrdersStore().total = 1
    const filtersStore = useOrdersFiltersStore()
    filtersStore.search = 'acme'
    filtersStore.hideCanceled = true

    await mountExport().run('filtered')
    await flushPromises()

    const [params, config] = getOrdersMock.mock.calls[0]!
    expect(params).toMatchObject({ search: 'acme', skip: 0, limit: 500 })
    expect(params?.status).not.toContain('canceled')
    expect(config?.signal).toBeInstanceOf(AbortSignal)
    const [worksheet, format] = writeMock.mock.calls[0]!
    expect(worksheet.ref).toMatch(/^A1:[A-Z]+3$/)
    expect(worksheet.cells.A2?.v).toBe('ORD-1')
    expect(worksheet.cells.A3?.v).toBe('ORD-1')
    expect(format.filename).toMatch(/^orders_\d{4}-\d{2}-\d{2}\.xlsx$/)
  })
})
