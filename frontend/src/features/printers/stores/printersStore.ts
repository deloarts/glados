import { createMasterDataStore, useToggleGroupBy } from '@/shared/stores/createMasterDataStore'
import { archivePrinter } from '../api/archivePrinter'
import { createPrinter } from '../api/createPrinter'
import { getPrinters } from '../api/getPrinters'
import { restorePrinter } from '../api/restorePrinter'
import { updatePrinter } from '../api/updatePrinter'

export type PrinterGroupBy = 'kind' | 'location' | null

// No other feature picks printers from this store, so items is the
// management table's current page. The filter keys match the backend query
// params, so the created and changed columns set `filter-field` to
// `creator_id` and `changed_by_id` rather than a display field. `enabled` is a boolean filter, so `false` is sent
// and counts as active.
export const usePrintersStore = createMasterDataStore('printers', {
  api: {
    list: getPrinters,
    create: createPrinter,
    update: updatePrinter,
    archive: archivePrinter,
    restore: restorePrinter,
  },
  filters: {
    name: 'contains',
    kind: 'equals',
    enabled: 'boolean',
    creator_id: 'equals',
    changed_by_id: 'equals',
  },
  tableOnly: true,
  extend: () => useToggleGroupBy<Exclude<PrinterGroupBy, null>>(),
})
