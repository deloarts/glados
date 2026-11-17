import { FilterMatchMode } from '@openvue/core/api'

import type { DataTableFilterMeta } from 'openvue/datatable'

// Filtering is server-side; this object only exists because
// filterDisplay="row" throws without an entry per filterable column.
export const ORDERS_TABLE_FILTERS: DataTableFilterMeta = {
  order_number: { value: null, matchMode: FilterMatchMode.CONTAINS },
  status: { value: null, matchMode: FilterMatchMode.EQUALS },
  supplier_name: { value: null, matchMode: FilterMatchMode.EQUALS },
  ordered_date: { value: null, matchMode: FilterMatchMode.CONTAINS },
  expected_delivery_date: { value: null, matchMode: FilterMatchMode.CONTAINS },
  delivery_date: { value: null, matchMode: FilterMatchMode.CONTAINS },
  note: { value: null, matchMode: FilterMatchMode.CONTAINS },
  storage_place: { value: null, matchMode: FilterMatchMode.CONTAINS },
  created: { value: null, matchMode: FilterMatchMode.CONTAINS },
}
