import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'

import { cardDraftKey, cardDraftState, clearCardDraft, readCardDraft, writeCardDraft } from '../utils/cardDraft'
import { makeCard } from './meetingFixtures'
import type { MeetingCardResponse } from '../types/meetingResponse'
import type { MeetingCardUpdateRequest } from '../types/meetingRequest'

const updateMeetingCard = vi.fn<(meetingId: number, cardId: number, body: MeetingCardUpdateRequest) => Promise<MeetingCardResponse>>()
const getMeetingCard = vi.fn<(meetingId: number, cardId: number) => Promise<MeetingCardResponse>>()
vi.mock('../api/meetingsApi', () => ({
  updateMeetingCard: (meetingId: number, cardId: number, body: MeetingCardUpdateRequest) =>
    updateMeetingCard(meetingId, cardId, body),
  getMeetingCard: (meetingId: number, cardId: number) => getMeetingCard(meetingId, cardId),
}))

import { useCardEditing } from '../composables/useCardEditing'

const DRAFT = { editVersion: 3, body: 'Draft text', internal: false, savedAt: '2026-11-10T09:00:00Z' }

function conflict(): Error {
  return Object.assign(new Error('Conflict'), { isAxiosError: true, response: { status: 409, data: {} } })
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('card drafts in the browser', () => {
  it('stores, reads and clears a draft per card', () => {
    expect(writeCardDraft(1, DRAFT)).toBe(true)

    expect(readCardDraft(1)).toEqual(DRAFT)
    expect(readCardDraft(2)).toBeNull()
    clearCardDraft(1)
    expect(readCardDraft(1)).toBeNull()
  })

  it('reads nothing from a broken or foreign value', () => {
    localStorage.setItem(cardDraftKey(1), '{not json')
    localStorage.setItem(cardDraftKey(2), JSON.stringify({ body: 'no version' }))

    expect(readCardDraft(1)).toBeNull()
    expect(readCardDraft(2)).toBeNull()
  })

  it('keeps nothing when storage refuses the write', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })

    expect(writeCardDraft(1, DRAFT)).toBe(false)
    spy.mockRestore()
  })

  it('offers a draft of the same version back and a draft of an older version for merging', () => {
    const card = makeCard({ edit_version: 3, body: 'Saved text' })

    expect(cardDraftState(card, null)).toBe('none')
    expect(cardDraftState(card, DRAFT)).toBe('restorable')
    expect(cardDraftState(makeCard({ edit_version: 4, body: 'Saved text' }), DRAFT)).toBe('stale')
    expect(cardDraftState(makeCard({ body: 'Draft text' }), DRAFT)).toBe('none')
  })
})

describe('useCardEditing', () => {
  function setup(card: MeetingCardResponse = makeCard({ edit_version: 3, body: 'Saved text' })) {
    const current = ref(card)
    const saved = vi.fn<(card: MeetingCardResponse) => void>()
    const scope = effectScope()
    const editing = scope.run(() =>
      useCardEditing({ meetingId: () => 21, card: () => current.value, onSaved: saved }),
    )!
    return { editing, current, saved, scope }
  }

  it('keeps the text being written as a draft against the version it started from', async () => {
    vi.useFakeTimers()
    const { editing, scope } = setup()

    editing.start()
    editing.body.value = 'Typed text'
    await nextTick()
    vi.advanceTimersByTime(900)

    expect(readCardDraft(1)).toMatchObject({ editVersion: 3, body: 'Typed text', internal: false })
    scope.stop()
  })

  it('clears the draft once the card is saved', async () => {
    vi.useFakeTimers()
    const { editing, saved, scope } = setup()
    const result = makeCard({ edit_version: 4, body: 'Typed text' })
    updateMeetingCard.mockResolvedValue(result)

    editing.start()
    editing.body.value = 'Typed text'
    await nextTick()
    vi.advanceTimersByTime(900)
    await editing.save()

    expect(updateMeetingCard).toHaveBeenCalledWith(21, 1, {
      scope: 'Vacuum gripper',
      scope_icon: 'mechanics',
      body: 'Typed text',
      internal: false,
      expected_edit_version: 3,
    })
    expect(saved).toHaveBeenCalledWith(result)
    expect(readCardDraft(1)).toBeNull()
    expect(editing.editing.value).toBe(false)
    scope.stop()
  })

  it('restores a draft found after a reload', () => {
    writeCardDraft(1, DRAFT)
    const { editing, scope } = setup()

    expect(editing.draftState.value).toBe('restorable')
    editing.restoreDraft()

    expect(editing.editing.value).toBe(true)
    expect(editing.body.value).toBe('Draft text')
    scope.stop()
  })

  it('offers a stale draft for merging with the text saved since', () => {
    writeCardDraft(1, DRAFT)
    const { editing, scope } = setup(makeCard({ edit_version: 5, body: 'Their newer text' }))

    expect(editing.draftState.value).toBe('stale')
    editing.mergeDraft()

    expect(editing.merge).toMatchObject({ visible: true, theirs: 'Their newer text', theirVersion: 5, mine: 'Draft text' })
    scope.stop()
  })

  it('opens the merge with the newer text when the save clashes', async () => {
    const { editing, scope } = setup()
    updateMeetingCard.mockRejectedValueOnce(conflict())
    getMeetingCard.mockResolvedValue(makeCard({ edit_version: 4, body: 'Their text' }))

    editing.start()
    editing.body.value = 'My text'
    expect(await editing.save()).toBe(false)

    expect(editing.merge).toMatchObject({ visible: true, theirs: 'Their text', theirVersion: 4, mine: 'My text' })
    expect(editing.editing.value).toBe(true)

    updateMeetingCard.mockResolvedValue(makeCard({ edit_version: 5, body: 'Merged' }))
    expect(await editing.saveMerged('Merged')).toBe(true)
    expect(updateMeetingCard).toHaveBeenLastCalledWith(21, 1, expect.objectContaining({ body: 'Merged', expected_edit_version: 4 }))
    expect(editing.merge.visible).toBe(false)
    scope.stop()
  })

  it('takes a newer version with the same text, such as a scope change, as its base', async () => {
    const { editing, current, scope } = setup()
    updateMeetingCard.mockResolvedValue(makeCard({ edit_version: 5 }))

    editing.start()
    current.value = makeCard({ edit_version: 4, body: 'Saved text', scope: 'Renamed' })
    await nextTick()
    await editing.save()

    expect(updateMeetingCard).toHaveBeenLastCalledWith(21, 1, expect.objectContaining({ scope: 'Renamed', expected_edit_version: 4 }))
    scope.stop()
  })
})
