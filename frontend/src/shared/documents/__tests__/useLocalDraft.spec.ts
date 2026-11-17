import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { LOCAL_DRAFT_WRITE_MS, useLocalDraft } from '../composables/useLocalDraft'
import { pruneLocalDrafts, readLocalDraft, writeLocalDraft } from '../utils/localDraft'

interface Answers {
  answers: Record<string, string>
}

function setup(initial: { id: number | null; changed: string | null } = { id: 7, changed: '2026-10-21T08:00:00Z' }) {
  const doc = ref(initial)
  const onScreen = ref<Answers | null>(null)
  const scope = effectScope()
  const draft = scope.run(() =>
    useLocalDraft<Answers>({
      key: () => (doc.value.id === null ? null : `checklist.${doc.value.id}`),
      base: () => doc.value.changed,
      value: () => onScreen.value,
    }),
  )!
  return { doc, onScreen, draft, scope }
}

async function settle(): Promise<void> {
  await nextTick()
  await vi.advanceTimersByTimeAsync(LOCAL_DRAFT_WRITE_MS)
}

describe('useLocalDraft', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    localStorage.clear()
    setActivePinia(createPinia())
    useCurrentUserStore().user = { id: 1, permissions: [], is_systemuser: false } as never
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('keeps the changes on screen and drops the copy once they are saved', async () => {
    const { onScreen, draft } = setup()
    draft.check()
    expect(draft.offer.value).toBeNull()

    onScreen.value = { answers: { a1: 'ok' } }
    await settle()
    expect(readLocalDraft<Answers>(1, 'checklist.7')).toMatchObject({
      base: '2026-10-21T08:00:00Z',
      value: { answers: { a1: 'ok' } },
    })

    onScreen.value = null
    await settle()
    expect(readLocalDraft(1, 'checklist.7')).toBeNull()
  })

  it('offers a kept copy and leaves it alone until the offer is settled', async () => {
    writeLocalDraft(1, 'checklist.7', { answers: { a1: 'nok' } }, '2026-10-21T08:00:00Z')
    const { onScreen, draft } = setup()

    // The saved document shows no changes; that must not drop the copy.
    draft.check()
    await settle()
    expect(draft.offer.value).toMatchObject({ stale: false, draft: { value: { answers: { a1: 'nok' } } } })
    expect(readLocalDraft(1, 'checklist.7')).not.toBeNull()

    expect(draft.accept()).toEqual({ answers: { a1: 'nok' } })
    onScreen.value = { answers: { a1: 'nok' } }
    await settle()
    expect(draft.offer.value).toBeNull()
    expect(readLocalDraft(1, 'checklist.7')).not.toBeNull()
  })

  it('marks a copy stale when the document was saved after it, and drops it on discard', () => {
    writeLocalDraft(1, 'checklist.7', { answers: {} }, '2026-10-21T08:00:00Z')
    const { draft } = setup({ id: 7, changed: '2026-10-21T09:30:00Z' })

    draft.check()
    expect(draft.offer.value?.stale).toBe(true)

    draft.discard()
    expect(draft.offer.value).toBeNull()
    expect(readLocalDraft(1, 'checklist.7')).toBeNull()
  })

  it('keeps a dismissed copy until new changes replace it', async () => {
    writeLocalDraft(1, 'checklist.7', { answers: { a1: 'old' } }, null)
    const { onScreen, draft } = setup()
    draft.check()
    draft.dismiss()

    onScreen.value = null
    await settle()
    expect(readLocalDraft<Answers>(1, 'checklist.7')?.value).toEqual({ answers: { a1: 'old' } })

    onScreen.value = { answers: { a1: 'new' } }
    await settle()
    expect(readLocalDraft<Answers>(1, 'checklist.7')?.value).toEqual({ answers: { a1: 'new' } })
  })

  it('writes nothing for a document that was not checked yet, and offers a copy only to its user', async () => {
    writeLocalDraft(2, 'checklist.7', { answers: { a1: 'theirs' } }, null)
    const { onScreen, draft } = setup()

    onScreen.value = { answers: { a1: 'ok' } }
    await settle()
    expect(readLocalDraft(1, 'checklist.7')).toBeNull()

    draft.check()
    expect(draft.offer.value).toBeNull()
  })

  it('writes what is still waiting when the page goes away', async () => {
    const { onScreen, draft, scope } = setup()
    draft.check()
    onScreen.value = { answers: { a1: 'ok' } }
    await nextTick()

    scope.stop()
    expect(readLocalDraft(1, 'checklist.7')).not.toBeNull()
  })
})

describe('local draft storage', () => {
  beforeEach(() => localStorage.clear())

  const weeksAgo = (weeks: number) => new Date(Date.now() - weeks * 7 * 24 * 60 * 60 * 1000).toISOString()

  it('drops copies older than ten weeks and anything unreadable, of every user', () => {
    localStorage.setItem('glados.documentDraft.1.checklist.1', JSON.stringify({ savedAt: weeksAgo(11), base: null, value: {} }))
    localStorage.setItem('glados.documentDraft.2.checklist.4', JSON.stringify({ savedAt: weeksAgo(9), base: null, value: { a: 1 } }))
    localStorage.setItem('glados.documentDraft.1.checklist.2', 'not json')
    localStorage.setItem('unrelated', 'kept')

    pruneLocalDrafts()

    expect(localStorage.getItem('glados.documentDraft.1.checklist.1')).toBeNull()
    expect(localStorage.getItem('glados.documentDraft.1.checklist.2')).toBeNull()
    expect(readLocalDraft(2, 'checklist.4')?.value).toEqual({ a: 1 })
    expect(localStorage.getItem('unrelated')).toBe('kept')
  })

  it('does not offer a copy that has grown too old since the app started', () => {
    localStorage.setItem('glados.documentDraft.1.checklist.1', JSON.stringify({ savedAt: weeksAgo(11), base: null, value: {} }))
    expect(readLocalDraft(1, 'checklist.1')).toBeNull()
  })
})
