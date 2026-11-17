import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { getQaTasks } from '../api/getQaTasks'
import { useQaFiltersStore } from './qaFiltersStore'
import { buildQaTaskFilterParams } from '../utils/qaTaskFilterParams'

import type { QaTaskFilterParams, QaTaskResponse } from '../types/qaTaskResponse'

export const useQaTasksStore = defineStore('qaTasks', () => {
  const tasks = ref<QaTaskResponse[]>([])
  // The whole worklist's count for the paginator.
  const total = ref(0)
  const loading = ref(false)
  // A live re-sync must not blank the table, so it has its own flag. Both
  // entry points share one sequencer, so stale responses are discarded.
  const refreshing = ref(false)

  const { error, run } = useSequencedFetch(getQaTasks)

  const filters = useQaFiltersStore()

  // Server-side, since inspection orders are not knowable client side without
  // every lot.
  function buildParams(page?: { skip: number; limit: number }): QaTaskFilterParams {
    return buildQaTaskFilterParams(filters, page)
  }

  function apply(page: { items: QaTaskResponse[]; total: number }): void {
    tasks.value = page.items
    total.value = page.total
  }

  async function fetchTasks(page?: { skip: number; limit: number }): Promise<void> {
    loading.value = true
    try {
      const response = await run(buildParams(page))
      if (response) apply(response)
    } finally {
      loading.value = false
    }
  }

  async function refresh(page?: { skip: number; limit: number }): Promise<void> {
    refreshing.value = true
    try {
      const response = await run(buildParams(page))
      if (response) apply(response)
    } finally {
      refreshing.value = false
    }
  }

  // Counts over what is displayed, i.e. the current page.
  const readyCount = computed(() => tasks.value.filter((t) => t.can_start).length)
  const evidenceMissingCount = computed(
    () => tasks.value.filter((t) => t.requires_evidence && !t.has_evidence).length,
  )

  return {
    tasks,
    total,
    loading,
    refreshing,
    error,
    readyCount,
    evidenceMissingCount,
    fetchTasks,
    refresh,
  }
})
