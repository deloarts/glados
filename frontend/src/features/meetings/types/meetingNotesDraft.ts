import type { Schemas } from '@/core/api/generated'

export type MeetingNotesDraftSummaryResponse = Schemas['MeetingNotesDraftSummaryResponse']
export type MeetingNotesDraftResponse = Schemas['MeetingNotesDraftResponse']
export type MeetingNotesDraftCardResponse = Schemas['MeetingNotesDraftCardResponse']
export type MeetingNotesDraftApplyRequest = Schemas['MeetingNotesDraftApplyRequest']
export type MeetingNotesDraftApplyResponse = Schemas['MeetingNotesDraftApplyResponse']
export type MeetingNotesDraftCardRequest = Schemas['MeetingNotesDraftCardRequest']
export type PersonMatchResponse = Schemas['PersonMatchResponse']
export type PersonSuggestionResponse = Schemas['PersonSuggestionResponse']

export interface MeetingNotesDraftListParams {
  meeting_id?: number
  project_id?: number
  product_id?: number
}
