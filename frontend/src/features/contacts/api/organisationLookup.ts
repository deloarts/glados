import { webApi } from '@/core/api/webRequest'

import type { LookupOption } from '@/shared/components/forms/lookupMultiSelect'

/** How many organisations the picker offers at once. */
const PAGE_SIZE = 20

/**
 * The customers and suppliers a contact can belong to, as lookup options,
 * read straight from their list routes so the contacts feature needs
 * neither of their features. Archived organisations stay pickable, since an
 * existing contact may still name one.
 */
export async function fetchCustomerOptions(query: string): Promise<LookupOption[]> {
  const page = await webApi.get('/customers/', {
    query: {
      limit: PAGE_SIZE,
      include_archived: true,
      order_by: 'name',
      order_dir: 'asc',
      ...(query ? { name: query } : {}),
    },
  })
  return page.items.map((customer) => ({ id: customer.id, label: customer.name }))
}

export async function fetchCustomerOptionsByIds(ids: number[]): Promise<LookupOption[]> {
  const customers = await Promise.all(
    ids.map((id) => webApi.get('/customers/{customer_id}', { path: { customer_id: id } })),
  )
  return customers.map((customer) => ({ id: customer.id, label: customer.name }))
}

export async function fetchSupplierOptions(query: string): Promise<LookupOption[]> {
  const page = await webApi.get('/suppliers/', {
    query: {
      limit: PAGE_SIZE,
      include_archived: true,
      order_by: 'name',
      order_dir: 'asc',
      ...(query ? { name: query } : {}),
    },
  })
  return page.items.map((supplier) => ({ id: supplier.id, label: supplier.name }))
}

export async function fetchSupplierOptionsByIds(ids: number[]): Promise<LookupOption[]> {
  const suppliers = await Promise.all(
    ids.map((id) => webApi.get('/suppliers/{supplier_id}', { path: { supplier_id: id } })),
  )
  return suppliers.map((supplier) => ({ id: supplier.id, label: supplier.name }))
}
