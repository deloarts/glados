import type { MeetingAttendeeRequest, MeetingTodoOwnerRequest } from '../types/meetingRequest'
import type { MeetingAttendanceStatus, MeetingScopeIcon } from '../types/meetingResponse'
import type {
  MeetingNotesDraftApplyRequest,
  MeetingNotesDraftResponse,
  PersonSuggestionResponse,
} from '../types/meetingNotesDraft'

/**
 * The review of a draft of meeting notes an agent prepared: the form the
 * page edits, built from the draft, and the request that applies it. The
 * names the notes carry are matched once per spelling, so one choice covers
 * every place a name appears, as an attendee and as a todo owner. A choice
 * is `user:<id>`, `contact:<id>`, `guest` (an attendee as written) or
 * `none` (left out).
 */
export type PersonChoice = `user:${number}` | `contact:${number}` | 'guest' | 'none'

export interface ReviewTodo {
  title: string
  note: string | null
  due_date: string | null
  /** The owners as the notes name them. */
  owners: string[]
}

export interface ReviewCard {
  include: boolean
  scope: string
  scope_icon: MeetingScopeIcon | null
  body: string
  internal: boolean
  decisions: string[]
  todos: ReviewTodo[]
  review_note: string | null
}

export interface ReviewAttendee {
  name: string
  status: MeetingAttendanceStatus
  email: string | null
}

export interface MeetingNotesReviewState {
  /** The new meeting's name and place; null when the draft adds to a meeting. */
  newMeeting: { name: string; location: string; starts_at: string; ends_at: string; tags: string[] } | null
  attendees: ReviewAttendee[]
  people: Record<string, PersonChoice>
  cards: ReviewCard[]
  next_meeting_date: string | null
  next_meeting_time: string | null
  next_meeting_location: string | null
}

export function choiceOf(suggestion: PersonSuggestionResponse): PersonChoice {
  return `${suggestion.kind}:${suggestion.id}`
}

/** The form the review starts from: the draft as the agent sent it, each
 * name preselected as its best match, or as a guest when an attendee has
 * none, or left out when only a todo names it. */
export function initialReview(draft: MeetingNotesDraftResponse): MeetingNotesReviewState {
  const attendeeNames = new Set(draft.attendees.map((attendee) => attendee.name))
  const people: Record<string, PersonChoice> = {}
  for (const match of draft.people) {
    people[match.written] = match.best
      ? choiceOf(match.best)
      : attendeeNames.has(match.written)
        ? 'guest'
        : 'none'
  }
  const created = draft.new_meeting
  return {
    newMeeting: created
      ? {
          name: created.name,
          location: created.location ?? '',
          starts_at: created.starts_at,
          ends_at: created.ends_at,
          tags: [...created.tags],
        }
      : null,
    attendees: draft.attendees.map((attendee) => ({ ...attendee })),
    people,
    cards: draft.cards.map((card) => ({
      include: true,
      scope: card.scope ?? '',
      scope_icon: card.scope_icon,
      body: card.body,
      internal: card.internal,
      decisions: [...card.decisions],
      todos: card.todos.map((todo) => ({ ...todo, owners: [...todo.owners] })),
      review_note: card.review_note,
    })),
    next_meeting_date: draft.next_meeting_date,
    next_meeting_time: draft.next_meeting_time,
    next_meeting_location: draft.next_meeting_location,
  }
}

function parsed(choice: PersonChoice | undefined): { kind: 'user' | 'contact'; id: number } | null {
  if (!choice || choice === 'guest' || choice === 'none') return null
  const [kind, id] = choice.split(':')
  return { kind: kind as 'user' | 'contact', id: Number(id) }
}

function attendeeRequest(attendee: ReviewAttendee, choice: PersonChoice | undefined): MeetingAttendeeRequest | null {
  if (choice === 'guest') {
    return { kind: 'guest', status: attendee.status, name: attendee.name, email: attendee.email }
  }
  const person = parsed(choice)
  if (!person) return null
  return person.kind === 'user'
    ? { kind: 'user', status: attendee.status, user_id: person.id }
    : { kind: 'contact', status: attendee.status, contact_id: person.id }
}

function ownerRequests(owners: string[], people: Record<string, PersonChoice>): MeetingTodoOwnerRequest[] {
  const seen = new Set<string>()
  const result: MeetingTodoOwnerRequest[] = []
  for (const owner of owners) {
    const choice = people[owner]
    const person = parsed(choice)
    if (!person || !choice || seen.has(choice)) continue
    seen.add(choice)
    result.push(person.kind === 'user' ? { user_id: person.id } : { contact_id: person.id })
  }
  return result
}

/** Whether an owner written in the notes would be left out of its todo. */
export function ownerLeftOut(owner: string, people: Record<string, PersonChoice>): boolean {
  return parsed(people[owner]) === null
}

/** The request that applies the review: only the cards kept, the attendees
 * and owners as matched, a user or contact once even if the notes name
 * them twice. */
export function applyRequest(review: MeetingNotesReviewState): MeetingNotesDraftApplyRequest {
  const seen = new Set<string>()
  const attendees: MeetingAttendeeRequest[] = []
  for (const attendee of review.attendees) {
    const choice = review.people[attendee.name]
    const request = attendeeRequest(attendee, choice)
    if (!request) continue
    if (choice !== 'guest' && choice) {
      if (seen.has(choice)) continue
      seen.add(choice)
    }
    attendees.push(request)
  }
  const created = review.newMeeting
  return {
    new_meeting: created
      ? {
          name: created.name.trim(),
          location: created.location.trim() || null,
          starts_at: created.starts_at,
          ends_at: created.ends_at,
          tags: created.tags,
        }
      : null,
    attendees,
    cards: review.cards
      .filter((card) => card.include)
      .map((card) => ({
        scope: card.scope.trim() || null,
        scope_icon: card.scope_icon,
        body: card.body,
        internal: card.internal,
        decisions: card.decisions.map((text) => text.trim()).filter(Boolean),
        todos: card.todos
          .filter((todo) => todo.title.trim())
          .map((todo) => ({
            title: todo.title.trim(),
            note: todo.note?.trim() || null,
            due_date: todo.due_date,
            owners: ownerRequests(todo.owners, review.people),
          })),
      })),
    next_meeting_date: review.next_meeting_date,
    next_meeting_time: review.next_meeting_date ? review.next_meeting_time : null,
    next_meeting_location: review.next_meeting_date ? review.next_meeting_location : null,
  }
}
