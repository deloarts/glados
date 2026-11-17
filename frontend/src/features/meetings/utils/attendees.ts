import type { MeetingAttendeeRequest } from '../types/meetingRequest'
import type { MeetingAttendanceStatus, MeetingAttendeeKind, MeetingAttendeeResponse } from '../types/meetingResponse'

/** An attendee as the meeting dialog edits it, before it is saved. */
export interface AttendeeDraft {
  key: string
  kind: MeetingAttendeeKind
  status: MeetingAttendanceStatus
  userId: number | null
  contactId: number | null
  /** The guest's row on the meeting, so editing keeps it. */
  attendeeId: number | null
  name: string
  email: string | null
  /** A line under the name, such as a contact's organisation. */
  detail: string | null
}

export const ATTENDANCE_STATUSES: MeetingAttendanceStatus[] = ['present', 'excused', 'distribution_only']

export function attendeeKey(kind: MeetingAttendeeKind, id: number | string): string {
  return `${kind}:${id}`
}

export function draftFromAttendee(attendee: MeetingAttendeeResponse): AttendeeDraft {
  const id = attendee.user?.id ?? attendee.contact_id ?? attendee.id
  return {
    key: attendeeKey(attendee.kind, id),
    kind: attendee.kind,
    status: attendee.status,
    userId: attendee.user?.id ?? null,
    contactId: attendee.contact_id,
    attendeeId: attendee.kind === 'guest' ? attendee.id : null,
    name: attendee.name,
    email: attendee.email,
    detail: null,
  }
}

export function attendeeRequest(draft: AttendeeDraft): MeetingAttendeeRequest {
  if (draft.kind === 'user') return { kind: 'user', status: draft.status, user_id: draft.userId }
  if (draft.kind === 'contact') return { kind: 'contact', status: draft.status, contact_id: draft.contactId }
  return {
    kind: 'guest',
    status: draft.status,
    attendee_id: draft.attendeeId,
    name: draft.name,
    email: draft.email || null,
  }
}

const GUEST_RE = /^(.*?)\s*<?([^\s<>]+@[^\s<>]+?)>?$/

/** A guest typed as "Name", "Name e-mail" or "Name <e-mail>". */
export function parseGuest(input: string): { name: string; email: string | null } {
  const text = input.trim()
  const match = GUEST_RE.exec(text)
  if (!match) return { name: text, email: null }
  const email = match[2] as string
  return { name: (match[1] as string).trim() || email, email }
}
