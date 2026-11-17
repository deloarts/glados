import { useI18n } from 'vue-i18n'

import { getMadeItemDemands, useMadeItemsDemandsStore } from '@/features/made-items'
import { useBucketsStore } from '@/features/buckets'
import { exportFilename, useSpreadsheetExport } from '@/shared/spreadsheet-export'

import { useMadeItemsProcurementStore } from '../stores/madeItemsProcurementStore'
import { madeItemDemandsExportColumns } from '../utils/madeItemDemandsExport'
import { useMadeItemDemandsQuery } from './useMadeItemDemandsQuery'

/**
 * The spreadsheet export of the made item demands: the rows of the table's
 * current filter and sort, or the checked rows.
 */
export function useMadeItemDemandsExport() {
  const { t, locale } = useI18n()
  const demandsStore = useMadeItemsDemandsStore()
  const procurementStore = useMadeItemsProcurementStore()
  const bucketsStore = useBucketsStore()
  const { listParams } = useMadeItemDemandsQuery()

  return useSpreadsheetExport({
    total: () => demandsStore.total,
    selected: () => procurementStore.selectedDemands,
    fetchPage: (window, signal) => getMadeItemDemands({ ...listParams(), ...window }, { signal }),
    columns: () =>
      madeItemDemandsExportColumns(
        t,
        locale.value,
        (bucketId) => bucketsStore.byId.made_item_demand[bucketId]?.name ?? null,
      ),
    format: () => ({
      sheetName: t('madeItems.demands.export.sheetName'),
      filename: exportFilename(t('madeItems.demands.export.filename')),
    }),
  })
}
