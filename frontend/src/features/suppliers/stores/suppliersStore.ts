import { createMasterDataStore, useToggleGroupBy } from '@/shared/stores/createMasterDataStore'
import { archiveSupplier } from '../api/archiveSupplier'
import { createSupplier } from '../api/createSupplier'
import { getSuppliers } from '../api/getSuppliers'
import { restoreSupplier } from '../api/restoreSupplier'
import { updateSupplier } from '../api/updateSupplier'

export type SupplierGroupBy = 'country' | 'capability' | null

// `items` is read by several other features (SupplierFormDialog,
// OrderCreateForm, ...) as the complete supplier list for pickers.
export const useSuppliersStore = createMasterDataStore('suppliers', {
  api: {
    list: getSuppliers,
    create: createSupplier,
    update: updateSupplier,
    archive: archiveSupplier,
    restore: restoreSupplier,
  },
  filters: {
    name: 'contains',
    legal_name: 'contains',
    level: 'equals',
    capability_id: 'equals',
    article_group_id: 'equals',
    address: 'contains',
    country: 'contains',
    email: 'contains',
    creator_id: 'equals',
    changed_by_id: 'equals',
  },
  dateRanges: ['created', 'changed'],
  extend: () => useToggleGroupBy<Exclude<SupplierGroupBy, null>>(),
})
