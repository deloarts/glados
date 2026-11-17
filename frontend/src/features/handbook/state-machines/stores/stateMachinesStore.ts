import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

import { getStateMachines } from '../api/getStateMachines'
import { extractApiError } from '@/core/utils/errors'
import type { StateMachineResponse } from '../types/stateMachinesResponse'

// The backend returns the whole registry in one request, so every embed on
// every handbook page shares this store. loaded makes a repeat call a no-op
// and pending collapses racing callers into one request.
export const useStateMachinesStore = defineStore('stateMachines', () => {
  const machines = shallowRef<StateMachineResponse[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  // Raw backend detail; the component picks the message to show.
  const error = ref<string | null>(null)
  const lastFetched = shallowRef<Date | null>(null)

  let pending: Promise<void> | null = null

  async function run(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await getStateMachines()
      machines.value = response.machines
      lastFetched.value = new Date()
      loaded.value = true
    } catch (e) {
      error.value = extractApiError(e)
      // loaded stays false, so the next page retries a failed fetch.
    } finally {
      loading.value = false
    }
  }

  /** No-ops once loaded; callers racing before the first response lands share it. */
  function fetch(): Promise<void> {
    if (loaded.value) return Promise.resolve()
    if (pending) return pending
    pending = run().finally(() => {
      pending = null
    })
    return pending
  }

  /** Forces a fresh request, e.g. after a backend restart. */
  function refresh(): Promise<void> {
    loaded.value = false
    return fetch()
  }

  return { machines, loading, loaded, error, lastFetched, fetch, refresh }
})
