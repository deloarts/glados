import { ref, watch } from 'vue'

import { getCustomers } from '../api/getCustomers'

import type { Ref } from 'vue'
import type { CustomerResponse } from '../types/customerResponse'

/**
 * Keeps a CustomerSelect in step with a form that stores only a customer id,
 * such as a made item's customer. The id stays the source of truth, so a save
 * before the customer has loaded keeps it instead of clearing it. Archived
 * customers resolve too.
 */
export function useCustomerById(customerId: Ref<number | null>) {
  const customer = ref<CustomerResponse | null>(null)

  watch(
    customerId,
    async (id) => {
      if (id === null) {
        customer.value = null
        return
      }
      if (customer.value?.id === id) return
      const result = await getCustomers({ id, include_archived: true, limit: 1 })
      // A later pick wins over a lookup that was still in flight.
      if (customerId.value === id) customer.value = result.items[0] ?? null
    },
    { immediate: true },
  )

  function selectCustomer(selected: CustomerResponse | null): void {
    customer.value = selected
    customerId.value = selected?.id ?? null
  }

  return { customer, selectCustomer }
}
