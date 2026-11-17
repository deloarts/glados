import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { getPdmUsers } from '../api/getPdmUsers'
import { linkPdmUsers } from '../api/linkPdmUsers'

import type { LinkPdmUserEntry, PdmUser } from '../types/adminSettingsTypes'

/**
 * Backs the "Match PDM Users" dialog: an unpaged list of every
 * vault user (`refresh`), and `save`, which posts the batch of links the
 * dialog collected and then reloads so `linked_user_id`/`proposed_user_id`
 * reflect what the backend actually stored rather than an optimistic guess.
 */
export const usePdmUsersStore = defineStore('pdmUsers', () => {
  const { loading, error, run } = useSequencedFetch(getPdmUsers)
  const items = ref<PdmUser[]>([])

  async function refresh(): Promise<void> {
    const response = await run()
    if (!response) return
    items.value = response
  }

  async function save(links: LinkPdmUserEntry[]): Promise<void> {
    await linkPdmUsers({ links })
    await refresh()
  }

  return {
    loading,
    error,
    items,

    refresh,
    save,
  }
})
