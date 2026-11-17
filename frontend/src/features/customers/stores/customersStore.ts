import { createMasterDataStore, useToggleGroupBy } from '@/shared/stores/createMasterDataStore'
import { archiveCustomer } from '../api/archiveCustomer'
import { createCustomer } from '../api/createCustomer'
import { getCustomers } from '../api/getCustomers'
import { restoreCustomer } from '../api/restoreCustomer'
import { updateCustomer } from '../api/updateCustomer'

export type CustomerGroupBy = 'country' | 'level' | null

// items is the complete customer list other features pick from.
export const useCustomersStore = createMasterDataStore('customers', {
  api: {
    list: getCustomers,
    create: createCustomer,
    update: updateCustomer,
    archive: archiveCustomer,
    restore: restoreCustomer,
  },
  filters: {
    name: 'contains',
    legal_name: 'contains',
    level: 'equals',
    address: 'contains',
    country: 'contains',
    email: 'contains',
    creator_id: 'equals',
    changed_by_id: 'equals',
  },
  dateRanges: ['created', 'changed'],
  extend: () => useToggleGroupBy<Exclude<CustomerGroupBy, null>>(),
})
