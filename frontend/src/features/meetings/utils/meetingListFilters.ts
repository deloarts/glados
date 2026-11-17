import { toDayKey } from '@/core/utils/dates'
import type { MeetingListRowResponse } from '../types/meetingResponse'

/**
 * The column filters of the Meeting Notes table. The list of one project or
 * product comes whole from the server, so the table filters it here and
 * every filter answers at once; only the tag goes to the server.
 */

export type MeetingStatusFilter = 'sent' | 'notSent' | 'printed' | 'notPrinted' | 'invalid'
export type MeetingTodoFilter = 'open' | 'overdue' | 'none'

export const MEETING_STATUS_FILTERS: MeetingStatusFilter[] = ['sent', 'notSent', 'printed', 'notPrinted', 'invalid']
export const MEETING_TODO_FILTERS: MeetingTodoFilter[] = ['open', 'overdue', 'none']

/** The key of the product itself among the owners a product's list offers. */
export const PRODUCT_OWNER_KEY = 'product'

export interface MeetingListFilters {
  status: MeetingStatusFilter | null
  /** A day or a range of days, as the range DatePicker gives it. */
  dates: (Date | null)[] | null
  /** Owner keys: PRODUCT_OWNER_KEY or a project's id as a string. */
  owners: string[]
  scope: string
  name: string
  notes: string
  todos: MeetingTodoFilter | null
  /** Attendee names, any of which a meeting must have. */
  attendees: string[]
  location: string
}

export function emptyMeetingListFilters(): MeetingListFilters {
  return {
    status: null,
    dates: null,
    owners: [],
    scope: '',
    name: '',
    notes: '',
    todos: null,
    attendees: [],
    location: '',
  }
}

export function hasMeetingListFilters(filters: MeetingListFilters): boolean {
  return (
    !!filters.status ||
    !!filters.dates?.some(Boolean) ||
    filters.owners.length > 0 ||
    !!filters.scope.trim() ||
    !!filters.name.trim() ||
    !!filters.notes.trim() ||
    !!filters.todos ||
    filters.attendees.length > 0 ||
    !!filters.location.trim()
  )
}

export function ownerKey(row: MeetingListRowResponse): string {
  return row.owner.kind === 'product' ? PRODUCT_OWNER_KEY : String(row.owner.id)
}

function contains(value: string | null | undefined, query: string): boolean {
  const wanted = query.trim().toLocaleLowerCase()
  return !wanted || (value ?? '').toLocaleLowerCase().includes(wanted)
}

function localDayKey(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

/** Whether the meeting's day falls in the picked day or range; an open end is no limit. */
function inDates(row: MeetingListRowResponse, dates: MeetingListFilters['dates']): boolean {
  const [from, to] = dates ?? []
  if (!from) return true
  const day = toDayKey(row.starts_at)
  // A single picked day, before the range is closed, is that day alone.
  const end = to ?? from
  return day >= localDayKey(from) && day <= localDayKey(end)
}

function matchesStatus(row: MeetingListRowResponse, status: MeetingStatusFilter | null): boolean {
  switch (status) {
    case 'sent':
      return row.sent
    case 'notSent':
      return !row.sent
    case 'printed':
      return row.printed
    case 'notPrinted':
      return !row.printed
    case 'invalid':
      return !row.valid
    default:
      return true
  }
}

function matchesTodos(row: MeetingListRowResponse, todos: MeetingTodoFilter | null): boolean {
  if (todos === 'open') return row.open_todo_count > 0
  if (todos === 'overdue') return row.overdue_todo_count > 0
  if (todos === 'none') return row.open_todo_count === 0
  return true
}

/** The rows that pass every column filter. */
export function filterMeetingRows(rows: MeetingListRowResponse[], filters: MeetingListFilters): MeetingListRowResponse[] {
  return rows.filter(
    (row) =>
      matchesStatus(row, filters.status) &&
      inDates(row, filters.dates) &&
      (!filters.owners.length || filters.owners.includes(ownerKey(row))) &&
      (!filters.scope.trim() || row.scopes.some((chip) => contains(chip.scope, filters.scope))) &&
      (contains(row.name, filters.name) || contains(row.meeting_number, filters.name)) &&
      contains(row.notes, filters.notes) &&
      matchesTodos(row, filters.todos) &&
      (!filters.attendees.length || row.attendees.some((attendee) => filters.attendees.includes(attendee.name))) &&
      contains(row.location, filters.location),
  )
}

/** The attendee names of the rows, for the Attendees filter, in alphabetical order. */
export function attendeeNames(rows: MeetingListRowResponse[]): string[] {
  const names = new Set(rows.flatMap((row) => row.attendees.map((attendee) => attendee.name).filter(Boolean)))
  return [...names].sort((a, b) => a.localeCompare(b))
}
