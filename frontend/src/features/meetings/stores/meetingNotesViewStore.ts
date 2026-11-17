import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { emptyMeetingListFilters, hasMeetingListFilters } from '../utils/meetingListFilters'
import type { MeetingListFilters } from '../utils/meetingListFilters'

export type MeetingSort = 'startsDesc' | 'startsAsc' | 'numberDesc' | 'numberAsc' | 'nameAsc' | 'nameDesc'

const DEFAULT_SORT: MeetingSort = 'startsDesc'

/**
 * How the Meeting Notes tab of a project or a product is looked at, shared
 * by its views bar and its table: invalid meetings shown or not, on a
 * product the meetings of its projects hidden or not and grouped by project,
 * the tag the list is filtered by, the column filters, the sort, the
 * actions column and the Project column. By default invalid meetings are
 * left out, a product's projects are shown without a Project column, and
 * nothing filters the list. Sync bumps `refreshTrigger`.
 */
export const useMeetingNotesViewStore = defineStore('meetingNotesView', () => {
  const showInvalid = ref(false)
  const hideProjects = ref(false)
  const groupByProject = ref(false)
  const tagFilter = ref<string | null>(null)
  const filters = ref<MeetingListFilters>(emptyMeetingListFilters())
  const sortBy = ref<MeetingSort>(DEFAULT_SORT)
  const showActions = ref(false)
  const showProjectColumn = ref(false)
  const refreshTrigger = ref(0)

  const hasActiveFilters = computed(
    () =>
      showInvalid.value ||
      hideProjects.value ||
      groupByProject.value ||
      !!tagFilter.value ||
      hasMeetingListFilters(filters.value) ||
      sortBy.value !== DEFAULT_SORT,
  )

  function triggerRefresh(): void {
    refreshTrigger.value += 1
  }

  function setSort(sort: MeetingSort): void {
    sortBy.value = sort
  }

  function clearSort(): void {
    sortBy.value = DEFAULT_SORT
  }

  function clearAll(): void {
    showInvalid.value = false
    hideProjects.value = false
    groupByProject.value = false
    tagFilter.value = null
    filters.value = emptyMeetingListFilters()
    sortBy.value = DEFAULT_SORT
  }

  return {
    showInvalid,
    hideProjects,
    groupByProject,
    tagFilter,
    filters,
    sortBy,
    showActions,
    showProjectColumn,
    refreshTrigger,
    hasActiveFilters,
    triggerRefresh,
    setSort,
    clearSort,
    clearAll,
  }
})
