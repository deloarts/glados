import { ref, watch } from 'vue'
import type { Ref } from 'vue'

import { getContactUsage } from '../api/contactsApi'
import type { ContactUsageResponse } from '../types/contactResponse'

/**
 * Where the contacts of a table page are used, loaded in one request
 * whenever the page changes. A failed load leaves the column empty rather
 * than blocking the table.
 */
export function useContactUsage(contacts: Ref<{ id: number }[]>) {
  const usage = ref<Map<number, ContactUsageResponse>>(new Map())
  let epoch = 0

  async function load(): Promise<void> {
    const current = ++epoch
    const ids = contacts.value.map((contact) => contact.id)
    try {
      const rows = await getContactUsage(ids)
      if (current === epoch) usage.value = new Map(rows.map((row) => [row.contact_id, row]))
    } catch {
      if (current === epoch) usage.value = new Map()
    }
  }

  watch(contacts, () => void load(), { immediate: true })

  return { usage, reload: load }
}
