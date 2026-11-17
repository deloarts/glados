import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const getMock = vi.fn<(url: string) => Promise<{ data: unknown }>>()
const postMock = vi.fn<(url: string, payload?: unknown) => Promise<{ data: unknown }>>()
const patchMock = vi.fn<(url: string, payload?: unknown) => Promise<{ data: unknown }>>()
const putMock = vi.fn<(url: string, payload?: unknown) => Promise<{ data: unknown }>>()
const deleteMock = vi.fn<(url: string) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: (url: string, payload?: unknown) => postMock(url, payload),
    patch: (url: string, payload?: unknown) => patchMock(url, payload),
    put: (url: string, payload?: unknown) => putMock(url, payload),
    delete: (url: string) => deleteMock(url),
  },
}))

import { useProductionLotDetailStore } from '../productionLotDetailStore'
import { makeLotResponse } from '@/test-utils/factories'

import type { LotResponse } from '../../../types/productionLotsResponse'

/**
 * A promise plus its resolve, so a test can control exactly when a given
 * call settles instead of racing on real timers. Mirrors the helper in
 * productionLotsStore.spec.ts.
 */
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function makeLot(overrides: Partial<LotResponse> = {}): LotResponse {
  return makeLotResponse({
    public_id: '22222222-2222-2222-2222-222222222222',
    lot_number: 'LOT-1',
    quantity_completed: 0,
    status: 'draft',
    project_id: 1,
    ...overrides,
  })
}

describe('useProductionLotDetailStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getMock.mockReset()
    postMock.mockReset()
    patchMock.mockReset()
    putMock.mockReset()
    deleteMock.mockReset()
  })

  describe('fetch', () => {
    it('toggles loading around the request and populates lot on success', async () => {
      const lotDeferred = deferred<{ data: LotResponse }>()
      getMock.mockReturnValueOnce(lotDeferred.promise)
      const store = useProductionLotDetailStore()

      const call = store.fetch(1)
      expect(store.loading).toBe(true)

      lotDeferred.resolve({ data: makeLot({ id: 1 }) })
      await call

      expect(store.loading).toBe(false)
      expect(store.lot?.id).toBe(1)
      expect(getMock).toHaveBeenCalledWith('/production-lots/1')
    })

    it('still resets loading, and leaves lot untouched, when the request fails', async () => {
      getMock.mockRejectedValueOnce(new Error('network error'))
      const store = useProductionLotDetailStore()

      await store.fetch(1)

      expect(store.loading).toBe(false)
      expect(store.lot).toBeNull()
    })
  })

  describe('fetchChangelog / fetchCompletions / fetchEvents', () => {
    it('fetchChangelog populates changelog verbatim from the response', async () => {
      getMock.mockResolvedValueOnce({ data: ['lot created', 'status changed to queued'] })
      const store = useProductionLotDetailStore()

      await store.fetchChangelog(1)

      expect(getMock).toHaveBeenCalledWith('/production-lots/1/changelog')
      expect(store.changelog).toEqual(['lot created', 'status changed to queued'])
    })

    it('fetchCompletions populates completions verbatim from the response', async () => {
      const completions = [{ id: 1 }] as unknown as LotResponse[]
      getMock.mockResolvedValueOnce({ data: completions })
      const store = useProductionLotDetailStore()

      await store.fetchCompletions(1)

      expect(getMock).toHaveBeenCalledWith('/production-lots/1/completions')
      expect(store.completions).toEqual(completions)
    })

    it('fetchEvents populates events verbatim from the response', async () => {
      const events = [{ id: 1 }] as unknown as LotResponse[]
      getMock.mockResolvedValueOnce({ data: events })
      const store = useProductionLotDetailStore()

      await store.fetchEvents(1)

      expect(getMock).toHaveBeenCalledWith('/production-lots/1/events')
      expect(store.events).toEqual(events)
    })
  })

  describe('refetch', () => {
    it('is a no-op when no lot has been loaded yet', async () => {
      const store = useProductionLotDetailStore()

      await store.refetch()

      expect(getMock).not.toHaveBeenCalled()
    })

    it('reloads the currently-loaded lot by its own id', async () => {
      getMock.mockResolvedValue({ data: makeLot({ id: 7 }) })
      const store = useProductionLotDetailStore()
      await store.fetch(7)
      getMock.mockClear()

      await store.refetch()

      expect(getMock).toHaveBeenCalledWith('/production-lots/7')
    })
  })

  describe('clear', () => {
    it('resets lot, changelog, completions and events back to their defaults', async () => {
      getMock.mockImplementation((url: string) => {
        if (url.endsWith('/changelog')) return Promise.resolve({ data: ['created'] })
        if (url.endsWith('/completions')) return Promise.resolve({ data: [{ id: 1 }] })
        if (url.endsWith('/events')) return Promise.resolve({ data: [{ id: 1 }] })
        return Promise.resolve({ data: makeLot({ id: 1 }) })
      })
      const store = useProductionLotDetailStore()
      await store.fetch(1)
      await store.fetchChangelog(1)
      await store.fetchCompletions(1)
      await store.fetchEvents(1)
      expect(store.lot).not.toBeNull()

      store.clear()

      expect(store.lot).toBeNull()
      expect(store.changelog).toEqual([])
      expect(store.completions).toEqual([])
      expect(store.events).toEqual([])
    })
  })

  describe('mutating flag lifecycle (withMutation)', () => {
    it('sets mutating synchronously and clears it only once the post-mutation refetch settles', async () => {
      getMock.mockResolvedValue({ data: makeLot({ id: 1 }) })
      const store = useProductionLotDetailStore()
      await store.fetch(1)

      const postDeferred = deferred<{ data: unknown }>()
      postMock.mockReturnValueOnce(postDeferred.promise)
      const refetchDeferred = deferred<{ data: unknown }>()
      getMock.mockReturnValueOnce(refetchDeferred.promise)

      const call = store.addStep(1, { position_id: 5 })
      // withMutation flips mutating.value = true before its first await, so
      // it is already true the instant addStep() returns control here.
      expect(store.mutating).toBe(true)

      postDeferred.resolve({ data: {} })
      await Promise.resolve()
      // Still mutating: the post-mutation refetch is in flight.
      expect(store.mutating).toBe(true)

      refetchDeferred.resolve({ data: makeLot({ id: 1 }) })
      await call

      expect(store.mutating).toBe(false)
    })

    it('resets mutating without refetching when the mutating call itself rejects', async () => {
      getMock.mockResolvedValue({ data: makeLot({ id: 1 }) })
      const store = useProductionLotDetailStore()
      await store.fetch(1)
      getMock.mockClear()
      postMock.mockRejectedValueOnce(new Error('500'))

      await expect(store.addStep(1, { position_id: 5 })).rejects.toThrow('500')

      expect(store.mutating).toBe(false)
      // refetch() is only reached after a successful action; a failed
      // action must not trigger one.
      expect(getMock).not.toHaveBeenCalled()
    })
  })

  // Every mutating action funnels through withMutation, which always
  // refetches the lot after a successful call. This table pins down each
  // action's own HTTP verb/URL/payload plus that shared refetch behaviour,
  // without repeating the full mutating-flag mechanics per action (covered
  // once above).
  type Verb = 'post' | 'patch' | 'put' | 'delete'
  interface MutationCase {
    label: string
    verb: Verb
    url: string
    payload?: unknown
    invoke: (store: ReturnType<typeof useProductionLotDetailStore>) => Promise<unknown>
  }

  const mutationCases: MutationCase[] = [
    {
      label: 'addStep',
      verb: 'post',
      url: '/production-lots/1/steps',
      payload: { position_id: 5 },
      invoke: (store) => store.addStep(1, { position_id: 5 }),
    },
    {
      label: 'updateStep',
      verb: 'patch',
      url: '/production-lots/1/steps/9',
      payload: { note: 'updated' },
      invoke: (store) => store.updateStep(1, 9, { note: 'updated' }),
    },
    {
      label: 'removeStep',
      verb: 'delete',
      url: '/production-lots/1/steps/9',
      invoke: (store) => store.removeStep(1, 9),
    },
    {
      label: 'reorderSteps',
      verb: 'put',
      url: '/production-lots/1/steps/reorder',
      payload: { ordered_step_ids: [9, 8] },
      invoke: (store) => store.reorderSteps(1, [9, 8]),
    },
    {
      label: 'regroupPositions',
      verb: 'put',
      url: '/production-lots/1/positions',
      payload: {
        groups: [
          [1, 2],
          [3],
        ],
      },
      invoke: (store) =>
        store.regroupPositions(1, [
          [1, 2],
          [3],
        ]),
    },
    {
      label: 'appendPosition',
      verb: 'post',
      url: '/production-lots/1/positions',
      payload: { steps: [{ role: 'fabrication' }] },
      invoke: (store) => store.appendPosition(1, { steps: [{ role: 'fabrication' }] }),
    },
    {
      label: 'saveStructure',
      verb: 'put',
      url: '/production-lots/1/structure',
      payload: { positions: [{ steps: [{ id: null, role: 'fabrication' }] }] },
      invoke: (store) =>
        store.saveStructure(1, { positions: [{ steps: [{ id: null, role: 'fabrication' }] }] }),
    },
    {
      label: 'assignPosition',
      verb: 'post',
      url: '/production-lots/1/positions/2/assign',
      payload: { order_id: 10, unit: 'pcs' },
      invoke: (store) => store.assignPosition(1, 2, { order_id: 10, unit: 'pcs' }),
    },
    {
      label: 'unassignPosition',
      verb: 'delete',
      url: '/production-lots/1/positions/2/assign',
      invoke: (store) => store.unassignPosition(1, 2),
    },
    {
      label: 'assignInternal',
      verb: 'post',
      url: '/production-lots/1/positions/2/assign-internal',
      payload: { orders: [{ machine_id: 5, quantity: 3 }] },
      invoke: (store) => store.assignInternal(1, 2, { orders: [{ machine_id: 5, quantity: 3 }] }),
    },
    {
      label: 'cancel',
      verb: 'post',
      url: '/production-lots/1/cancel',
      // The edit version the caller showed goes along.
      payload: { reason: 'wrong material', expected_edit_version: 4 },
      invoke: (store) => store.cancel(1, 4, 'wrong material'),
    },
    {
      label: 'complete',
      verb: 'post',
      url: '/production-lots/1/complete',
      payload: { reason: 'early finish', expected_edit_version: 4 },
      invoke: (store) => store.complete(1, 4, 'early finish'),
    },
    {
      label: 'hold',
      verb: 'post',
      url: '/production-lots/1/hold',
      payload: { reason: 'waiting on material' },
      invoke: (store) => store.hold(1, 'waiting on material'),
    },
    {
      label: 'resume',
      verb: 'post',
      url: '/production-lots/1/resume',
      invoke: (store) => store.resume(1),
    },
    {
      label: 'recordProvision',
      verb: 'post',
      url: '/production-lots/1/positions/2/provisions',
      payload: { quantity: 5, provision_date: '2026-08-01' },
      invoke: (store) =>
        store.recordProvision(1, 2, { quantity: 5, provision_date: '2026-08-01' }),
    },
  ]

  it.each(mutationCases)(
    '$label sends its request and triggers a post-mutation refetch',
    async ({ verb, url, payload, invoke }) => {
      getMock.mockResolvedValue({ data: makeLot({ id: 1 }) })
      postMock.mockResolvedValue({ data: {} })
      patchMock.mockResolvedValue({ data: {} })
      putMock.mockResolvedValue({ data: [] })
      deleteMock.mockResolvedValue({ data: undefined })
      const store = useProductionLotDetailStore()
      await store.fetch(1)
      getMock.mockClear()

      await invoke(store)

      const verbMock = { post: postMock, patch: patchMock, put: putMock, delete: deleteMock }[verb]
      // The delete shim only ever forwards one argument; post/patch/put
      // shims always forward a second (possibly undefined) argument,
      // toHaveBeenCalledWith is strict about arg count, so a payload-less
      // post/patch/put call (resume) must be asserted with an explicit
      // undefined rather than a 1-arg call.
      const expectedArgs =
        payload !== undefined ? [url, payload] : verb === 'delete' ? [url] : [url, undefined]
      expect(verbMock).toHaveBeenCalledWith(...expectedArgs)
      // withMutation always refetches the lot after a successful action.
      expect(getMock).toHaveBeenCalledWith('/production-lots/1')
    },
  )

  describe('fetchProvisions', () => {
    it('returns the provisions directly, without touching mutating or triggering a refetch', async () => {
      const provisions = [{ id: 1 }] as unknown as LotResponse[]
      getMock.mockResolvedValueOnce({ data: provisions })
      const store = useProductionLotDetailStore()

      const result = await store.fetchProvisions(1, 2)

      expect(getMock).toHaveBeenCalledWith('/production-lots/1/positions/2/provisions')
      expect(result).toEqual(provisions)
      expect(store.mutating).toBe(false)
    })
  })
})
