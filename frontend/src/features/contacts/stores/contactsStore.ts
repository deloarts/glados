import { ref } from 'vue'

import { createMasterDataStore } from '@/shared/stores/createMasterDataStore'
import {
  archiveContact,
  createContact,
  getContacts,
  restoreContact,
  updateContact,
} from '../api/contactsApi'

/**
 * The contacts tab's table. No other feature picks from a whole contact
 * list, so the store keeps only the table's page. Grouping by organisation
 * sorts by organisation on the server, so a group stays together across
 * pages.
 */
export const useContactsStore = createMasterDataStore('contacts', {
  api: {
    list: getContacts,
    create: createContact,
    update: updateContact,
    archive: archiveContact,
    restore: restoreContact,
  },
  filters: {
    name: 'contains',
    email: 'contains',
    phone: 'contains',
    organisation_kind: 'equals',
  },
  tableOnly: true,
  extend: (base) => {
    const groupBy = ref<'organisation' | null>(null)

    function setGroupBy(value: 'organisation'): void {
      if (groupBy.value === value) {
        clearGroupBy()
        return
      }
      groupBy.value = value
      base.setSort('organisation', 'asc')
    }

    function clearGroupBy(): void {
      groupBy.value = null
      if (base.sortBy.value === 'organisation') base.clearSort()
    }

    return { groupBy, setGroupBy, clearGroupBy }
  },
})
