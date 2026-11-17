import { useI18n } from 'vue-i18n'

import { getSourceItemDemands, useSourceItemDemandsStore } from '@/features/source-items'
import { useBucketsStore } from '@/features/buckets'
import { exportFilename, useSpreadsheetExport } from '@/shared/spreadsheet-export'

import { useSourceItemDemandsSelectionStore } from '../stores/sourceItemDemandsSelectionStore'
import { sourceItemDemandsExportColumns } from '../utils/sourceItemDemandsExport'
import { useSourceItemDemandsQuery } from './useSourceItemDemandsQuery'

/**
 * The spreadsheet export of the source item demands: the rows of the
 * table's current filter and sort, or the checked rows.
 */
export function useSourceItemDemandsExport() {
  const { t } = useI18n()
  const demandsStore = useSourceItemDemandsStore()
  const selectionStore = useSourceItemDemandsSelectionStore()
  const bucketsStore = useBucketsStore()
  const { listParams } = useSourceItemDemandsQuery()

  return useSpreadsheetExport({
    total: () => demandsStore.total,
    selected: () => selectionStore.selectedDemands,
    fetchPage: (window, signal) => getSourceItemDemands({ ...listParams(), ...window }, { signal }),
    columns: () =>
      sourceItemDemandsExportColumns(
        t,
        (bucketId) => bucketsStore.byId.source_item_demand[bucketId]?.name ?? null,
      ),
    format: () => ({
      sheetName: t('sourceItems.demands.export.sheetName'),
      filename: exportFilename(t('sourceItems.demands.export.filename')),
    }),
  })
}
