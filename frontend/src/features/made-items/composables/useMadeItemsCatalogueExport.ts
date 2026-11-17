import { useI18n } from 'vue-i18n'

import { exportFilename, useSpreadsheetExport } from '@/shared/spreadsheet-export'

import { getMadeItems } from '../api/getMadeItems'
import { useMadeItemsCatalogueColumnsStore } from '../stores/madeItemsCatalogueColumnsStore'
import { useMadeItemsCatalogueEditStore } from '../stores/madeItemsCatalogueEditStore'
import { useMadeItemsStore } from '../stores/madeItemsStore'
import { madeItemsExportColumns } from '../utils/madeItemsCatalogueExport'
import { useMadeItemsCatalogueQuery } from './useMadeItemsCatalogueQuery'

/**
 * The spreadsheet export of the made item catalogue: the rows of the
 * table's current filter and sort, or the checked rows, with the table's
 * visible columns.
 */
export function useMadeItemsCatalogueExport() {
  const { t, locale } = useI18n()
  const madeItemsStore = useMadeItemsStore()
  const editStore = useMadeItemsCatalogueEditStore()
  const columnsStore = useMadeItemsCatalogueColumnsStore()
  const listQuery = useMadeItemsCatalogueQuery()

  return useSpreadsheetExport({
    total: () => madeItemsStore.total,
    selected: () => editStore.selectedItems,
    fetchPage: (window, signal) => getMadeItems({ ...listQuery(), ...window }, { signal }),
    columns: () => madeItemsExportColumns(columnsStore.visibleColumns, t, locale.value),
    format: () => ({
      sheetName: t('madeItems.catalogue.export.sheetName'),
      filename: exportFilename(t('madeItems.catalogue.export.filename')),
    }),
  })
}
