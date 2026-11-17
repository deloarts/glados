import type {
  MeetingCardResponse,
  MeetingIssueResponse,
  MeetingListRowResponse,
  MeetingResponse,
  MeetingTodoResponse,
} from '../types/meetingResponse'

export const ANNA = {
  id: 2,
  public_id: '22222222-2222-2222-2222-222222222222',
  username: 'anna',
  full_name: 'Anna Generic',
  has_avatar: false,
}

export function makeTodo(overrides: Partial<MeetingTodoResponse> = {}): MeetingTodoResponse {
  return {
    id: 11,
    public_id: '00000000-0000-0000-0000-000000000011',
    meeting_id: 21,
    card_id: 1,
    position: 0,
    title: 'Send layout drawing rev. D',
    note: null,
    due_date: '2026-11-13',
    done: false,
    done_at: null,
    done_by: null,
    created: '2026-11-06T09:10:00Z',
    creator: ANNA,
    changed: null,
    owners: [{ user: ANNA, contact_id: null, name: 'Anna Generic' }],
    ...overrides,
  }
}

export function makeCard(overrides: Partial<MeetingCardResponse> = {}): MeetingCardResponse {
  return {
    id: 1,
    public_id: '00000000-0000-0000-0000-000000000101',
    meeting_id: 21,
    position: 0,
    scope: 'Vacuum gripper',
    scope_icon: 'mechanics',
    body: 'The cups show wear after **40,000 cycles**.',
    internal: false,
    created: '2026-11-06T09:04:00Z',
    creator: ANNA,
    changed: null,
    changed_by: null,
    edit_version: 3,
    decisions: [],
    todos: [],
    ...overrides,
  }
}

export function makeMeeting(overrides: Partial<MeetingResponse> = {}): MeetingResponse {
  return {
    id: 21,
    public_id: '00000000-0000-0000-0000-000000000021',
    meeting_number: 'MTG-26-0021',
    owner: { kind: 'project', id: 142, number: '26-0142', product_id: 31 },
    name: 'Design Review Gripper',
    starts_at: '2026-11-06T08:00:00Z',
    ends_at: '2026-11-06T09:30:00Z',
    location: 'Room Danube',
    next_meeting_date: null,
    next_meeting_time: null,
    next_meeting_location: null,
    follow_up_of: null,
    valid: true,
    invalid_at: null,
    invalid_by: null,
    invalid_reason: null,
    issue_number: 0,
    last_sent_at: null,
    last_printed_at: null,
    created: '2026-11-06T07:52:00Z',
    creator: ANNA,
    changed: null,
    changed_by: null,
    edit_version: 1,
    attendees: [
      {
        id: 5,
        public_id: '00000000-0000-0000-0000-000000000005',
        kind: 'user',
        status: 'present',
        position: 0,
        user: ANNA,
        contact_id: null,
        name: 'Anna Generic',
        email: 'anna.generic@example.com',
        anonymised: false,
      },
    ],
    tags: [],
    cards: [makeCard()],
    files: [],
    ...overrides,
  }
}

export function makeListRow(overrides: Partial<MeetingListRowResponse> = {}): MeetingListRowResponse {
  return {
    id: 21,
    public_id: '00000000-0000-0000-0000-000000000021',
    meeting_number: 'MTG-26-0021',
    owner: { kind: 'project', id: 142, number: '26-0142', product_id: 31 },
    name: 'Design Review Gripper',
    valid: true,
    starts_at: '2026-11-06T08:00:00Z',
    ends_at: '2026-11-06T09:30:00Z',
    location: 'Room Danube',
    scopes: [{ scope: 'Vacuum gripper', icon: 'mechanics', internal: false }],
    notes: 'The cups show wear after 40,000 cycles.',
    attendees: [{ kind: 'user', status: 'present', user_id: 2, name: 'Anna Generic' }],
    tags: [],
    open_todo_count: 0,
    overdue_todo_count: 0,
    sent: false,
    printed: false,
    ...overrides,
  }
}

export function makeIssue(overrides: Partial<MeetingIssueResponse> = {}): MeetingIssueResponse {
  return {
    issue_number: 0,
    last_sent_at: null,
    send: { issue_number: 1, draft: false, revision: '1' },
    print: { issue_number: 0, draft: true, revision: 'draft' },
    changed_card_ids: [],
    added_card_ids: [],
    removed_card_ids: [],
    ...overrides,
  }
}
