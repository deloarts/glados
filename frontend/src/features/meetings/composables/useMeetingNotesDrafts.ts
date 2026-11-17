import { ref, watch } from 'vue'
import type { Ref } from 'vue'

import { getMeetingNotesDrafts } from '../api/meetingNotesDraftsApi'
import type { MeetingNotesDraftListParams, MeetingNotesDraftSummaryResponse } from '../types/meetingNotesDraft'

/**
 * The signed-in user's drafts of meeting notes that wait at one place: on a
 * meeting's page those that add to it, on a project's or product's meeting
 * list those that propose a new meeting there. A failed load shows none,
 * since the drafts are only a hint next to the page's own content.
 */
export function useMeetingNotesDrafts(params: () => MeetingNotesDraftListParams | null): {
  drafts: Ref<MeetingNotesDraftSummaryResponse[]>
  load: () => Promise<void>
} {
  const drafts = ref<MeetingNotesDraftSummaryResponse[]>([])

  async function load(): Promise<void> {
    const current = params()
    if (!current) {
      drafts.value = []
      return
    }
    try {
      const found = await getMeetingNotesDrafts(current)
      drafts.value = current.meeting_id === undefined ? found.filter((d) => d.meeting_id === null) : found
    } catch {
      drafts.value = []
    }
  }

  watch(
    () => JSON.stringify(params()),
    () => void load(),
    { immediate: true },
  )
  return { drafts, load }
}
