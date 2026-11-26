import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { SseHttpError } from '@/core/realtime/sseClient'

import type {
  AutoPlanProgressEvent,
  AutoPlanProgressOrder,
  AutoPlanRequest,
  AutoPlanResponse,
  AutoPlanRun,
  AutoPlanRunStatus,
} from '../../types/scheduleBoardResponse'
import type { UserResponse } from '@/core/types/userResponse'

type OnProgress = (ev: AutoPlanProgressEvent) => void

const streamAutoPlanScheduleMock =
  vi.fn<(payload: AutoPlanRequest, onProgress: OnProgress, signal: AbortSignal) => Promise<AutoPlanResponse>>()

vi.mock('../../api/autoPlanScheduleStream', () => {
  class AutoPlanConnectionLostError extends Error {
    constructor() {
      super('Auto-plan stream ended without a result or error frame')
      this.name = 'AutoPlanConnectionLostError'
    }
  }
  return {
    streamAutoPlanSchedule: (payload: AutoPlanRequest, onProgress: OnProgress, signal: AbortSignal) =>
      streamAutoPlanScheduleMock(payload, onProgress, signal),
    AutoPlanConnectionLostError,
  }
})

const getAutoPlanRunStatusMock = vi.fn<() => Promise<AutoPlanRunStatus>>()

vi.mock('../../api/getAutoPlanRunStatus', () => ({
  getAutoPlanRunStatus: () => getAutoPlanRunStatusMock(),
}))

import { useAutoPlanRunStore, AutoPlanAlreadyRunningError, AutoPlanRunTakenError } from '../autoPlanRunStore'
import { AutoPlanConnectionLostError } from '../../api/autoPlanScheduleStream'

const payload = {} as AutoPlanRequest

function progressEvent(overrides: Partial<AutoPlanProgressEvent> = {}): AutoPlanProgressEvent {
  return { stage: 'preparing', current: null, total: null, order: null, ...overrides }
}

function makeResponse(overrides: Partial<AutoPlanResponse> = {}): AutoPlanResponse {
  return {
    proposals: [],
    skipped_pinned_or_in_progress: 0,
    skipped_todays_planned: 0,
    skipped: [],
    redated: [],
    kept_day: 0,
    walk_failed: false,
    ...overrides,
  }
}

function makeRun(overrides: Partial<AutoPlanRun> = {}): AutoPlanRun {
  return {
    run_id: 'run-1',
    user_id: 1,
    user_name: 'Alex Runner',
    started_at: '2026-08-24T09:00:00Z',
    stage: 'placing',
    current: 1,
    total: 5,
    ...overrides,
  }
}

function orderEntry(overrides: Partial<AutoPlanProgressOrder> = {}): AutoPlanProgressOrder {
  return {
    order_id: 1,
    production_order_number: 'PO-1',
    lot_number: 'LOT-1',
    made_item_part_number: 'PN-1',
    placed: true,
    before_machine_id: null,
    after_machine_id: 5,
    before_machine_pool_id: null,
    after_machine_pool_id: null,
    ...overrides,
  }
}

// A controllable, not-yet-settled promise that lets a test drive onProgress
// calls mid-run before choosing how the run terminates.
function deferred<T>(): {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (reason?: unknown) => void
} {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('useAutoPlanRunStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    streamAutoPlanScheduleMock.mockReset()
    getAutoPlanRunStatusMock.mockReset()
    getAutoPlanRunStatusMock.mockResolvedValue({ running: false, run: null })
  })

  it('starts idle with an indeterminate percent', () => {
    const store = useAutoPlanRunStore()

    expect(store.status).toBe('idle')
    expect(store.percent).toBeNull()
  })

  it('percent is indeterminate before totals are known, tracks current/total within placing, and resets when recomputing starts its own count', async () => {
    let onProgress!: OnProgress
    const { promise, resolve } = deferred<AutoPlanResponse>()
    streamAutoPlanScheduleMock.mockImplementation(async (_payload, progress) => {
      onProgress = progress
      return promise
    })
    const store = useAutoPlanRunStore()
    const runPromise = store.run(payload)

    onProgress(progressEvent({ stage: 'preparing' }))
    expect(store.percent).toBeNull()

    onProgress(progressEvent({ stage: 'loading_orders' }))
    expect(store.percent).toBeNull()

    onProgress(progressEvent({ stage: 'placing', current: 0, total: 4 }))
    expect(store.percent).toBe(0)

    onProgress(progressEvent({ stage: 'placing', current: 2, total: 4 }))
    expect(store.percent).toBe(50)

    // recomputing starts its own current/total pair, independent of
    // placing's, so percent must reset to that stage's own 0-100 range.
    onProgress(progressEvent({ stage: 'recomputing', current: 0, total: 2 }))
    expect(store.percent).toBe(0)

    onProgress(progressEvent({ stage: 'recomputing', current: 1, total: 2 }))
    expect(store.percent).toBe(50)

    onProgress(progressEvent({ stage: 'finalizing' }))
    expect(store.percent).toBeNull()

    resolve(makeResponse())
    await runPromise
  })

  it('appends a feed row for every placing event that carries an order, in order, and ignores placing events without one', async () => {
    let onProgress!: OnProgress
    const { promise, resolve } = deferred<AutoPlanResponse>()
    streamAutoPlanScheduleMock.mockImplementation(async (_payload, progress) => {
      onProgress = progress
      return promise
    })
    const store = useAutoPlanRunStore()
    const runPromise = store.run(payload)

    // A bare total-announcement frame carries no order and must not
    // produce a feed row.
    onProgress(progressEvent({ stage: 'placing', current: 0, total: 2, order: null }))
    expect(store.feed).toEqual([])

    const placed = orderEntry({ order_id: 1, placed: true })
    onProgress(progressEvent({ stage: 'placing', current: 1, total: 2, order: placed }))
    const skipped = orderEntry({
      order_id: 2,
      placed: false,
      before_machine_id: 9,
      after_machine_id: 9,
    })
    onProgress(progressEvent({ stage: 'placing', current: 2, total: 2, order: skipped }))

    expect(store.feed).toEqual([placed, skipped])

    resolve(makeResponse())
    await runPromise
  })

  it('replaces the row of an order streamed again, so a placement the write dropped ends as skipped', async () => {
    let onProgress!: OnProgress
    const { promise, resolve } = deferred<AutoPlanResponse>()
    streamAutoPlanScheduleMock.mockImplementation(async (_payload, progress) => {
      onProgress = progress
      return promise
    })
    const store = useAutoPlanRunStore()
    const runPromise = store.run(payload)

    const other = orderEntry({ order_id: 2, placed: true })
    onProgress(progressEvent({ stage: 'placing', current: 1, total: 2, order: orderEntry({ order_id: 1 }) }))
    onProgress(progressEvent({ stage: 'placing', current: 2, total: 2, order: other }))
    const dropped = orderEntry({
      order_id: 1,
      placed: false,
      before_machine_id: 9,
      after_machine_id: 9,
      reason: 'changed_while_planning',
    })
    onProgress(progressEvent({ stage: 'placing', current: 2, total: 2, order: dropped }))

    expect(store.feed).toEqual([dropped, other])

    resolve(makeResponse())
    await runPromise
  })

  it('caps the feed at 1000 rows, dropping the oldest first', async () => {
    let onProgress!: OnProgress
    const { promise, resolve } = deferred<AutoPlanResponse>()
    streamAutoPlanScheduleMock.mockImplementation(async (_payload, progress) => {
      onProgress = progress
      return promise
    })
    const store = useAutoPlanRunStore()
    const runPromise = store.run(payload)

    for (let i = 1; i <= 1005; i++) {
      onProgress(
        progressEvent({ stage: 'placing', current: i, total: 1005, order: orderEntry({ order_id: i }) }),
      )
    }

    expect(store.feed).toHaveLength(1000)
    expect(store.feed[0]!.order_id).toBe(6)
    expect(store.feed[store.feed.length - 1]!.order_id).toBe(1005)

    resolve(makeResponse())
    await runPromise
  })

  it('returns status to idle and records result after a successful run', async () => {
    const response = makeResponse()
    streamAutoPlanScheduleMock.mockResolvedValue(response)
    const store = useAutoPlanRunStore()

    await store.run(payload)

    expect(store.status).toBe('idle')
    expect(store.result).toEqual(response)
    expect(store.errorDetail).toBeNull()
    expect(store.connectionLost).toBe(false)
  })

  it('returns status to idle and records errorDetail after a rejected run, rethrowing the error', async () => {
    streamAutoPlanScheduleMock.mockRejectedValue(new Error('boom'))
    const store = useAutoPlanRunStore()

    await expect(store.run(payload)).rejects.toThrow('boom')

    expect(store.status).toBe('idle')
    expect(store.errorDetail).toBe('boom')
    expect(store.result).toBeNull()
    expect(store.connectionLost).toBe(false)
  })

  it('returns status to idle and records connectionLost after AutoPlanConnectionLostError, rethrowing the error', async () => {
    streamAutoPlanScheduleMock.mockRejectedValue(new AutoPlanConnectionLostError())
    const store = useAutoPlanRunStore()

    await expect(store.run(payload)).rejects.toBeInstanceOf(AutoPlanConnectionLostError)

    expect(store.status).toBe('idle')
    expect(store.connectionLost).toBe(true)
    expect(store.result).toBeNull()
    expect(store.errorDetail).toBeNull()
  })

  it('clears the previous terminal outcome as soon as the next run starts', async () => {
    streamAutoPlanScheduleMock.mockRejectedValueOnce(new Error('first failure'))
    const store = useAutoPlanRunStore()
    await expect(store.run(payload)).rejects.toThrow('first failure')
    expect(store.errorDetail).toBe('first failure')

    const { promise, resolve } = deferred<AutoPlanResponse>()
    streamAutoPlanScheduleMock.mockImplementationOnce(async () => promise)
    const secondRun = store.run(payload)

    // resetState() runs synchronously at the top of run(), before the
    // stream call, so the stale outcome is gone immediately, not only once
    // the second run itself terminates.
    expect(store.errorDetail).toBeNull()
    expect(store.connectionLost).toBe(false)
    expect(store.result).toBeNull()

    const response = makeResponse()
    resolve(response)
    await secondRun

    expect(store.result).toEqual(response)
  })

  it('single-run guard: run() while a run is active rejects immediately with AutoPlanAlreadyRunningError and does not start a second stream; the first run still completes normally', async () => {
    const { promise, resolve } = deferred<AutoPlanResponse>()
    streamAutoPlanScheduleMock.mockImplementation(async () => promise)
    const store = useAutoPlanRunStore()

    const firstRun = store.run(payload)
    expect(store.status).toBe('running')

    await expect(store.run(payload)).rejects.toBeInstanceOf(AutoPlanAlreadyRunningError)
    expect(streamAutoPlanScheduleMock).toHaveBeenCalledTimes(1)

    const response = makeResponse()
    resolve(response)
    await expect(firstRun).resolves.toEqual(response)

    expect(store.status).toBe('idle')
    expect(store.result).toEqual(response)
  })

  describe('activeRun / isMine / anyRunActive', () => {
    it('fetchStatus populates activeRun from the status endpoint', async () => {
      const run = makeRun()
      getAutoPlanRunStatusMock.mockResolvedValue({ running: true, run })
      const store = useAutoPlanRunStore()

      await store.fetchStatus()

      expect(store.activeRun).toEqual(run)
    })

    it('fetchStatus leaves the previous activeRun in place and never throws when the request fails', async () => {
      const run = makeRun()
      getAutoPlanRunStatusMock.mockResolvedValueOnce({ running: true, run })
      const store = useAutoPlanRunStore()
      await store.fetchStatus()

      getAutoPlanRunStatusMock.mockRejectedValueOnce(new Error('network down'))
      await expect(store.fetchStatus()).resolves.toBeUndefined()

      expect(store.activeRun).toEqual(run)
    })

    it('anyRunActive is true exactly when activeRun is non-null', async () => {
      const store = useAutoPlanRunStore()
      expect(store.anyRunActive).toBe(false)

      getAutoPlanRunStatusMock.mockResolvedValueOnce({ running: true, run: makeRun() })
      await store.fetchStatus()
      expect(store.anyRunActive).toBe(true)

      getAutoPlanRunStatusMock.mockResolvedValueOnce({ running: false, run: null })
      await store.fetchStatus()
      expect(store.anyRunActive).toBe(false)
    })

    it('isMine is true only when activeRun.user_id matches the signed-in user, and false with no active run', async () => {
      useCurrentUserStore().user = { id: 3 } as unknown as UserResponse
      const store = useAutoPlanRunStore()
      expect(store.isMine).toBe(false)

      getAutoPlanRunStatusMock.mockResolvedValueOnce({ running: true, run: makeRun({ user_id: 3 }) })
      await store.fetchStatus()
      expect(store.isMine).toBe(true)

      getAutoPlanRunStatusMock.mockResolvedValueOnce({ running: true, run: makeRun({ user_id: 9 }) })
      await store.fetchStatus()
      expect(store.isMine).toBe(false)
    })
  })

  it("run(): a 409 SseHttpError refetches status and rejects with AutoPlanRunTakenError instead of setting errorDetail (losing the race isn't an error)", async () => {
    const holderRun = makeRun({ user_id: 9 })
    getAutoPlanRunStatusMock.mockResolvedValueOnce({ running: true, run: holderRun })
    streamAutoPlanScheduleMock.mockRejectedValue(new SseHttpError(409))
    const store = useAutoPlanRunStore()

    await expect(store.run(payload)).rejects.toBeInstanceOf(AutoPlanRunTakenError)

    expect(getAutoPlanRunStatusMock).toHaveBeenCalledTimes(1)
    expect(store.activeRun).toEqual(holderRun)
    expect(store.errorDetail).toBeNull()
    expect(store.status).toBe('idle')
  })

  describe('polling', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('startObserverPolling polls every 3s; stopObserverPolling clears it so no further calls happen afterwards', async () => {
      getAutoPlanRunStatusMock.mockResolvedValue({ running: false, run: null })
      const store = useAutoPlanRunStore()

      store.startObserverPolling()
      await vi.advanceTimersByTimeAsync(3000)
      expect(getAutoPlanRunStatusMock).toHaveBeenCalledTimes(1)

      await vi.advanceTimersByTimeAsync(3000)
      expect(getAutoPlanRunStatusMock).toHaveBeenCalledTimes(2)

      store.stopObserverPolling()
      getAutoPlanRunStatusMock.mockClear()
      await vi.advanceTimersByTimeAsync(9000)

      expect(getAutoPlanRunStatusMock).not.toHaveBeenCalled()
    })

    it('calling startObserverPolling twice does not stack a second interval', async () => {
      getAutoPlanRunStatusMock.mockResolvedValue({ running: false, run: null })
      const store = useAutoPlanRunStore()

      store.startObserverPolling()
      store.startObserverPolling()
      await vi.advanceTimersByTimeAsync(3000)

      expect(getAutoPlanRunStatusMock).toHaveBeenCalledTimes(1)
      store.stopObserverPolling()
    })

    it('the 30s safety poll starts itself once a run becomes active and stops itself once status returns null', async () => {
      const run = makeRun()
      getAutoPlanRunStatusMock.mockResolvedValueOnce({ running: true, run })
      const store = useAutoPlanRunStore()

      await store.fetchStatus()
      expect(getAutoPlanRunStatusMock).toHaveBeenCalledTimes(1)

      getAutoPlanRunStatusMock.mockResolvedValueOnce({ running: false, run: null })
      await vi.advanceTimersByTimeAsync(30000)

      expect(getAutoPlanRunStatusMock).toHaveBeenCalledTimes(2)
      expect(store.activeRun).toBeNull()

      getAutoPlanRunStatusMock.mockClear()
      await vi.advanceTimersByTimeAsync(60000)

      expect(getAutoPlanRunStatusMock).not.toHaveBeenCalled()
    })
  })
})
