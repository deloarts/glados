import { useI18n } from 'vue-i18n'

import { getDemands, useBoughtItemsDemandsStore } from '@/features/bought-items'
import { useBucketsStore } from '@/features/buckets'
import { exportFilename, useSpreadsheetExport } from '@/shared/spreadsheet-export'

import { useBoughtItemsProcurementStore } from '../stores/boughtItemsProcurementStore'
import { boughtItemDemandsExportColumns } from '../utils/boughtItemDemandsExport'
import { useBoughtItemDemandsQuery } from './useBoughtItemDemandsQuery'

/**
 * The spreadsheet export of the bought item demands: the rows of the
 * table's current filter and sort, or the checked rows.
 */
export function useBoughtItemDemandsExport() {
  const { t } = useI18n()
  const demandsStore = useBoughtItemsDemandsStore()
  const procurementStore = useBoughtItemsProcurementStore()
  const bucketsStore = useBucketsStore()
  const { listParams } = useBoughtItemDemandsQuery()

  return useSpreadsheetExport({
    total: () => demandsStore.total,
    selected: () => procurementStore.selectedDemands,
    fetchPage: (window, signal) => getDemands({ ...listParams(), ...window }, { signal }),
    columns: () =>
      boughtItemDemandsExportColumns(
        t,
        (bucketId) => bucketsStore.byId.bought_item_demand[bucketId]?.name ?? null,
      ),
    format: () => ({
      sheetName: t('boughtItems.demands.export.sheetName'),
      filename: exportFilename(t('boughtItems.demands.export.filename')),
    }),
  })
}
