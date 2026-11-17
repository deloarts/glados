import { describe, expect, it } from 'vitest'

import { applyRequest, initialReview, ownerLeftOut } from '../utils/meetingNotesDraft'
import { makeDraft } from './meetingNotesDraftFixtures'

describe('meeting notes draft review', () => {
  it('preselects the best match, a guest for an unmatched attendee and nobody for an unmatched owner', () => {
    const review = initialReview(makeDraft())

    expect(review.people).toEqual({ 'Hans M.': 'user:7', Erika: 'guest', 'H. Müller': 'user:7', Paul: 'none' })
    expect(ownerLeftOut('Paul', review.people)).toBe(true)
    expect(ownerLeftOut('Hans M.', review.people)).toBe(false)
  })

  it('applies the kept cards with attendees and owners as matched, a person only once', () => {
    const review = initialReview(makeDraft())
    review.cards[1]!.include = false

    const request = applyRequest(review)

    expect(request.attendees).toEqual([
      { kind: 'user', status: 'present', user_id: 7 },
      { kind: 'guest', status: 'excused', name: 'Erika', email: 'erika@example.com' },
    ])
    expect(request.cards).toHaveLength(1)
    expect(request.cards[0]).toMatchObject({
      scope: 'Cabinet',
      scope_icon: 'electrical',
      decisions: ['Use 800 mm'],
      todos: [{ title: 'Send layout', due_date: '2026-11-20', owners: [{ user_id: 7 }] }],
    })
    expect(request.new_meeting).toMatchObject({ name: 'Kick-off cabinet', location: null })
  })

  it('leaves out a person matched to nobody and drops the next meeting time without its date', () => {
    const review = initialReview(makeDraft())
    review.people.Erika = 'none'

    const request = applyRequest(review)

    expect(request.attendees?.map((a) => a.kind)).toEqual(['user'])
    expect(request.next_meeting_time).toBeNull()
    expect(request.next_meeting_location).toBeNull()
  })

  it('sends no new meeting for a draft that adds to a meeting', () => {
    const review = initialReview(makeDraft({ meeting_id: 21, meeting_number: 'MTG-26-0001', new_meeting: null }))

    expect(applyRequest(review).new_meeting).toBeNull()
  })
})
