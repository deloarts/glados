import { describe, expect, it } from 'vitest'

import type {
  MeetingCardResponse,
  MeetingSnapshotCardResponse,
  MeetingSnapshotResponse,
} from '../types/meetingResponse'
import { compareSnapshot, countChanges } from '../utils/snapshotChanges'
import { ANNA, makeCard, makeMeeting, makeTodo } from './meetingFixtures'

function sentCard(card: MeetingCardResponse): MeetingSnapshotCardResponse {
  return {
    id: card.id,
    position: card.position,
    scope: card.scope,
    scope_icon: card.scope_icon,
    body: card.body,
    internal: card.internal,
    edit_version: card.edit_version,
    created: card.created,
    creator: card.creator,
    changed: card.changed,
    changed_by: card.changed_by,
    decisions: card.decisions.map((decision) => ({
      id: decision.id,
      card_id: decision.card_id,
      position: decision.position,
      text: decision.text,
      created: decision.created,
      creator: decision.creator,
    })),
    todos: card.todos.map((todo) => ({
      id: todo.id,
      card_id: todo.card_id,
      position: todo.position,
      title: todo.title,
      note: todo.note,
      due_date: todo.due_date,
      done: todo.done,
      done_at: todo.done_at,
      owners: todo.owners,
    })),
  }
}

function snapshot(cards: MeetingCardResponse[], options: Record<string, boolean> = {}): MeetingSnapshotResponse {
  return {
    id: 7,
    public_id: '00000000-0000-0000-0000-000000000007',
    meeting_id: 21,
    journal_entry_id: 70,
    kind: 'sent',
    created: '2026-11-06T10:00:00Z',
    actor: ANNA,
    issue: { issue_number: 1, draft: false, revision: '1' },
    language: 'enGB',
    options: { include_todos: true, include_internal: false, list_documents: true, ...options },
    byte_size: 1000,
    sha256: 'f'.repeat(64),
    meeting: {
      meeting_number: 'MTG-26-0021',
      name: 'Design Review Gripper',
      starts_at: '2026-11-06T08:00:00Z',
      ends_at: '2026-11-06T09:30:00Z',
      location: 'Room Danube',
      next_meeting_date: null,
      next_meeting_time: null,
      next_meeting_location: null,
      owner_kind: 'project',
      owner_id: 142,
      owner_number: '26-0142',
    },
    cards: cards.map(sentCard),
    attendees: [],
    files: [],
    attachments: [],
    recipients: ['thomas@muster.example'],
    cc: [],
    subject: 'Minutes',
  }
}

const DECISION = {
  id: 51,
  public_id: '00000000-0000-0000-0000-000000000051',
  meeting_id: 21,
  card_id: 1,
  position: 0,
  text: 'Switch to silicone cups',
  created: '2026-11-06T09:12:00Z',
  creator: ANNA,
}

const GRIPPER = makeCard({ id: 1, position: 0, body: 'Line one\nLine two', todos: [makeTodo({ id: 11 })], decisions: [DECISION] })
const SCHEDULE = makeCard({ id: 2, position: 1, scope: 'Schedule', scope_icon: 'schedule', body: 'Week 48' })
const PRICING = makeCard({ id: 3, position: 2, scope: 'Pricing', scope_icon: 'commercial', internal: true, body: 'Margin' })

describe('compareSnapshot', () => {
  it('finds nothing changed when the notes are as they were sent', () => {
    const comparison = compareSnapshot(snapshot([GRIPPER, SCHEDULE]), makeMeeting({ cards: [GRIPPER, SCHEDULE] }))

    expect(comparison.cards.map((card) => [card.cardId, card.status])).toEqual([
      [1, 'unchanged'],
      [2, 'unchanged'],
    ])
    expect(countChanges(comparison)).toEqual({ added: 0, removed: 0, changed: 0 })
  })

  it('names a changed text with its line diff, and a changed scope and icon with what they were', () => {
    const now = makeMeeting({
      cards: [
        { ...GRIPPER, body: 'Line one\nLine 2' },
        { ...SCHEDULE, scope: 'Milestones', scope_icon: 'risk' },
      ],
    })

    const [gripper, schedule] = compareSnapshot(snapshot([GRIPPER, SCHEDULE]), now).cards

    expect(gripper?.status).toBe('changed')
    expect(gripper?.body).toEqual([
      { kind: 'same', text: 'Line one' },
      { kind: 'removed', text: 'Line two' },
      { kind: 'added', text: 'Line 2' },
    ])
    expect(schedule).toMatchObject({
      status: 'changed',
      bodyChanged: false,
      scopeChange: { from: 'Schedule', to: 'Milestones' },
      iconChange: { from: 'schedule', to: 'risk' },
    })
  })

  it('counts a new card as added and a deleted one as removed, after the cards of today', () => {
    const added = makeCard({ id: 4, position: 3, scope: 'Safety', body: 'Fence' })
    const comparison = compareSnapshot(snapshot([GRIPPER, SCHEDULE]), makeMeeting({ cards: [GRIPPER, added] }))

    expect(comparison.cards.map((card) => [card.cardId, card.status])).toEqual([
      [1, 'unchanged'],
      [4, 'added'],
      [2, 'removed'],
    ])
    expect(comparison.cards[1]?.body).toEqual([{ kind: 'added', text: 'Fence' }])
    expect(comparison.cards[2]?.body).toEqual([{ kind: 'removed', text: 'Week 48' }])
  })

  it('counts new todos and changed decisions, but not a todo ticked off', () => {
    const now = makeMeeting({
      cards: [
        {
          ...GRIPPER,
          todos: [{ ...makeTodo({ id: 11 }), done: true }, makeTodo({ id: 12, title: 'Order spares' })],
          decisions: [{ ...DECISION, text: 'Switch to rubber cups' }],
        },
        { ...SCHEDULE, todos: [] },
      ],
    })
    const ticked = makeMeeting({ cards: [{ ...GRIPPER, todos: [{ ...makeTodo({ id: 11 }), done: true }] }, SCHEDULE] })

    const [gripper] = compareSnapshot(snapshot([GRIPPER, SCHEDULE]), now).cards

    expect(gripper?.status).toBe('changed')
    expect(gripper?.todosAdded.map((todo) => todo.title)).toEqual(['Order spares'])
    expect(gripper?.decisionsAdded).toEqual(['Switch to rubber cups'])
    expect(gripper?.decisionsRemoved).toEqual(['Switch to silicone cups'])
    expect(compareSnapshot(snapshot([GRIPPER, SCHEDULE]), ticked).cards[0]?.status).toBe('unchanged')
  })

  it('leaves internal cards out of the comparison when the snapshot left them out', () => {
    const comparison = compareSnapshot(snapshot([GRIPPER]), makeMeeting({ cards: [GRIPPER, PRICING] }))

    expect(comparison.cards.map((card) => card.cardId)).toEqual([1])
    expect(comparison.internalLeftOut).toBe(1)
  })

  it('compares the internal cards a snapshot included, and a card turned internal since', () => {
    const included = compareSnapshot(
      snapshot([GRIPPER], { include_internal: true }),
      makeMeeting({ cards: [GRIPPER, PRICING] }),
    )
    const turned = compareSnapshot(snapshot([GRIPPER]), makeMeeting({ cards: [{ ...GRIPPER, internal: true }] }))

    expect(included.cards.map((card) => [card.cardId, card.status])).toEqual([
      [1, 'unchanged'],
      [3, 'added'],
    ])
    expect(included.internalLeftOut).toBe(0)
    expect(turned.cards[0]).toMatchObject({ status: 'changed', internalChange: { from: false, to: true } })
  })

  it('does not count new todos when the snapshot left the todos out', () => {
    const sent = snapshot([{ ...GRIPPER, todos: [] }], { include_todos: false })
    const comparison = compareSnapshot(sent, makeMeeting({ cards: [GRIPPER] }))

    expect(comparison.withTodos).toBe(false)
    expect(comparison.cards[0]).toMatchObject({ status: 'unchanged', todosAdded: [] })
  })
})
