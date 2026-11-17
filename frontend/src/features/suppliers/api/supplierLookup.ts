import { getSupplier } from './getSupplier'
import { getSuppliers } from './getSuppliers'

import type { LookupOption } from '@/shared/components/forms/lookupMultiSelect'
import type { SupplierResponse } from '../types/supplierResponse'

/** How many suppliers a lookup filter offers at once. */
const PAGE_SIZE = 20

function toOption(supplier: SupplierResponse): LookupOption {
  return { id: supplier.id, label: supplier.name }
}

/**
 * A page of suppliers for a lookup filter such as a manufacturer column,
 * archived ones included since old records still name them, narrowed by
 * name while the user types.
 */
export async function fetchSupplierLookupOptions(query: string): Promise<LookupOption[]> {
  const page = await getSuppliers({
    limit: PAGE_SIZE,
    include_archived: true,
    order_by: 'name',
    order_dir: 'asc',
    ...(query ? { name: query } : {}),
  })
  return page.items.map(toOption)
}

export async function fetchSupplierLookupByIds(ids: number[]): Promise<LookupOption[]> {
  const suppliers = await Promise.all(ids.map((id) => getSupplier(id)))
  return suppliers.map(toOption)
}
