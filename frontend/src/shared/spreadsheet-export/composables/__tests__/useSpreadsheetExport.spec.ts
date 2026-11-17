import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { answerConfirmations } from '@/test-utils/confirmations'
import SpreadsheetExportButton from '../../components/SpreadsheetExportButton.vue'
import { EXPORT_CONFIRM_ROWS, EXPORT_MAX_ROWS } from '../../utils/fetchExportRows'
import { useSpreadsheetExport, type SpreadsheetExportSource } from '../useSpreadsheetExport'

import type { PageResponse } from '@/core/api/types'
import type { PageWindow } from '@/core/api/fetchAllPages'
import type { WorksheetData } from '../../utils/buildWorksheet'
import type { SpreadsheetFormat } from '../../types/spreadsheetExport'

const { writeMock, warnMock, errorMock } = vi.hoisted(() => ({
  writeMock: vi.fn<(worksheet: WorksheetData, format: SpreadsheetFormat) => Promise<void>>(),
  warnMock: vi.fn<(summary: string, detail?: string) => void>(),
  errorMock: vi.fn<(summary: string, detail?: string) => void>(),
}))

vi.mock('../../utils/writeSpreadsheet', () => ({ writeSpreadsheetFile: writeMock }))
vi.mock('@/core/composables/useAppToast', () => ({
  useAppToast: () => ({
    warn: warnMock,
    error: errorMock,
    info: vi.fn<(summary: string, detail?: string) => void>(),
    success: vi.fn<(summary: string, detail?: string) => void>(),
  }),
}))

interface Row {
  id: number
}

type FetchPage = (window: PageWindow, signal: AbortSignal) => Promise<PageResponse<Row>>

function listOf(total: number): FetchPage {
  return async ({ skip, limit }) => ({
    items: Array.from({ length: Math.max(0, Math.min(limit, total - skip)) }, (_, i) => ({ id: skip + i + 1 })),
    total,
    skip,
    limit,
  })
}

function mountExport(options: { total: number; selected?: Row[]; fetchPage?: FetchPage }) {
  const fetchPage = vi.fn<FetchPage>(options.fetchPage ?? listOf(options.total))
  const source: SpreadsheetExportSource<Row> = {
    total: () => options.total,
    selected: () => options.selected ?? [],
    fetchPage,
    columns: () => [{ header: 'ID', value: (row) => row.id }],
    format: () => ({ sheetName: 'Rows', filename: 'rows.xlsx' }),
  }
  const Host = defineComponent({
    setup() {
      const exporter = useSpreadsheetExport(source)
      return () =>
        h(SpreadsheetExportButton, {
          total: options.total,
          selectedCount: options.selected?.length ?? 0,
          exporting: exporter.exporting.value,
          loaded: exporter.loaded.value,
          exportTotal: exporter.total.value,
          onExport: (scope: 'filtered' | 'selected') => void exporter.run(scope),
          onCancel: () => exporter.cancel(),
        })
    },
  })
  return { wrapper: mountWithApp(Host), fetchPage }
}

function writtenIds(): unknown[] {
  const worksheet = writeMock.mock.calls[0]?.[0]
  if (!worksheet) return []
  return Object.entries(worksheet.cells)
    .filter(([address]) => address.startsWith('A') && address !== 'A1')
    .map(([, cell]) => cell.v)
}

describe('useSpreadsheetExport with SpreadsheetExportButton', () => {
  let confirmations: ReturnType<typeof answerConfirmations> | null = null

  beforeEach(() => {
    writeMock.mockResolvedValue(undefined)
  })

  afterEach(() => {
    confirmations?.stop()
    confirmations = null
  })

  it('exports every row of the filter on a click, without asking below the threshold', async () => {
    confirmations = answerConfirmations('accept')
    const { wrapper } = mountExport({ total: 3 })

    await wrapper.get('[data-testid="spreadsheet-export"]').trigger('click')
    await flushPromises()

    expect(confirmations.asked).toHaveLength(0)
    expect(writtenIds()).toEqual([1, 2, 3])
    expect(writeMock.mock.calls[0]?.[1]).toEqual({ sheetName: 'Rows', filename: 'rows.xlsx' })
  })

  it('asks before a large export and reads nothing when the user declines', async () => {
    confirmations = answerConfirmations('reject')
    const { wrapper, fetchPage } = mountExport({ total: EXPORT_CONFIRM_ROWS + 1 })

    await wrapper.get('[data-testid="spreadsheet-export"]').trigger('click')
    await flushPromises()

    expect(confirmations.asked).toHaveLength(1)
    expect(fetchPage).not.toHaveBeenCalled()
    expect(writeMock).not.toHaveBeenCalled()
  })

  it('exports a large filter once the user confirms', async () => {
    confirmations = answerConfirmations('accept')
    const { wrapper } = mountExport({ total: EXPORT_CONFIRM_ROWS + 1 })

    await wrapper.get('[data-testid="spreadsheet-export"]').trigger('click')
    await flushPromises()

    expect(writtenIds()).toHaveLength(EXPORT_CONFIRM_ROWS + 1)
  })

  it('refuses a filter above the cap with a warning and reads nothing', async () => {
    const { wrapper, fetchPage } = mountExport({ total: EXPORT_MAX_ROWS + 1 })

    await wrapper.get('[data-testid="spreadsheet-export"]').trigger('click')
    await flushPromises()

    expect(warnMock).toHaveBeenCalledTimes(1)
    expect(fetchPage).not.toHaveBeenCalled()
  })

  it('shows the progress while it reads and downloads nothing once cancelled', async () => {
    let releasePage: () => void = () => {}
    const fetchPage: FetchPage = (window, signal) =>
      new Promise((resolve, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
        releasePage = () => void listOf(3)(window, signal).then(resolve)
      })
    const { wrapper } = mountExport({ total: 3, fetchPage })

    await wrapper.get('[data-testid="spreadsheet-export"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="spreadsheet-export-progress"]').text()).toContain('0 of 3')
    await wrapper.get('[data-testid="spreadsheet-export-cancel"]').trigger('click')
    await flushPromises()
    releasePage()
    await flushPromises()

    expect(writeMock).not.toHaveBeenCalled()
    expect(errorMock).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="spreadsheet-export"]').exists()).toBe(true)
  })

  it('shows an error toast when a page fails to load', async () => {
    const { wrapper } = mountExport({
      total: 3,
      fetchPage: () => Promise.reject(new Error('Network down')),
    })

    await wrapper.get('[data-testid="spreadsheet-export"]').trigger('click')
    await flushPromises()

    expect(errorMock).toHaveBeenCalledTimes(1)
    expect(writeMock).not.toHaveBeenCalled()
  })

  it('exports the checked rows from the menu without reading the list', async () => {
    const { wrapper, fetchPage } = mountExport({ total: 40, selected: [{ id: 7 }, { id: 9 }] })

    await wrapper.get('[data-testid="spreadsheet-export-menu"]').trigger('click')
    await flushPromises()
    const selected = [...document.body.querySelectorAll<HTMLElement>('[role="menuitem"]')].find((item) =>
      item.textContent?.includes('Selected Rows (2)'),
    )
    expect(selected).toBeDefined()
    selected?.querySelector<HTMLElement>('a')?.click()
    await flushPromises()

    expect(fetchPage).not.toHaveBeenCalled()
    expect(writtenIds()).toEqual([7, 9])
    wrapper.unmount()
  })

  it('shows a plain button without the menu for a table without row selection', async () => {
    const wrapper = mountWithApp(SpreadsheetExportButton, {
      props: { total: 4, exporting: false, loaded: 0, exportTotal: 0 },
    })

    expect(wrapper.find('[data-testid="spreadsheet-export-menu"]').exists()).toBe(false)
    await wrapper.get('[data-testid="spreadsheet-export"]').trigger('click')
    expect(wrapper.emitted('export')).toEqual([['filtered']])
  })

  it('disables the button when the filter matches no rows', () => {
    const { wrapper } = mountExport({ total: 0 })

    expect(wrapper.get('[data-testid="spreadsheet-export"]').attributes('disabled')).toBeDefined()
  })
})
