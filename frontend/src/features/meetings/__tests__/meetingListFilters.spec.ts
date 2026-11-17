import { describe, it, expect } from 'vitest'

import { makeListRow } from './meetingFixtures'
import { emptyMeetingListFilters, filterMeetingRows, hasMeetingListFilters } from '../utils/meetingListFilters'
import type { MeetingListFilters } from '../utils/meetingListFilters'

const REVIEW = makeListRow({ id: 1, sent: true, open_todo_count: 2, overdue_todo_count: 1 })
const SURVEY = makeListRow({
  id: 2,
  meeting_number: 'MTG-26-0015',
  name: 'Site Survey Fence',
  starts_at: '2026-10-21T08:00:00Z',
  location: 'Customer site',
  notes: 'Fence posts need new anchors.',
  scopes: [{ scope: 'Fence, north door', icon: 'commercial', internal: false }],
  attendees: [{ kind: 'contact', status: 'present', user_id: null, name: 'Thomas Muster' }],
  owner: { kind: 'product', id: 31, number: 'PR-0031', product_id: null },
  valid: false,
  printed: true,
})
const ROWS = [REVIEW, SURVEY]

function ids(filters: Partial<MeetingListFilters>): number[] {
  return filterMeetingRows(ROWS, { ...emptyMeetingListFilters(), ...filters }).map((row) => row.id)
}

describe('filterMeetingRows', () => {
  it('keeps every row without a filter', () => {
    expect(ids({})).toEqual([1, 2])
    expect(hasMeetingListFilters(emptyMeetingListFilters())).toBe(false)
  })

  it('filters by status and by open todos', () => {
    expect(ids({ status: 'sent' })).toEqual([1])
    expect(ids({ status: 'notSent' })).toEqual([2])
    expect(ids({ status: 'printed' })).toEqual([2])
    expect(ids({ status: 'invalid' })).toEqual([2])
    expect(ids({ todos: 'overdue' })).toEqual([1])
    expect(ids({ todos: 'none' })).toEqual([2])
  })

  it('filters by a day or a range of days', () => {
    expect(ids({ dates: [new Date(2026, 10, 6), null] })).toEqual([1])
    expect(ids({ dates: [new Date(2026, 9, 1), new Date(2026, 9, 31)] })).toEqual([2])
  })

  it('searches the name with the number, the scopes, the notes and the location, in any case', () => {
    expect(ids({ name: 'mtg-26-0015' })).toEqual([2])
    expect(ids({ name: 'gripper' })).toEqual([1])
    expect(ids({ scope: 'north' })).toEqual([2])
    expect(ids({ notes: 'ANCHORS' })).toEqual([2])
    expect(ids({ location: 'danube' })).toEqual([1])
  })

  it('filters by owner and by any of the picked attendees', () => {
    expect(ids({ owners: ['product'] })).toEqual([2])
    expect(ids({ owners: ['142'] })).toEqual([1])
    expect(ids({ attendees: ['Thomas Muster', 'Nobody'] })).toEqual([2])
    expect(hasMeetingListFilters({ ...emptyMeetingListFilters(), attendees: ['Anna Generic'] })).toBe(true)
  })
})
