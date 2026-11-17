import { webApi } from '@/core/api/webRequest'

import type {
  MeetingNotesDraftApplyRequest,
  MeetingNotesDraftApplyResponse,
  MeetingNotesDraftListParams,
  MeetingNotesDraftResponse,
  MeetingNotesDraftSummaryResponse,
} from '../types/meetingNotesDraft'

/** The signed-in user's drafts of meeting notes, newest first. */
export async function getMeetingNotesDrafts(
  params: MeetingNotesDraftListParams = {},
): Promise<MeetingNotesDraftSummaryResponse[]> {
  return webApi.get('/meeting-notes-drafts/', { query: params })
}

/** One draft with the users and contacts suggested for its names. */
export async function getMeetingNotesDraft(draftId: number): Promise<MeetingNotesDraftResponse> {
  return webApi.get('/meeting-notes-drafts/{draft_id}', { path: { draft_id: draftId } })
}

export async function applyMeetingNotesDraft(
  draftId: number,
  body: MeetingNotesDraftApplyRequest,
): Promise<MeetingNotesDraftApplyResponse> {
  return webApi.post('/meeting-notes-drafts/{draft_id}/apply', { path: { draft_id: draftId }, body })
}

export async function discardMeetingNotesDraft(draftId: number): Promise<void> {
  await webApi.delete('/meeting-notes-drafts/{draft_id}', { path: { draft_id: draftId } })
}
