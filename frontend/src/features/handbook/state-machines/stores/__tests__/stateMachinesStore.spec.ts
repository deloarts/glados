import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { StateMachinesResponse } from '../../types/stateMachinesResponse'

const getStateMachinesMock = vi.fn<() => Promise<StateMachinesResponse>>()

vi.mock('../../api/getStateMachines', () => ({
  getStateMachines: () => getStateMachinesMock(),
}))

import { useStateMachinesStore } from '../stateMachinesStore'

function makeResponse(): StateMachinesResponse {
  return {
    machines: [
      {
        key: 'production_order_status',
        entity: 'Production order',
        description: null,
        kind: 'intent',
        rules: [],
        intents: [],
        transitions: [],
        states: [{ value: 'queued', initial: true, terminal: false }],
        edges: [],
      },
    ],
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  getStateMachinesMock.mockReset()
})

describe('stateMachinesStore', () => {
  it('fetches once and serves every following caller from the cached response', async () => {
    getStateMachinesMock.mockResolvedValue(makeResponse())
    const store = useStateMachinesStore()

    await store.fetch()
    await store.fetch()
    await store.fetch()

    expect(getStateMachinesMock).toHaveBeenCalledTimes(1)
    expect(store.machines).toHaveLength(1)
    expect(store.loaded).toBe(true)
  })

  it('collapses two callers racing before the first response lands into one request', async () => {
    let resolve!: (value: StateMachinesResponse) => void
    getStateMachinesMock.mockReturnValue(
      new Promise((r) => {
        resolve = r
      }),
    )
    const store = useStateMachinesStore()

    const first = store.fetch()
    const second = store.fetch()
    resolve(makeResponse())
    await Promise.all([first, second])

    expect(getStateMachinesMock).toHaveBeenCalledTimes(1)
    expect(store.machines).toHaveLength(1)
  })

  it('records the error and leaves the catalog retryable on failure', async () => {
    getStateMachinesMock.mockRejectedValueOnce(new Error('network down'))
    const store = useStateMachinesStore()

    await store.fetch()
    expect(store.error).toBeDefined()
    expect(store.loaded).toBe(false)

    getStateMachinesMock.mockResolvedValueOnce(makeResponse())
    await store.fetch()

    expect(getStateMachinesMock).toHaveBeenCalledTimes(2)
    expect(store.loaded).toBe(true)
    expect(store.error).toBeNull()
  })

  it('refresh() forces a new request even when already loaded', async () => {
    getStateMachinesMock.mockResolvedValue(makeResponse())
    const store = useStateMachinesStore()

    await store.fetch()
    await store.refresh()

    expect(getStateMachinesMock).toHaveBeenCalledTimes(2)
  })
})
