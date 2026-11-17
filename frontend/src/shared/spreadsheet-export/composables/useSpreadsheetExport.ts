import { ref, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { getDisplayTimezone } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { useConfirmAsync } from '@/shared/composables/useConfirmAsync'

import type { PageResponse } from '@/core/api/types'
import type { PageWindow } from '@/core/api/fetchAllPages'
import type {
  SpreadsheetColumn,
  SpreadsheetExportScope,
  SpreadsheetFormat,
} from '../types/spreadsheetExport'
import { buildWorksheet } from '../utils/buildWorksheet'
import { EXPORT_CONFIRM_ROWS, EXPORT_MAX_ROWS, fetchExportRows } from '../utils/fetchExportRows'
import { writeSpreadsheetFile } from '../utils/writeSpreadsheet'

/**
 * What a table hands its export: its rows, its columns and its file name.
 * `TSheetRow` is the row the columns read, which differs from the fetched
 * `TRow` when one record becomes several sheet rows, such as an order with
 * its lines.
 */
export interface SpreadsheetExportSource<TRow, TSheetRow = TRow> {
  /** The row count of the current filter, as the table's paginator shows it. */
  total: () => number
  /** The checked rows, exported as they are without reading the list again. */
  selected: () => readonly TRow[]
  /** One page of the current filter and sort, the same request the table makes. */
  fetchPage: (window: PageWindow, signal: AbortSignal) => Promise<PageResponse<TRow>>
  /** The columns in their sheet order, read when the export starts. */
  columns: () => SpreadsheetColumn<TSheetRow>[]
  format: () => SpreadsheetFormat
  /** Turns the exported records into sheet rows. Required when `TSheetRow` differs from `TRow`. */
  toSheetRows?: (rows: readonly TRow[]) => TSheetRow[]
}

/**
 * Runs the spreadsheet export of a table. The filtered scope reads every row
 * of the current filter page by page, asks first above
 * EXPORT_CONFIRM_ROWS rows and refuses above EXPORT_MAX_ROWS, and can be
 * cancelled while it reads. The selected scope writes the checked rows
 * straight away. `loaded` and `total` drive the progress shown meanwhile.
 */
export function useSpreadsheetExport<TRow, TSheetRow = TRow>(
  source: SpreadsheetExportSource<TRow, TSheetRow>,
) {
  const { t } = useI18n()
  const { formatNumber: n } = useLocaleFormat()
  const toast = useAppToast()
  const { ask } = useConfirmAsync()

  const exporting = ref(false)
  const loaded = ref(0)
  const total = ref(0)
  const controller = shallowRef<AbortController | null>(null)

  async function write(rows: readonly TRow[]): Promise<void> {
    const sheetRows = source.toSheetRows ? source.toSheetRows(rows) : (rows as readonly unknown[] as TSheetRow[])
    const worksheet = buildWorksheet(sheetRows, source.columns(), getDisplayTimezone())
    await writeSpreadsheetFile(worksheet, source.format())
  }

  // Refuses a filter above the cap and asks before a large one.
  async function mayExport(count: number): Promise<boolean> {
    if (count > EXPORT_MAX_ROWS) {
      toast.warn(
        t('spreadsheetExport.tooManyRows.summary'),
        t('spreadsheetExport.tooManyRows.detail', { count: n(count), limit: n(EXPORT_MAX_ROWS) }),
      )
      return false
    }
    if (count <= EXPORT_CONFIRM_ROWS) return true
    return ask({
      header: t('spreadsheetExport.confirm.header'),
      message: t('spreadsheetExport.confirm.message', { count: n(count) }),
      icon: 'mdi mdi-file-excel-outline',
      acceptProps: { label: t('spreadsheetExport.confirm.accept') },
      rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    })
  }

  async function exportFiltered(): Promise<void> {
    const count = source.total()
    if (count === 0 || !(await mayExport(count))) return

    const abort = new AbortController()
    controller.value = abort
    exporting.value = true
    loaded.value = 0
    total.value = count
    try {
      const rows = await fetchExportRows(source.fetchPage, {
        signal: abort.signal,
        onProgress: (done, all) => {
          loaded.value = done
          total.value = all
        },
      })
      await write(rows)
    } catch (e) {
      if (!abort.signal.aborted) {
        toast.error(t('spreadsheetExport.failed'), extractApiError(e) ?? undefined)
      }
    } finally {
      exporting.value = false
      controller.value = null
    }
  }

  async function exportSelected(): Promise<void> {
    const rows = source.selected()
    if (rows.length === 0) return
    try {
      await write(rows)
    } catch (e) {
      toast.error(t('spreadsheetExport.failed'), extractApiError(e) ?? undefined)
    }
  }

  /** Starts an export of `scope`; a second one waits until the first has finished. */
  async function run(scope: SpreadsheetExportScope): Promise<void> {
    if (exporting.value) return
    await (scope === 'selected' ? exportSelected() : exportFiltered())
  }

  /** Stops a running filtered export; nothing is downloaded. */
  function cancel(): void {
    controller.value?.abort()
  }

  return { exporting, loaded, total, run, cancel }
}
