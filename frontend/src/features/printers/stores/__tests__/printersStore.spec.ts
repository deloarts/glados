import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { DataTableFilterMetaData } from 'openvue/datatable'
import type { PrinterFilterParams } from '../../types/printerRequest'
import type { PrinterResponse } from '../../types/printerResponse'

const getPrintersMock =
  vi.fn<(params?: PrinterFilterParams) => Promise<PageResponse<PrinterResponse>>>()
const archivePrinterMock = vi.fn<(id: number) => Promise<PrinterResponse>>()
const restorePrinterMock = vi.fn<(id: number) => Promise<PrinterResponse>>()

vi.mock('../../api/getPrinters', () => ({
  getPrinters: (params?: PrinterFilterParams) => getPrintersMock(params),
}))
vi.mock('../../api/createPrinter', () => ({ createPrinter: vi.fn<() => void>() }))
vi.mock('../../api/updatePrinter', () => ({ updatePrinter: vi.fn<() => void>() }))
vi.mock('../../api/archivePrinter', () => ({
  archivePrinter: (id: number) => archivePrinterMock(id),
}))
vi.mock('../../api/restorePrinter', () => ({
  restorePrinter: (id: number) => restorePrinterMock(id),
}))

import { usePrintersStore } from '../printersStore'

function makePrinter(overrides: Partial<PrinterResponse> = {}): PrinterResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    archived: false,
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    name: 'Zebra ZT230',
    internal_name: 'zebra-zt230',
    kind: 'zpl_label',
    host: '192.0.2.10',
    port: 9100,
    timeout_seconds: 5,
    transport: 'raw',
    ipp_uri_path: '/',
    head_dpi: 300,
    format_convert_factor: 2,
    default_media: null,
    location: null,
    vendor: null,
    model: null,
    firmware: null,
    bought_item_ids: [],
    bought_items: [],
    enabled: true,
    is_default: false,
    note: null,
    creator_id: 1,
    creator_full_name: 'Creator',
    changes: [],
    ...overrides,
  }
}

function page(items: PrinterResponse[], total = items.length): PageResponse<PrinterResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('printersStore - showArchived cycle', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getPrintersMock.mockReset()
    archivePrinterMock.mockReset()
    restorePrinterMock.mockReset()
  })

  it('toggleShowArchived flips state and hasActiveFilters becomes true while it is on', () => {
    const store = usePrintersStore()

    expect(store.showArchived).toBe(false)
    expect(store.hasActiveFilters).toBe(false)

    store.toggleShowArchived()

    expect(store.showArchived).toBe(true)
    expect(store.hasActiveFilters).toBe(true)
  })

  it('clearAll resets showArchived back to false alongside search', () => {
    const store = usePrintersStore()
    store.toggleShowArchived()
    store.search = 'zebra'

    store.clearAll()

    expect(store.showArchived).toBe(false)
    expect(store.search).toBe('')
    expect(store.hasActiveFilters).toBe(false)
  })

  it('archive calls the archive endpoint, updates the item in place, and bumps refreshTrigger', async () => {
    const store = usePrintersStore()
    getPrintersMock.mockResolvedValue(page([makePrinter()], 1))
    await store.refresh()
    archivePrinterMock.mockResolvedValue(makePrinter({ archived: true }))

    await store.archive(1)

    expect(archivePrinterMock).toHaveBeenCalledWith(1)
    expect(store.items[0]!.archived).toBe(true)
    expect(store.refreshTrigger).toBe(1)
  })

  it('restore calls the restore endpoint and updates the item in place', async () => {
    const store = usePrintersStore()
    getPrintersMock.mockResolvedValue(page([makePrinter({ archived: true })], 1))
    await store.refresh()
    restorePrinterMock.mockResolvedValue(makePrinter({ archived: false }))

    await store.restore(1)

    expect(restorePrinterMock).toHaveBeenCalledWith(1)
    expect(store.items[0]!.archived).toBe(false)
    expect(store.refreshTrigger).toBe(1)
  })
})

describe('printersStore row filters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getPrintersMock.mockReset()
  })

  function setFilter(store: ReturnType<typeof usePrintersStore>, field: string, value: unknown): void {
    ;(store.filters[field] as DataTableFilterMetaData).value = value
  }

  it('buildParams maps every column filter to its backend query param', () => {
    const store = usePrintersStore()
    store.search = 'zebra'
    setFilter(store, 'name', 'zt')
    setFilter(store, 'kind', 'zpl_label')
    setFilter(store, 'enabled', true)
    setFilter(store, 'creator_id', 2)

    expect(store.buildParams({ skip: 0, limit: 25 })).toEqual({
      skip: 0,
      limit: 25,
      search: 'zebra',
      name: 'zt',
      kind: 'zpl_label',
      enabled: true,
      creator_id: 2,
    })
  })

  it('an enabled filter of false is sent and counts as active', () => {
    const store = usePrintersStore()
    setFilter(store, 'enabled', false)

    expect(store.hasActiveFilters).toBe(true)
    expect(store.buildParams()).toEqual({ enabled: false })
  })

  it('refresh passes the built params through to the API', async () => {
    getPrintersMock.mockResolvedValue(page([makePrinter()]))
    const store = usePrintersStore()
    setFilter(store, 'kind', 'ipp_document')

    await store.refresh(store.buildParams({ skip: 0, limit: 10 }))

    expect(getPrintersMock).toHaveBeenCalledWith({ skip: 0, limit: 10, kind: 'ipp_document' })
  })

  it('clearAll resets every column filter', () => {
    const store = usePrintersStore()
    setFilter(store, 'name', 'zt')
    setFilter(store, 'enabled', false)
    setFilter(store, 'creator_id', 2)

    store.clearAll()

    expect(store.hasActiveFilters).toBe(false)
    expect(store.buildParams()).toEqual({})
  })
})
