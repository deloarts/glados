import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { getMyTimeTrackingAccount } from '../api/timeTrackingApi'
import type { TimeTrackingAccountResponse } from '../types/timeTrackingTypes'

/**
 * The signed-in user's time tracking account state: which credentials are
 * stored and whether they can be used. It is Glados data only, so loading
 * it never contacts the time tracking system. The sidebar shortcut, My
 * Account and the Time Tracking tab all read this one copy; it is loaded
 * once after sign-in and refreshed after a save, a removal, or a response
 * that reports the credentials as no longer usable.
 *
 * The verification result of a save or an access check (employee name and
 * read rights) is dropped here, since it belongs to the response that
 * produced it and is not kept beyond the screen that shows it. No password
 * ever reaches this store. Reset on logout like every per-user store.
 */
export const useTimeTrackingAccountStore = defineStore('timeTrackingAccount', () => {
  const { loading, error, run } = useSequencedFetch(getMyTimeTrackingAccount)

  const account = ref<TimeTrackingAccountResponse | null>(null)
  const loaded = ref(false)

  let pending: Promise<void> | null = null

  const credentialsValid = computed(() => account.value?.time_tracking_credentials_valid ?? false)

  function setAccount(next: TimeTrackingAccountResponse): void {
    account.value = { ...next, time_tracking_employee_name: null, time_tracking_rights: null }
    loaded.value = true
  }

  async function refresh(): Promise<void> {
    const result = await run()
    if (result) setAccount(result)
  }

  /**
   * Loads the account unless it already is; concurrent callers share one
   * request. A failed load stays retryable.
   */
  function ensureLoaded(): Promise<void> {
    if (loaded.value) return Promise.resolve()
    if (!pending) {
      pending = refresh().finally(() => {
        pending = null
      })
    }
    return pending
  }

  return { account, loaded, loading, error, credentialsValid, setAccount, refresh, ensureLoaded }
})
