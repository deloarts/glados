import type { MeetingOwnerResponse } from '../types/meetingResponse'

/** The meeting notes tab of the meeting's project or product. */
export function meetingNotesTabPath(owner: Pick<MeetingOwnerResponse, 'kind' | 'id'>): string {
  return owner.kind === 'project'
    ? `/workspace/projects/${owner.id}/meeting-notes`
    : `/workspace/products/${owner.id}/meeting-notes`
}

/** The meeting's page below its project or product. */
export function meetingPath(meeting: { id: number; owner: Pick<MeetingOwnerResponse, 'kind' | 'id'> }): string {
  return `${meetingNotesTabPath(meeting.owner)}/${meeting.id}`
}

/** The page of the meeting's owner. */
export function meetingOwnerPath(owner: Pick<MeetingOwnerResponse, 'kind' | 'id'>): string {
  return owner.kind === 'project' ? `/workspace/projects/${owner.id}` : `/workspace/products/${owner.id}`
}
