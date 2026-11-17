import { computed, onScopeDispose, reactive, ref, watch } from 'vue'

import { apiErrorStatus } from '@/core/utils/errors'
import { getMeetingCard, updateMeetingCard } from '../api/meetingsApi'
import { cardDraftState, clearCardDraft, readCardDraft, writeCardDraft } from '../utils/cardDraft'
import type { CardDraft } from '../utils/cardDraft'
import type { MeetingCardResponse } from '../types/meetingResponse'

const AUTOSAVE_MS = 800

export interface CardMergeState {
  visible: boolean
  /** The card's text as someone else saved it. */
  theirs: string
  theirVersion: number
  /** The text the user wrote. */
  mine: string
}

/**
 * Editing one card: the text and the internal flag being written, the
 * card's `edit_version` they were started from, the draft kept in the
 * browser while typing, the save with its version check, and the merge when
 * someone else saved the card first. Each card saves on its own, so several
 * people can write different cards at once.
 */
export function useCardEditing(options: {
  meetingId: () => number
  card: () => MeetingCardResponse
  onSaved: (card: MeetingCardResponse) => void
}) {
  const cardId = () => options.card().id

  const editing = ref(false)
  const body = ref('')
  const internal = ref(false)
  const saving = ref(false)
  const error = ref<unknown>(null)
  // What the user started from: a save expects this version, and a later
  // version with the same text, such as a scope change, is no conflict.
  const baseVersion = ref(0)
  const baseBody = ref('')

  const storedDraft = ref<CardDraft | null>(readCardDraft(cardId()))
  const draftState = computed(() => (editing.value ? 'none' : cardDraftState(options.card(), storedDraft.value)))

  const merge = reactive<CardMergeState>({ visible: false, theirs: '', theirVersion: 0, mine: '' })

  function begin(text: string, isInternal: boolean, version: number, from: string): void {
    body.value = text
    internal.value = isInternal
    baseVersion.value = version
    baseBody.value = from
    error.value = null
    editing.value = true
  }

  function start(): void {
    const card = options.card()
    begin(card.body, card.internal, card.edit_version, card.body)
  }

  function discardDraft(): void {
    clearCardDraft(cardId())
    storedDraft.value = null
  }

  function stop(): void {
    editing.value = false
    merge.visible = false
    discardDraft()
  }

  /** Continues the draft found after a reload, on the version it was written against. */
  function restoreDraft(): void {
    const draft = storedDraft.value
    const card = options.card()
    if (!draft) return
    begin(draft.body, draft.internal, card.edit_version, card.body)
  }

  /** A draft written against an older version: the merge dialog shows both texts. */
  function mergeDraft(): void {
    const draft = storedDraft.value
    const card = options.card()
    if (!draft) return
    begin(draft.body, draft.internal, card.edit_version, card.body)
    openMerge(card)
  }

  function openMerge(card: MeetingCardResponse): void {
    merge.theirs = card.body
    merge.theirVersion = card.edit_version
    merge.mine = body.value
    merge.visible = true
  }

  let timer: ReturnType<typeof setTimeout> | null = null
  function scheduleDraft(): void {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      if (!editing.value) return
      const draft: CardDraft = {
        editVersion: baseVersion.value,
        body: body.value,
        internal: internal.value,
        savedAt: new Date().toISOString(),
      }
      if (writeCardDraft(cardId(), draft)) storedDraft.value = draft
    }, AUTOSAVE_MS)
  }

  watch([body, internal], () => {
    if (editing.value) scheduleDraft()
  })

  watch(
    () => options.card(),
    (card) => {
      if (editing.value && card.edit_version !== baseVersion.value && card.body === baseBody.value) {
        baseVersion.value = card.edit_version
      }
    },
  )

  onScopeDispose(() => {
    if (timer) clearTimeout(timer)
  })

  async function put(text: string, version: number): Promise<MeetingCardResponse> {
    const card = options.card()
    return updateMeetingCard(options.meetingId(), card.id, {
      scope: card.scope,
      scope_icon: card.scope_icon,
      body: text,
      internal: internal.value,
      expected_edit_version: version,
    })
  }

  function finish(saved: MeetingCardResponse): void {
    if (timer) clearTimeout(timer)
    stop()
    options.onSaved(saved)
  }

  async function onConflict(): Promise<void> {
    const fresh = await getMeetingCard(options.meetingId(), cardId())
    openMerge(fresh)
  }

  /** Saves the card; true when it saved, false when it opened the merge or failed. */
  async function save(): Promise<boolean> {
    saving.value = true
    error.value = null
    try {
      finish(await put(body.value, baseVersion.value))
      return true
    } catch (err) {
      if (apiErrorStatus(err) === 409) await onConflict().catch((reason: unknown) => (error.value = reason))
      else error.value = err
      return false
    } finally {
      saving.value = false
    }
  }

  /** Saves the merged text over the version the merge dialog showed. */
  async function saveMerged(text: string): Promise<boolean> {
    saving.value = true
    error.value = null
    body.value = text
    try {
      finish(await put(text, merge.theirVersion))
      return true
    } catch (err) {
      if (apiErrorStatus(err) === 409) await onConflict().catch((reason: unknown) => (error.value = reason))
      else error.value = err
      return false
    } finally {
      saving.value = false
    }
  }

  /** Keeps editing the user's own text after closing the merge. */
  function closeMerge(): void {
    merge.visible = false
  }

  return {
    editing,
    body,
    internal,
    saving,
    error,
    draftState,
    storedDraft,
    merge,
    start,
    stop,
    save,
    saveMerged,
    closeMerge,
    restoreDraft,
    mergeDraft,
    discardDraft,
  }
}
