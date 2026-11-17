import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const fetchPdmPreviewMock = vi.fn<(kind: 'made' | 'bought') => Promise<PdmPreviewResponse>>()

vi.mock('../api', () => ({
  fetchPdmPreview: (kind: 'made' | 'bought') => fetchPdmPreviewMock(kind),
}))

import { usePdmPreviewStore } from '../pdmPreviewStore'

import type { PdmPreviewResponse } from '../api'

function response(overrides: Partial<PdmPreviewResponse> = {}): PdmPreviewResponse {
  return {
    kind: 'made',
    enabled: true,
    unlinked: [],
    newer: [],
    ...overrides,
  }
}

describe('usePdmPreviewStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    fetchPdmPreviewMock.mockReset()
  })

  it('starts empty and disabled for both kinds before load() is called', () => {
    const store = usePdmPreviewStore()

    expect(store.state.made).toEqual({ enabled: false, unlinked: [], newer: {} })
    expect(store.state.bought).toEqual({ enabled: false, unlinked: [], newer: {} })
  })

  it('load(kind) populates enabled/unlinked and keys newer by item public_id', async () => {
    fetchPdmPreviewMock.mockResolvedValue(
      response({
        unlinked: [
          {
            file_id: 1,
            name: 'part.sldprt',
            path: '\\Made\\part.sldprt',
            part_number: 'CAD-1',
            revision: 'A',
            article_name: 'Bracket',
            version: 2,
            state: 'Released',
            modified_at: null,
            sync_state: 'skipped',
            last_error: null,
          },
        ],
        newer: [
          {
            item_id: 5,
            item_public_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            part_number: 'CAD-2',
            revision: 'B',
            file_id: 2,
            name: 'other.sldprt',
            version: 4,
            state: 'Released',
            modified_at: '2026-09-08T10:00:00Z',
          },
        ],
      }),
    )
    const store = usePdmPreviewStore()

    await store.load('made')

    expect(store.state.made.enabled).toBe(true)
    expect(store.state.made.unlinked).toHaveLength(1)
    expect(store.state.made.unlinked[0]?.part_number).toBe('CAD-1')
    expect(store.isNewer('made', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')?.item_id).toBe(5)
    expect(store.isNewer('made', 'does-not-exist')).toBeUndefined()
  })

  it('keeps made and bought state independent', async () => {
    fetchPdmPreviewMock.mockImplementation((kind) =>
      Promise.resolve(response({ kind, enabled: kind === 'made' })),
    )
    const store = usePdmPreviewStore()

    await store.load('made')
    await store.load('bought')

    expect(store.state.made.enabled).toBe(true)
    expect(store.state.bought.enabled).toBe(false)
  })

  it('toggles loadingMade/loadingBought around the fetch, independently per kind', async () => {
    let resolveMade: (v: PdmPreviewResponse) => void = () => {}
    fetchPdmPreviewMock.mockImplementation(
      (kind) =>
        new Promise((resolve) => {
          if (kind === 'made') resolveMade = resolve
          else resolve(response({ kind }))
        }),
    )
    const store = usePdmPreviewStore()

    const madePromise = store.load('made')
    expect(store.loadingMade).toBe(true)
    expect(store.loadingBought).toBe(false)

    resolveMade(response({ kind: 'made' }))
    await madePromise

    expect(store.loadingMade).toBe(false)
  })

  it('leaves state unchanged when the fetch fails', async () => {
    fetchPdmPreviewMock.mockRejectedValue(new Error('network error'))
    const store = usePdmPreviewStore()

    await store.load('made')

    expect(store.state.made).toEqual({ enabled: false, unlinked: [], newer: {} })
  })
})
