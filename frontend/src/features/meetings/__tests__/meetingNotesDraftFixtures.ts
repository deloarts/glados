import type { MeetingNotesDraftResponse } from '../types/meetingNotesDraft'

/** A draft of a new meeting of project 26-0142 with two cards and four names. */
export function makeDraft(overrides: Partial<MeetingNotesDraftResponse> = {}): MeetingNotesDraftResponse {
  return {
    id: 5,
    public_id: '00000000-0000-0000-0000-000000000005',
    created: '2026-11-12T10:00:00Z',
    token_name: 'Notebook agent',
    meeting_id: null,
    meeting_number: null,
    meeting_name: null,
    project_id: 142,
    product_id: null,
    owner_number: '26-0142',
    name: 'Kick-off cabinet',
    starts_at: '2026-11-10T09:00:00Z',
    card_count: 2,
    decision_count: 1,
    todo_count: 1,
    review_note: null,
    new_meeting: {
      name: 'Kick-off cabinet',
      starts_at: '2026-11-10T09:00:00Z',
      ends_at: '2026-11-10T11:00:00Z',
      location: null,
      tags: [],
    },
    attendees: [
      { name: 'Hans M.', status: 'present', email: null },
      { name: 'Erika', status: 'excused', email: 'erika@example.com' },
      { name: 'H. Müller', status: 'present', email: null },
    ],
    cards: [
      {
        scope: 'Cabinet',
        scope_icon: 'electrical',
        body: 'Layout agreed.',
        internal: false,
        decisions: ['Use 800 mm', '  '],
        todos: [{ title: 'Send layout', note: null, due_date: '2026-11-20', owners: ['Hans M.', 'Paul'] }],
        review_note: 'Second line unreadable',
      },
      {
        scope: null,
        scope_icon: null,
        body: 'Coffee',
        internal: false,
        decisions: [],
        todos: [],
        review_note: null,
      },
    ],
    next_meeting_date: null,
    next_meeting_time: '10:00:00',
    next_meeting_location: 'Room 2',
    people: [
      { written: 'Hans M.', candidates: [{ kind: 'user', id: 7, name: 'Hans Müller' }], best: { kind: 'user', id: 7, name: 'Hans Müller' } },
      { written: 'Erika', candidates: [], best: null },
      { written: 'H. Müller', candidates: [{ kind: 'user', id: 7, name: 'Hans Müller' }], best: { kind: 'user', id: 7, name: 'Hans Müller' } },
      { written: 'Paul', candidates: [], best: null },
    ],
    ...overrides,
  }
}
