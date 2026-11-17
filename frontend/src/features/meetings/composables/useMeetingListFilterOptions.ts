import { computed } from 'vue'
import type { Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  MEETING_STATUS_FILTERS,
  MEETING_TODO_FILTERS,
  PRODUCT_OWNER_KEY,
  attendeeNames,
  ownerKey,
} from '../utils/meetingListFilters'
import type { MeetingListRowResponse } from '../types/meetingResponse'

/**
 * The choices of the Meeting Notes table's column filters: the fixed status
 * and todo choices, and the projects and attendees of the loaded list.
 */
export function useMeetingListFilterOptions(rows: Ref<MeetingListRowResponse[]>) {
  const { t } = useI18n()

  const statusOptions = computed(() =>
    MEETING_STATUS_FILTERS.map((value) => ({ value, label: t(`meetings.list.filters.status.${value}`) })),
  )
  const todoOptions = computed(() =>
    MEETING_TODO_FILTERS.map((value) => ({ value, label: t(`meetings.list.filters.todos.${value}`) })),
  )
  // The product itself and the projects its list holds, by number.
  const ownerOptions = computed(() => {
    const projects = new Map<string, string>()
    for (const row of rows.value) if (row.owner.kind === 'project') projects.set(ownerKey(row), row.owner.number)
    const sorted = [...projects].sort(([, a], [, b]) => a.localeCompare(b))
    return [
      { value: PRODUCT_OWNER_KEY, label: t('meetings.list.product') },
      ...sorted.map(([value, label]) => ({ value, label })),
    ]
  })
  const attendeeOptions = computed(() => attendeeNames(rows.value))

  return { statusOptions, todoOptions, ownerOptions, attendeeOptions }
}
