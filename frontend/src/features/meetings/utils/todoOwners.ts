import type { UserSummary } from '@/core/types/userResponse'
import type { MeetingResponse, MeetingTodoResponse } from '../types/meetingResponse'

/** Someone a todo can belong to, as the todo form offers them. */
export interface TodoOwnerOption {
  value: string
  label: string
  kind: 'user' | 'contact'
}

/** The people of Glados a card can mention or a todo can belong to. */
export function activePeople(users: UserSummary[]): UserSummary[] {
  return users.filter((user) => user.is_active && !user.is_service_account && !user.is_systemuser)
}

/**
 * The owners a todo of the meeting can have: every active Glados user, and
 * the contacts that attend the meeting, such as the customer who confirms a
 * colour.
 */
export function todoOwnerOptions(meeting: MeetingResponse, users: UserSummary[]): TodoOwnerOption[] {
  const people: TodoOwnerOption[] = activePeople(users).map((user) => ({ value: `u:${user.id}`, label: user.full_name, kind: 'user' }))
  const contacts: TodoOwnerOption[] = meeting.attendees
    .filter((attendee) => attendee.kind === 'contact' && attendee.contact_id !== null && !attendee.anonymised)
    .map((attendee) => ({ value: `c:${attendee.contact_id}`, label: attendee.name, kind: 'contact' }))
  return [...people, ...contacts]
}

/** A todo only contacts own shows on no todo page and sends no notification. */
export function ownedOnlyByContacts(todo: MeetingTodoResponse): boolean {
  return todo.owners.length > 0 && todo.owners.every((owner) => owner.user === null)
}
