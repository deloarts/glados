import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

import type { PdmSyncActivity } from '../../types/adminSettingsTypes'

const getPdmSyncActivityMock = vi.fn<() => Promise<PdmSyncActivity>>()

vi.mock('../../api/getPdmSyncActivity', () => ({
  getPdmSyncActivity: () => getPdmSyncActivityMock(),
}))

import { usePdmSyncActivityStore } from '../pdmSyncActivityStore'

const IDLE: PdmSyncActivity = { requested: false, run: null, recent_entries: [] }
const REQUESTED: PdmSyncActivity = { requested: true, run: null, recent_entries: [] }

describe('pdmSyncActivityStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getPdmSyncActivityMock.mockReset()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('is busy while a synchronisation is requested', async () => {
    getPdmSyncActivityMock.mockResolvedValue(REQUESTED)
    const store = usePdmSyncActivityStore()

    store.startPolling()
    await flushPromises()

    expect(store.busy).toBe(true)
    store.stopPolling()
  })

  it('polls every 2 s while busy and every 10 s while idle', async () => {
    getPdmSyncActivityMock.mockResolvedValue(REQUESTED)
    const store = usePdmSyncActivityStore()
    store.startPolling()
    await flushPromises()
    expect(getPdmSyncActivityMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(2000)
    expect(getPdmSyncActivityMock).toHaveBeenCalledTimes(2)

    getPdmSyncActivityMock.mockResolvedValue(IDLE)
    await vi.advanceTimersByTimeAsync(2000)
    expect(getPdmSyncActivityMock).toHaveBeenCalledTimes(3)
    expect(store.busy).toBe(false)

    await vi.advanceTimersByTimeAsync(9000)
    expect(getPdmSyncActivityMock).toHaveBeenCalledTimes(3)
    await vi.advanceTimersByTimeAsync(1000)
    expect(getPdmSyncActivityMock).toHaveBeenCalledTimes(4)

    store.stopPolling()
  })

  it('stops polling once the last consumer leaves', async () => {
    getPdmSyncActivityMock.mockResolvedValue(IDLE)
    const store = usePdmSyncActivityStore()
    store.startPolling()
    store.startPolling()
    await flushPromises()

    store.stopPolling()
    await vi.advanceTimersByTimeAsync(10000)
    expect(getPdmSyncActivityMock).toHaveBeenCalledTimes(2)

    store.stopPolling()
    await vi.advanceTimersByTimeAsync(30000)
    expect(getPdmSyncActivityMock).toHaveBeenCalledTimes(2)
  })

  it('marks a request as busy before the next poll confirms it', async () => {
    getPdmSyncActivityMock.mockResolvedValue(IDLE)
    const store = usePdmSyncActivityStore()
    store.startPolling()
    await flushPromises()

    getPdmSyncActivityMock.mockReturnValue(new Promise(() => {}))
    store.markRequested()

    expect(store.busy).toBe(true)
    store.stopPolling()
  })
})
