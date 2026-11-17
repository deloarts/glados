import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type MeetingListParams = QueryOf<'/meetings'>
export type MeetingScopeParams = QueryOf<'/meeting-scopes'>
export type MeetingTagParams = QueryOf<'/meeting-tags'>

export type MeetingCreateRequest = Schemas['MeetingCreateRequest']
export type MeetingUpdateRequest = Schemas['MeetingUpdateRequest']
export type MeetingAttendeeRequest = Schemas['MeetingAttendeeRequest']
export type MeetingCardCreateRequest = Schemas['MeetingCardCreateRequest']
export type MeetingCardUpdateRequest = Schemas['MeetingCardUpdateRequest']
export type MeetingDecisionRequest = Schemas['MeetingDecisionRequest']
export type MeetingTodoRequest = Schemas['MeetingTodoRequest']
export type MeetingTodoOwnerRequest = Schemas['MeetingTodoOwnerRequest']
export type MeetingScopeRenameRequest = Schemas['MeetingScopeRenameRequest']
