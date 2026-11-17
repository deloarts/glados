import type {
  MeetingCardResponse,
  MeetingDecisionResponse,
  MeetingResponse,
  MeetingScopeIcon,
  MeetingSnapshotCardResponse,
  MeetingSnapshotDecisionResponse,
  MeetingSnapshotResponse,
  MeetingTodoResponse,
} from '../types/meetingResponse'
import { lineDiff } from './lineDiff'
import type { DiffLine } from './lineDiff'

/**
 * Changes Since: a snapshot of a print, download or send compared with the
 * notes as they are now, card by card. A card is added, removed, changed or
 * unchanged by the rules the server tags Changed After Sending with: its
 * text, scope, icon or internal flag changed, its decisions changed, or it
 * got a todo the snapshot did not have while the snapshot contained todos.
 * Ticking a todo off is no change. Internal cards a snapshot left out are
 * left out of the comparison too, so they never count as added.
 */

export type CardChangeStatus = 'added' | 'removed' | 'changed' | 'unchanged'

export interface ValueChange<T> {
  from: T
  to: T
}

export interface CardChange {
  cardId: number
  status: CardChangeStatus
  /** The card as it is now, or as the snapshot had it once it was removed. */
  scope: string | null
  scopeIcon: MeetingScopeIcon | null
  internal: boolean
  /** The line diff of the text from the snapshot to now; every line added for a new card, removed for a deleted one. */
  body: DiffLine[]
  bodyChanged: boolean
  scopeChange: ValueChange<string | null> | null
  iconChange: ValueChange<MeetingScopeIcon | null> | null
  internalChange: ValueChange<boolean> | null
  decisionsAdded: string[]
  decisionsRemoved: string[]
  /** The todos the card got since, when the snapshot contained todos. */
  todosAdded: MeetingTodoResponse[]
}

export interface SnapshotComparison {
  cards: CardChange[]
  /** The internal cards of today left out, since the snapshot left internal cards out. */
  internalLeftOut: number
  /** Whether the snapshot contained todos, which is what makes new todos count. */
  withTodos: boolean
}

function option(snapshot: MeetingSnapshotResponse, key: string, fallback: boolean): boolean {
  return snapshot.options[key] ?? fallback
}

function decisionKey(decision: MeetingDecisionResponse | MeetingSnapshotDecisionResponse): string {
  return `${decision.position}:${decision.id}:${decision.text}`
}

function sortedKeys(decisions: (MeetingDecisionResponse | MeetingSnapshotDecisionResponse)[]): string[] {
  return decisions.map(decisionKey).sort()
}

function texts(decisions: (MeetingDecisionResponse | MeetingSnapshotDecisionResponse)[], without: Set<number>): string[] {
  return [...decisions]
    .sort((a, b) => a.position - b.position || a.id - b.id)
    .filter((decision) => !without.has(decision.id))
    .map((decision) => decision.text)
}

function change<T>(from: T, to: T): ValueChange<T> | null {
  return from === to ? null : { from, to }
}

function compareCard(sent: MeetingSnapshotCardResponse, card: MeetingCardResponse, withTodos: boolean): CardChange {
  const sentTodoIds = new Set(sent.todos.map((todo) => todo.id))
  const todosAdded = withTodos ? card.todos.filter((todo) => !sentTodoIds.has(todo.id)) : []
  // A decision whose text changed reads as the old one removed and the new one added.
  const keep = new Set(
    card.decisions
      .filter((decision) =>
        sent.decisions.some((before) => before.id === decision.id && before.text === decision.text),
      )
      .map((decision) => decision.id),
  )
  const decisionsAdded = texts(card.decisions, keep)
  const decisionsRemoved = texts(sent.decisions, keep)
  const decisionsChanged = sortedKeys(card.decisions).join('\n') !== sortedKeys(sent.decisions).join('\n')
  const scopeChange = change(sent.scope, card.scope)
  const iconChange = change(sent.scope_icon, card.scope_icon)
  const internalChange = change(sent.internal, card.internal)
  const bodyChanged = sent.body !== card.body
  const changed =
    bodyChanged || !!scopeChange || !!iconChange || !!internalChange || decisionsChanged || todosAdded.length > 0
  return {
    cardId: card.id,
    status: changed ? 'changed' : 'unchanged',
    scope: card.scope,
    scopeIcon: card.scope_icon,
    internal: card.internal,
    body: lineDiff(sent.body, card.body),
    bodyChanged,
    scopeChange,
    iconChange,
    internalChange,
    decisionsAdded,
    decisionsRemoved,
    todosAdded,
  }
}

function addedCard(card: MeetingCardResponse, withTodos: boolean): CardChange {
  return {
    cardId: card.id,
    status: 'added',
    scope: card.scope,
    scopeIcon: card.scope_icon,
    internal: card.internal,
    body: lineDiff('', card.body),
    bodyChanged: true,
    scopeChange: null,
    iconChange: null,
    internalChange: null,
    decisionsAdded: texts(card.decisions, new Set()),
    decisionsRemoved: [],
    todosAdded: withTodos ? [...card.todos] : [],
  }
}

function removedCard(sent: MeetingSnapshotCardResponse): CardChange {
  return {
    cardId: sent.id,
    status: 'removed',
    scope: sent.scope,
    scopeIcon: sent.scope_icon,
    internal: sent.internal,
    body: lineDiff(sent.body, ''),
    bodyChanged: true,
    scopeChange: null,
    iconChange: null,
    internalChange: null,
    decisionsAdded: [],
    decisionsRemoved: texts(sent.decisions, new Set()),
    todosAdded: [],
  }
}

/** The snapshot compared with the meeting now: today's cards in their order, then the removed ones. */
export function compareSnapshot(snapshot: MeetingSnapshotResponse, meeting: MeetingResponse): SnapshotComparison {
  const withTodos = option(snapshot, 'include_todos', true)
  const withInternal = option(snapshot, 'include_internal', false)
  const sent = new Map(snapshot.cards.map((card) => [card.id, card]))
  const ordered = [...meeting.cards].sort((a, b) => a.position - b.position || a.id - b.id)
  const cards: CardChange[] = []
  let internalLeftOut = 0
  for (const card of ordered) {
    const before = sent.get(card.id)
    if (before) {
      cards.push(compareCard(before, card, withTodos))
    } else if (card.internal && !withInternal) {
      internalLeftOut += 1
    } else {
      cards.push(addedCard(card, withTodos))
    }
  }
  const current = new Set(meeting.cards.map((card) => card.id))
  const removed = [...snapshot.cards]
    .sort((a, b) => a.position - b.position || a.id - b.id)
    .filter((card) => !current.has(card.id))
    .map(removedCard)
  return { cards: [...cards, ...removed], internalLeftOut, withTodos }
}

/** How many cards differ from the snapshot, for a summary line. */
export function countChanges(comparison: SnapshotComparison): Record<Exclude<CardChangeStatus, 'unchanged'>, number> {
  const counts = { added: 0, removed: 0, changed: 0 }
  for (const card of comparison.cards) if (card.status !== 'unchanged') counts[card.status] += 1
  return counts
}
