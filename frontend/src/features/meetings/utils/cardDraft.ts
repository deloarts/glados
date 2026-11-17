import { safeStorage } from '@/core/utils/safeStorage'

/**
 * The unsaved text of a card kept in the browser while it is edited, so a
 * reload or a lost connection does not lose it. The draft records the card's
 * `edit_version` it was written against: on that same version it can be
 * restored as it is, and on a later one someone saved the card meanwhile, so
 * it is offered for merging instead.
 */
export interface CardDraft {
  editVersion: number
  body: string
  internal: boolean
  savedAt: string
}

export type CardDraftState = 'none' | 'restorable' | 'stale'

const PREFIX = 'glados.meetings.cardDraft.'

export function cardDraftKey(cardId: number): string {
  return `${PREFIX}${cardId}`
}

function isDraft(value: unknown): value is CardDraft {
  if (typeof value !== 'object' || value === null) return false
  const draft = value as Record<string, unknown>
  return (
    typeof draft.editVersion === 'number' &&
    typeof draft.body === 'string' &&
    typeof draft.internal === 'boolean' &&
    typeof draft.savedAt === 'string'
  )
}

export function readCardDraft(cardId: number): CardDraft | null {
  const raw = safeStorage.get(cardDraftKey(cardId))
  if (!raw) return null
  try {
    const parsed: unknown = JSON.parse(raw)
    return isDraft(parsed) ? parsed : null
  } catch {
    return null
  }
}

/** Whether the draft was stored; a full or blocked storage keeps nothing. */
export function writeCardDraft(cardId: number, draft: CardDraft): boolean {
  try {
    return safeStorage.set(cardDraftKey(cardId), JSON.stringify(draft))
  } catch {
    return false
  }
}

export function clearCardDraft(cardId: number): void {
  safeStorage.remove(cardDraftKey(cardId))
}

/** What a stored draft means for the card as it is now. */
export function cardDraftState(
  card: { edit_version: number; body: string; internal: boolean },
  draft: CardDraft | null,
): CardDraftState {
  if (!draft) return 'none'
  if (draft.body === card.body && draft.internal === card.internal) return 'none'
  return draft.editVersion === card.edit_version ? 'restorable' : 'stale'
}
