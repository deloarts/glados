import { useI18n } from 'vue-i18n'

import { exportFilename, useSpreadsheetExport } from '@/shared/spreadsheet-export'

import { getBoughtItems } from '../api/getBoughtItems'
import { useBoughtItemsCatalogueColumnsStore } from '../stores/boughtItemsCatalogueColumnsStore'
import { useBoughtItemsCatalogueEditStore } from '../stores/boughtItemsCatalogueEditStore'
import { useBoughtItemsStore } from '../stores/boughtItemsStore'
import { boughtItemsExportColumns } from '../utils/boughtItemsCatalogueExport'
import { useBoughtItemsCatalogueQuery } from './useBoughtItemsCatalogueQuery'

/**
 * The spreadsheet export of the bought item catalogue: the rows of the
 * table's current filter and sort, or the checked rows, with the table's
 * visible columns.
 */
export function useBoughtItemsCatalogueExport() {
  const { t } = useI18n()
  const boughtItemsStore = useBoughtItemsStore()
  const editStore = useBoughtItemsCatalogueEditStore()
  const columnsStore = useBoughtItemsCatalogueColumnsStore()
  const listQuery = useBoughtItemsCatalogueQuery()

  return useSpreadsheetExport({
    total: () => boughtItemsStore.total,
    selected: () => editStore.selectedItems,
    fetchPage: (window, signal) => getBoughtItems({ ...listQuery(), ...window }, { signal }),
    columns: () => boughtItemsExportColumns(columnsStore.visibleColumns, t),
    format: () => ({
      sheetName: t('boughtItems.catalogue.export.sheetName'),
      filename: exportFilename(t('boughtItems.catalogue.export.filename')),
    }),
  })
}
